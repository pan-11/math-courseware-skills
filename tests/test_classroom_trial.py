"""Opt-in trial coverage and provenance; synthetic files are retained, never playback evidence."""
import copy
import importlib
from pathlib import Path
import shutil
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/math-courseware-studio/scripts'))
from runtime import classroom_trial as trial, click_answers, editable_delivery, state, review
from test_click_answers import fixture, answer, non_answer
from fixture_factory import retained_project


def initialize(root, five=False):
    path = root / ('中间文件/_state/project.json' if five else '_state/project.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    state.write_json(path, {'schema_version': '1.0', 'artifacts': {}, 'stale_targets': []})


def register_base(root, plan):
    state.register_artifact(root, 'editable-base-pptx', plan['source_deck'], metadata={
        'source_versions': plan['source_versions'], 'intermediate': True, 'refill_stage': 'base'})


def classroom_plan(component_report, component_plan):
    pages = []
    for page in component_report['pages']:
        units, steps = [], []
        for item in page['answers']:
            uid = 'answer-' + item['blank_id']
            fraction = any(c['kind'] == 'bar' for c in item['components'])
            unit = {'unit_id': uid, 'role': 'answer', 'kind': 'fraction' if fraction else 'text',
                    'purpose': 'answer', 'initial_visible': False,
                    'targets': [{'shape_id': c['shape_id'], 'expected_text': c['text']}
                                for c in item['components']]}
            if fraction:
                unit['logical_id'] = item['blank_id']
            units.append(unit)
            steps.append({'step_id': 'show-' + item['blank_id'], 'pause_reason': 'Students calculate before checking',
                          'actions': [{'unit_id': uid, 'effect': 'appear', 'trigger': 'on_click'}]})
        entry = {'page_id': page['page_id'], 'teaching_goal': 'Calculate and explain the answer',
                 'student_action': 'Calculate first, then compare',
                 'basis': {'path': 'inputs/answer-basis.json', 'locator': page['page_id']},
                 'initial_reason': 'Questions and original answers stay visible; new answers wait for clicks',
                 'units': units, 'steps': steps, 'existing_policy': 'reject_conflicts'}
        if not steps:
            entry['static_reason'] = 'No determinate new answers on this scanned page'
        pages.append(entry)
    return {'schema_version': 'classroom_animation_v1', 'mode': 'classroom',
            'source_deck': component_report['output'], 'source_sha256': component_report['output_sha256'],
            'source_versions': {**component_plan['source_versions'],
                                component_report['output']: component_report['output_sha256']},
            'output': 'editable/output/classroom.pptx', 'request': copy.deepcopy(component_plan['request']),
            'mapping': component_report['mapping'], 'pages': pages}


class ClassroomTrialActivationTests(unittest.TestCase):
    def test_exact_activation_is_required_before_reading_a_project(self):
        api = importlib.import_module('runtime.classroom_trial')
        for value in (None, '', '课堂动画试用v1', '课堂动画试用V1 '):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '课堂动画试用V1'):
                api.current(Path('missing-synthetic-project'), activation=value)


class ClassroomTrialIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed, cls.component_plan = fixture()
        initialize(cls.seed)
        instruction = 'Synthetic request: ' + trial.ACTIVATION + ' for this synthetic lesson only'
        authority = cls.seed / 'inputs/instruction.json'
        state.write_json(authority, {'user_instruction': instruction})
        cls.component_plan['request'] = {'user_instruction': instruction, 'evidence_ref': {
            'path': 'inputs/instruction.json', 'sha256': state.sha256(authority)}}
        cls.component_plan['source_versions']['inputs/instruction.json'] = state.sha256(authority)
        cls.component_plan['output'] = 'editable/output/components.pptx'
        cls.component_plan['pages'][0]['items'] = [answer(), answer('Q2', 2, True), non_answer('open_blank')]
        cls.original_objects = trial.classroom_animation.inspect(cls.seed / cls.component_plan['source_deck'])['slides'][0]['objects']
        for blank, name in [('Q4', 'existing-title'), ('Q5', 'math-block-1')]:
            obj = next(o for o in cls.original_objects if o['name'] == name)
            retained = non_answer('already_visible', blank)
            retained['existing_shapes'] = [{'shape_id': obj['shape_id'], 'expected_text': obj['text']}]
            cls.component_plan['pages'][0]['items'].append(retained)
        register_base(cls.seed, cls.component_plan)
        cls.component_report = trial.components(cls.seed, cls.component_plan, trial.ACTIVATION)
        cls.plan = classroom_plan(cls.component_report, cls.component_plan)
        legacy_plan = copy.deepcopy(cls.component_plan)
        legacy_plan['output'] = 'editable/output/legacy.pptx'
        cls.legacy = click_answers.build(cls.seed, legacy_plan)
        cls.copy_paths = set(cls.component_plan['source_versions'])
        for report in (cls.component_report, cls.legacy):
            cls.copy_paths.update((report['output'], report['plan']['path'], report['manifest']))
        print('TRIAL_SYNTHETIC_SEED=' + str(cls.seed), flush=True)

    def project(self, old=False, five=False):
        root = retained_project('classroom-trial')
        initialize(root, five)
        for relative in self.copy_paths:
            target = state.resolve(root, relative)
            trial.classroom_animation._parent(target.parent)
            shutil.copyfile(state.resolve(self.seed, relative), target)
        register_base(root, self.component_plan)
        if old:
            result = self.legacy
            state.register_artifact(root, 'editable-pptx', result['output'], metadata={
                'refill_stage': 'click_answers', 'source_versions': result['source_versions'],
                'base_ref': {'path': result['source_deck'], 'sha256': result['source_sha256']},
                'answer_manifest': {'path': result['manifest'], 'sha256': result['manifest_sha256']}})
        print('TRIAL_SYNTHETIC_PROJECT=' + str(root), flush=True)
        return root, copy.deepcopy(self.plan)

    def build(self, root, plan):
        return trial.build(root, plan, {'path': self.component_report['manifest'],
                                       'sha256': self.component_report['manifest_sha256']}, trial.ACTIVATION)

    def test_real_components_animation_register_current_collect_with_and_without_old_final(self):
        for old in (False, True):
            with self.subTest(old=old):
                root, plan = self.project(old=old)
                before = state.load_project(root)['artifacts'].get('editable-pptx')
                result = self.build(root, plan)
                selected = trial.register(root, result['manifest'], trial.ACTIVATION)
                self.assertEqual(selected['profile'], trial.PROFILE)
                current = trial.current(root, trial.ACTIVATION)
                self.assertEqual(len(current['answer_coverage']), 2)
                self.assertEqual(len(current['answer_coverage'][1]['shape_ids']), 3)
                self.assertTrue(all(c['status'] == 'unverified' for c in current['checks'].values()))
                self.assertEqual(state.load_project(root)['artifacts'].get('editable-pptx'), before)
                if old:
                    self.assertEqual(editable_delivery.current(root), before)
                else:
                    with self.assertRaisesRegex(ValueError, 'intermediate'):
                        editable_delivery.current(root)
                package = trial.collect(root, trial.ACTIVATION)
                self.assertEqual(package['scope'], 'ppt-only')
                self.assertFalse(package['course_complete'])
                folder = state.resolve(root, package['directory'])
                self.assertEqual({p.name for p in folder.iterdir()}, {'classroom-trial-v1.pptx', 'manifest.json'})
                self.assertEqual(state.sha256(state.resolve(root, package['files'][0]['path'])), result['output_sha256'])
                self.assertNotEqual(trial.collect(root, trial.ACTIVATION)['directory'], package['directory'])
                original_ref = current['registration_ref']
                trial.register(root, result['manifest'], trial.ACTIVATION)
                latest = trial.current(root, trial.ACTIVATION)
                receipt = state.read_json(state.resolve(root, latest['registration_ref']['path']))
                self.assertEqual(receipt['previous_registration']['registration_ref'], original_ref)
                self.assertTrue(state.resolve(root, original_ref['path']).is_file())

    def test_five_folder_logical_paths_support_current_and_collect(self):
        root, plan = self.project(five=True)
        result = self.build(root, plan)
        trial.register(root, result['manifest'], trial.ACTIVATION)
        package = trial.collect(root, trial.ACTIVATION)
        self.assertTrue(state.resolve(root, package['files'][0]['path']).is_relative_to(root / '最终产品'))
        self.assertEqual(trial.current(root, trial.ACTIVATION)['path'], plan['output'])

    def test_request_activation_is_locked_and_plain_parameter_does_not_authorize_plan(self):
        root, plan = self.project()
        plan['request']['user_instruction'] = 'No activation in the bound request'
        with self.assertRaisesRegex(ValueError, 'locked request'):
            self.build(root, plan)
        plan['request']['user_instruction'] += trial.ACTIVATION
        with self.assertRaisesRegex(ValueError, 'instruction.*evidence'):
            self.build(root, plan)
        components_plan = copy.deepcopy(self.component_plan)
        components_plan['request']['user_instruction'] = 'Invented request ' + trial.ACTIVATION
        components_plan['output'] = 'editable/output/forged-activation.pptx'
        with self.assertRaisesRegex(ValueError, 'instruction.*evidence'):
            trial.components(root, components_plan, trial.ACTIVATION)
        self.assertFalse(state.resolve(root, components_plan['output']).exists())

    def test_existing_visible_answers_cannot_be_hidden_directly_or_by_parent_group(self):
        root, original = self.project()
        for name in ('existing-title', 'math-group'):
            with self.subTest(name=name):
                plan = copy.deepcopy(original)
                obj = next(o for o in self.original_objects if o['name'] == name)
                plan['pages'][0]['units'].append({'unit_id': 'hide-original', 'role': 'answer', 'kind': 'text',
                    'purpose': 'answer', 'initial_visible': False,
                    'targets': [{'shape_id': obj['shape_id'], 'expected_text': obj['text']}]})
                plan['pages'][0]['steps'].append({'step_id': 'show-original', 'pause_reason': 'Synthetic negative case',
                    'actions': [{'unit_id': 'hide-original', 'effect': 'appear', 'trigger': 'on_click'}]})
                with self.assertRaisesRegex(ValueError, 'originally visible'):
                    trial.check(root, plan, self.component_report['manifest'], trial.ACTIVATION)

    def test_registered_scope_and_actual_base_slides_cannot_be_omitted(self):
        root, _ = self.project()
        state.write_json(root / '_state/pages.json', {'pages': [{'page_id': 'P001'}, {'page_id': 'P002'}]})
        plan = copy.deepcopy(self.component_plan)
        plan['output'] = 'editable/output/omitted-page.pptx'
        with self.assertRaisesRegex(ValueError, 'registered page scope'):
            trial.components(root, plan, trial.ACTIVATION)
        root, _ = self.project()
        from pptx import Presentation
        source = state.resolve(root, plan['source_deck'])
        deck = Presentation(source)
        deck.slides.add_slide(deck.slide_layouts[6])
        deck.save(source)
        plan['source_sha256'] = plan['source_versions'][plan['source_deck']] = state.sha256(source)
        register_base(root, plan)
        with self.assertRaisesRegex(ValueError, 'every actual base slide'):
            trial.components(root, plan, trial.ACTIVATION)

    def test_answer_coverage_rejects_omission_mixing_partial_initial_visible_and_notation_split(self):
        root, original = self.project()
        mutations = [
            lambda p: p['pages'][0]['units'].pop(),
            lambda p: p['pages'][0]['units'][1]['targets'].pop(),
            lambda p: p['pages'][0]['units'][0]['targets'][0].update(paragraph=0),
            lambda p: p['pages'][0]['units'][0].update(initial_visible=True),
            lambda p: p['pages'][0]['units'][1].update(purpose='notation_instruction', objective='Write notation'),
            lambda p: p['pages'][0]['units'][1].update(kind='text'),
            lambda p: p['pages'][0]['steps'].clear(),
            lambda p: p['mapping'].update(P001=2),
            lambda p: p['pages'].clear(),
            lambda p: p['pages'][0]['units'][0]['targets'].extend(p['pages'][0]['units'][1]['targets']),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                plan = copy.deepcopy(original)
                mutate(plan)
                with self.assertRaises(ValueError):
                    trial.check(root, plan, self.component_report['manifest'], trial.ACTIVATION)
        self.assertFalse(state.resolve(root, original['output']).exists())

    def test_zero_answers_and_unresolved_blanks_report_truth_without_blocking_current_ppt(self):
        for ambiguous in (False, True):
            root, _ = self.project()
            plan = copy.deepcopy(self.component_plan)
            plan['output'] = 'editable/output/no-answer-components.pptx'
            plan['pages'][0]['items'] = [non_answer('ambiguous' if ambiguous else 'open_blank')]
            comp = trial.components(root, plan, trial.ACTIVATION)
            animated = classroom_plan(comp, plan)
            result = trial.build(root, animated, comp['manifest'], trial.ACTIVATION)
            trial.register(root, result['manifest'], trial.ACTIVATION)
            current = trial.current(root, trial.ACTIVATION)
            self.assertEqual(current['answer_coverage'], [])
            self.assertEqual(current['answer_completeness'], not ambiguous)
            self.assertEqual(len(current['known_issues']), int(ambiguous))
            self.assertFalse(current['course_complete'])

    def test_changed_base_or_component_manifest_or_output_is_rejected(self):
        root, plan = self.project()
        result = self.build(root, plan)
        trial.register(root, result['manifest'], trial.ACTIVATION)
        files = [self.component_plan['source_deck'], self.component_report['manifest'],
                 result['plan']['path'], result['manifest'], result['output']]
        for relative in files:
            path = state.resolve(root, relative)
            original = path.read_bytes()
            with self.subTest(path=relative):
                path.write_bytes(original + b'\n')
                with self.assertRaises(ValueError):
                    trial.current(root, trial.ACTIVATION)
                path.write_bytes(original)

    def test_components_cannot_be_registered_as_legacy_final(self):
        root, _ = self.project()
        result = self.component_report
        state.register_artifact(root, 'editable-pptx', result['output'], metadata={
            'refill_stage': 'click_answers', 'source_versions': result['source_versions'],
            'base_ref': {'path': result['source_deck'], 'sha256': result['source_sha256']},
            'answer_manifest': {'path': result['manifest'], 'sha256': result['manifest_sha256']}})
        with self.assertRaisesRegex(ValueError, 'mode'):
            editable_delivery.current(root)

    def test_optional_static_evidence_mutation_downgrades_without_blocking_collect(self):
        root, plan = self.project()
        result = self.build(root, plan)
        evidence = root / 'inputs/synthetic-static-note.txt'
        evidence.write_text('Synthetic evidence only; this test is not an actual native review', encoding='utf-8')
        check = root / 'inputs/static-check.json'
        state.write_json(check, {'schema_version': 'classroom_trial_check_v1', 'kind': 'static',
            'target': {'path': result['output'], 'sha256': result['output_sha256']},
            'verdict': 'pass', 'method': 'native_static_review', 'note': 'Synthetic receipt validation test only',
            'evidence': [{'path': 'inputs/synthetic-static-note.txt', 'sha256': state.sha256(evidence)}]})
        trial.register(root, result['manifest'], trial.ACTIVATION, checks={
            'static': {'path': 'inputs/static-check.json', 'sha256': state.sha256(check)}})
        selected = trial.current(root, trial.ACTIVATION)
        self.assertEqual(selected['checks']['static']['status'], 'pass')
        self.assertNotIn('inputs/static-check.json', selected['source_versions'])
        self.assertNotIn('inputs/synthetic-static-note.txt', selected['source_versions'])
        evidence.write_text('Changed synthetic note', encoding='utf-8')
        self.assertEqual(trial.current(root, trial.ACTIVATION)['checks']['static']['status'], 'stale')
        self.assertEqual(trial.collect(root, trial.ACTIVATION)['checks']['static']['status'], 'stale')

    def test_malformed_optional_references_are_invalid_without_reading_outside_project(self):
        root, plan = self.project()
        result = self.build(root, plan)
        trial.register(root, result['manifest'], trial.ACTIVATION, checks={
            'review': {'path': '../outside.json', 'sha256': 'untrusted'},
            'static': [], 'playback': None})
        selected = trial.current(root, trial.ACTIVATION)
        self.assertTrue(all(c['status'] == 'invalid' for c in selected['checks'].values()))
        self.assertEqual(trial.collect(root, trial.ACTIVATION)['checks'], selected['checks'])

    def test_optional_review_valid_is_not_pass_and_source_only_is_invalid(self):
        root, plan = self.project()
        result = self.build(root, plan)
        packet = review.prepare(root, {'rubric': 'visual', 'producer_id': 'synthetic-producer',
            'instruction': 'Synthetic validation fixture, not an actual independent review',
            'artifacts': [result['output']], 'sources': ['inputs/answer-basis.json']})
        data = state.read_json(state.resolve(root, packet['packet']))
        report = {'packet_sha256': packet['packet_sha256'], 'source_versions': data['versions'],
                  'reviewer_id': 'synthetic-reviewer', 'method': 'independent_agent',
                  'checks': [{'id': criterion['id'], 'verdict': 'changes_required',
                              'note': 'Synthetic review record needs changes', 'evidence': [result['output']]}
                             for criterion in data['criteria']]}
        review.record(root, packet['packet'], report)
        checks = {'review': {'path': packet['packet'], 'sha256': packet['packet_sha256']}}
        trial.register(root, result['manifest'], trial.ACTIVATION, checks)
        status = trial.current(root, trial.ACTIVATION)['checks']['review']
        self.assertTrue(status['valid'])
        self.assertEqual(status['status'], 'changes_required')
        record_path = state.resolve(root, packet['packet']).parent / 'result.json'
        record_path.write_bytes(record_path.read_bytes() + b'\n')
        self.assertEqual(trial.current(root, trial.ACTIVATION)['checks']['review']['status'], 'stale')
        wrong = review.prepare(root, {'rubric': 'visual', 'producer_id': 'synthetic-producer',
            'instruction': 'Wrong target test', 'artifacts': ['inputs/answer-basis.json'], 'sources': [result['output']]})
        trial.register(root, result['manifest'], trial.ACTIVATION,
                       {'review': {'path': wrong['packet'], 'sha256': wrong['packet_sha256']}})
        self.assertEqual(trial.current(root, trial.ACTIVATION)['checks']['review']['status'], 'invalid')


if __name__ == '__main__':
    unittest.main()
