"""V1 must check whole-page teaching intent, not only newly inserted answers."""
import copy
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/math-courseware-studio/scripts'))
from runtime import classroom_trial as trial, state
import test_classroom_trial as fixtures


class TeachingContractIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ClassroomTrialIntegrationTests.setUpClass()

    def case(self):
        helper = fixtures.ClassroomTrialIntegrationTests()
        root, plan = helper.project()
        return root, plan, helper.component_report['manifest']

    def test_answer_only_plan_without_full_teaching_contract_is_rejected(self):
        root, plan, manifest = self.case()
        plan.pop('teaching_contract', None)
        with self.assertRaisesRegex(ValueError, 'teaching.contract'):
            trial.check(root, plan, manifest, trial.ACTIVATION)

    def mutate_contract(self, root, plan, change):
        reference = plan['teaching_contract']
        value = state.read_json(state.resolve(root, reference['path']))
        change(value)
        state.write_json(state.resolve(root, reference['path']), value)
        reference['sha256'] = state.sha256(state.resolve(root, reference['path']))
        plan['source_versions'][reference['path']] = reference['sha256']

    def test_unaccounted_source_object_cannot_silently_stay_on_first_screen(self):
        root, plan, manifest = self.case()
        self.mutate_contract(root, plan, lambda c: c['pages'][0]['retained_objects'].pop())
        with self.assertRaisesRegex(ValueError, 'coverage missing'):
            trial.check(root, plan, manifest, trial.ACTIVATION)

    def test_wrong_order_and_bundled_clicks_do_not_match_contract(self):
        for mode in ('reverse', 'bundle'):
            root, plan, manifest = self.case()
            if mode == 'reverse':
                plan['pages'][0]['steps'].reverse()
            else:
                steps = plan['pages'][0]['steps']
                action = steps.pop()['actions'][0]
                action['trigger'] = 'with_previous'
                steps[0]['actions'].append(action)
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'click contents/order/grouping'):
                trial.check(root, plan, manifest, trial.ACTIVATION)

    def test_original_visible_content_can_follow_target_hidden_state(self):
        root, plan, manifest = self.case()
        obj = next(o for o in fixtures.ClassroomTrialIntegrationTests.original_objects if o['name'] == 'existing-title')
        page = plan['pages'][0]
        page['units'] = [u for u in page['units'] if not any(t['shape_id'] == obj['shape_id'] for t in u['targets'])]
        page['units'].append({'unit_id': 'later-explanation', 'role': 'explanation', 'kind': 'text',
            'purpose': 'explanation', 'initial_visible': False,
            'targets': [{'shape_id': obj['shape_id'], 'expected_text': obj['text']}]})
        page['steps'].insert(0, {'step_id': 'observe', 'pause_reason': 'Observe before revealing the original explanation',
            'actions': [{'unit_id': 'later-explanation', 'effect': 'fade', 'trigger': 'on_click'}]})
        fixtures.bind_teaching_contract(root, plan, 'revised-target.json')
        result = trial.check(root, plan, manifest, trial.ACTIVATION)
        self.assertTrue(result['teaching_coverage']['complete_inventory'])
        self.assertEqual(result['teaching_coverage']['pages'][0]['expected_clicks'], 3)
        self.assertEqual(result['teaching_coverage']['native_playback'], 'unverified')

    def test_plan_cannot_change_declared_initial_display(self):
        root, plan, manifest = self.case()
        self.mutate_contract(root, plan, lambda c: c['pages'][0]['managed_units'][0].update(initial_visible=True))
        with self.assertRaisesRegex(ValueError, 'initial visibility differs'):
            trial.check(root, plan, manifest, trial.ACTIVATION)

    def test_new_trial_requires_native_phase_for_automatic_followup(self):
        root, plan, manifest = self.case()
        steps = plan['pages'][0]['steps']
        followup = steps.pop()['actions'][0]
        followup['trigger'] = 'after_previous'
        steps[0]['actions'].append(followup)
        fixtures.bind_teaching_contract(root, plan, 'automatic-flat-contract.json')
        with self.assertRaisesRegex(ValueError, 'phase_start_ms'):
            trial.check(root, plan, manifest, trial.ACTIVATION)
        followup['phase_start_ms'] = 1
        fixtures.bind_teaching_contract(root, plan, 'automatic-native-contract.json')
        result = trial.check(root, plan, manifest, trial.ACTIVATION)
        self.assertEqual(result['teaching_coverage']['pages'][0]['expected_clicks'], 1)

    def test_zero_click_teaching_is_not_a_generic_escape(self):
        root, plan, manifest = self.case()
        plan['pages'][0]['units'] = []
        plan['pages'][0]['steps'] = []
        plan['pages'][0]['static_reason'] = 'Deliberately wrong blanket reason'
        fixtures.bind_teaching_contract(root, plan, 'static-target.json')
        self.mutate_contract(root, plan, lambda c: c['pages'][0].update(page_type='teaching'))
        from runtime import classroom_teaching_contract
        inventory = trial.classroom_animation.inspect(state.resolve(root, plan['source_deck']))
        objects = {p['slide_index']: {o['shape_id']: o for o in p['objects']} for p in inventory['slides']}
        with self.assertRaisesRegex(ValueError, 'zero-click teaching'):
            classroom_teaching_contract.validate(root, plan, objects)


class RetainedAnimationCoverageTests(unittest.TestCase):
    def test_partial_group_or_paragraph_animation_cannot_retain_the_entire_object(self):
        from runtime import classroom_timing, pptx_editor as editor
        for kind in ('group', 'paragraph'):
            with self.subTest(kind=kind):
                root, component = fixtures.fixture()
                fixtures.initialize(root)
                source = state.resolve(root, component['source_deck'])
                parts = editor._parts(source)
                part = editor._slides(parts)[0]
                slide = editor.ET.fromstring(parts[part])
                shapes = {editor._identity(n).get('name'): n for n in editor._shape_nodes(slide)}
                animated = shapes['math-block-1' if kind == 'group' else 'existing-title']
                retained = shapes['math-group' if kind == 'group' else 'existing-title']
                extra = shapes['math-block-2' if kind == 'group' else 'existing-title']
                body = extra.find('p:txBody', editor.NS)
                para = editor.ET.SubElement(body, '{' + editor.NS['a'] + '}p')
                run = editor.ET.SubElement(para, '{' + editor.NS['a'] + '}r')
                editor.ET.SubElement(run, '{' + editor.NS['a'] + '}t').text = 'This explanation has no existing animation'
                animated_target = {'shape_id': int(editor._identity(animated).get('id')), 'expected_text': editor._text(animated)}
                if kind == 'paragraph':
                    animated_target['paragraph'] = 0
                old_unit = {'unit_id': 'old', 'initial_visible': False, 'targets': [animated_target]}
                slide.append(classroom_timing.compile_timing(None, [{'step_id': 'old', 'pause_reason': 'Existing source click',
                    'actions': [{'unit_id': 'old', 'effect': 'appear', 'trigger': 'on_click'}]}], {'old': old_unit}))
                parts[part] = editor.ET.tostring(slide)
                with zipfile.ZipFile(source, 'w') as archive:
                    for name, value in parts.items():
                        archive.writestr(name, value)
                component['source_sha256'] = component['source_versions'][component['source_deck']] = state.sha256(source)
                instruction = 'Synthetic explicit ' + trial.ACTIVATION + ' retained coverage test'
                authority = state.resolve(root, component['request']['evidence_ref']['path'])
                state.write_json(authority, {'user_instruction': instruction})
                component['request']['user_instruction'] = instruction
                component['request']['evidence_ref']['sha256'] = state.sha256(authority)
                component['source_versions'][component['request']['evidence_ref']['path']] = state.sha256(authority)
                component['output'] = 'editable/output/components.pptx'
                fixtures.register_base(root, component)
                report = trial.components(root, component, trial.ACTIVATION)
                plan = fixtures.classroom_plan(report, component, root)
                page = plan['pages'][0]
                objects = {o['shape_id']: o for o in trial.classroom_animation.inspect(
                    state.resolve(root, report['output']))['slides'][0]['objects']}
                retained_id = int(editor._identity(retained).get('id'))
                retained_target = {'shape_id': retained_id, 'expected_text': objects[retained_id]['text']}
                overlaps = lambda target: trial.classroom_animation._overlap(retained_target, target, objects)
                page['units'] = [u for u in page['units'] if not any(overlaps(t) for t in u['targets'])]
                page['existing_policy'] = 'append_after_existing'
                page['existing_reason'] = 'Preserve source timing while testing an incorrectly broad retention declaration'
                ref = plan['teaching_contract']
                contract = state.read_json(state.resolve(root, ref['path']))
                target = contract['pages'][0]
                target['managed_units'] = [{k: copy.deepcopy(u[k]) for k in ('unit_id', 'initial_visible', 'targets')}
                                           for u in page['units']]
                target['retained_objects'] = [r for r in target['retained_objects']
                                              if not any(overlaps(t) for t in r['targets'])]
                target['retained_objects'].append({'category': 'existing_animation',
                    'reason': 'Invalid claim: one animated part means the entire object is animated', 'targets': [retained_target]})
                state.write_json(state.resolve(root, ref['path']), contract)
                ref['sha256'] = state.sha256(state.resolve(root, ref['path']))
                plan['source_versions'][ref['path']] = ref['sha256']
                with self.assertRaisesRegex(ValueError, 'actual animated object'):
                    trial.check(root, plan, report['manifest'], trial.ACTIVATION)


if __name__ == '__main__':
    unittest.main()
