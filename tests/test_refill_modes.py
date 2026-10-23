"""Mode-specific text authority; fixtures are synthetic and retained."""
import copy
import json
from pathlib import Path
import sys
import unittest
import uuid
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
import courseware
from runtime import state, pptx_editor as editor
from fixture_factory import layered_deck
from workflow_fixture import enable_modules


class RefillModeTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs' / ('refill-mode-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic refill mode test')
        self.page = {'page_id': 'P001', 'order': 1,
                     'text_units': [
                         {'unit_id': 'question', 'text': '40/100＝（ ）%', 'visible_at': 'initial'},
                         {'unit_id': 'answer', 'text': '40/100＝40%', 'visible_at': 'R01'}],
                     'reveal_steps': [{'step_id': 'R01', 'unit_ids': ['answer']}],
                     'native_objects': [
                         {'object_id': 'fraction', 'visible_at': 'initial'},
                         {'object_id': 'answer-label', 'visible_at': 'R01'}]}
        self.plan = {'mapping': {'P001': 1}, 'build_scope': 'text-refill',
                     'text_units': [{'page_id': 'P001', 'unit_id': 'question', 'text': '40/100＝（ ）%'}],
                     'required_native_objects': [],
                     'remaining_native_objects': [{'page_id': 'P001', 'object_id': 'fraction',
                                                   'reason': 'Synthetic native fraction pending.'}]}
        self.save_pages()

    def save_pages(self, extra=None):
        state.write_json(self.root / '_state/pages.json', {'pages': [self.page, *(extra or [])]})
        state.record_approval(self.root, {'targets': [{'path': '_state/pages.json',
            'sha256': state.sha256(self.root / '_state/pages.json')}], 'user_evidence': 'Synthetic test only'})

    def teaching(self):
        self.plan['refill_mode'] = 'teaching_reveal'
        self.plan['text_units'].append({'page_id': 'P001', 'unit_id': 'answer', 'text': '40/100＝40%'})
        self.plan['remaining_native_objects'].append({'page_id': 'P001', 'object_id': 'answer-label',
                                                     'reason': 'Synthetic answer label pending.'})

    def test_default_restores_initial_only_and_retains_deferred_source(self):
        before = (self.root / '_state/pages.json').read_bytes()
        result = courseware.validate_editable_authority(self.root, self.plan)
        self.assertEqual(result['page_modes'], {'P001': 'faithful_restore'})
        self.assertEqual(result['pages']['P001']['included_unit_ids'], ['question'])
        self.assertEqual(result['pages']['P001']['deferred_text_units'], [self.page['text_units'][1]])
        self.assertEqual((self.root / '_state/pages.json').read_bytes(), before)

    def test_restore_rejects_added_answer_missing_initial_and_changed_text(self):
        for change in ('add', 'remove', 'change'):
            plan = copy.deepcopy(self.plan)
            if change == 'add':
                plan['text_units'].append({'page_id': 'P001', **self.page['text_units'][1]})
            elif change == 'remove':
                plan['text_units'] = []
            else:
                plan['text_units'][0]['text'] = '44/100＝（ ）%'
            with self.subTest(change=change), self.assertRaises(ValueError):
                courseware.validate_editable_authority(self.root, plan)

    def test_teaching_covers_all_adopted_units_and_native_requirements(self):
        self.teaching()
        result = courseware.validate_editable_authority(self.root, self.plan)
        self.assertEqual(result['pages']['P001']['deferred_text_units'], [])
        self.plan['text_units'].pop()
        with self.assertRaises(ValueError):
            courseware.validate_editable_authority(self.root, self.plan)

    def test_modes_are_validated_and_page_override_is_local(self):
        other = copy.deepcopy(self.page)
        other.update(page_id='P002', order=2)
        self.save_pages([other])
        self.plan['mapping']['P002'] = 2
        self.plan['page_modes'] = {'P002': 'teaching_reveal'}
        self.plan['text_units'] += [{'page_id': 'P002', 'unit_id': u['unit_id'], 'text': u['text']}
                                    for u in other['text_units']]
        self.plan['remaining_native_objects'] += [
            {'page_id': 'P002', 'object_id': x['object_id'], 'reason': 'Synthetic gap'}
            for x in other['native_objects']]
        result = courseware.validate_editable_authority(self.root, self.plan)
        self.assertEqual(result['page_modes'], {'P001': 'faithful_restore', 'P002': 'teaching_reveal'})
        for patch in ({'refill_mode': 'automatic'}, {'page_modes': {'P099': 'teaching_reveal'}},
                      {'page_modes': {'P002': 'automatic'}}, {'page_modes': []}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                courseware.validate_editable_authority(self.root, {**self.plan, **patch})

    def test_answer_role_does_not_hide_visible_reference_text(self):
        self.page['text_units'][0].update(role='answer')
        self.page['text_units'][0].pop('visible_at')
        self.save_pages()
        result = courseware.validate_editable_authority(self.root, self.plan)
        self.assertEqual(result['pages']['P001']['initial_unit_ids'], ['question'])

    def test_reveal_membership_supplies_visibility_but_conflicts_fail(self):
        self.page['text_units'][1].pop('visible_at')
        self.save_pages()
        courseware.validate_editable_authority(self.root, self.plan)
        for visibility in ('initial', 'missing', ''):
            self.page['text_units'][1]['visible_at'] = visibility
            self.save_pages()
            with self.subTest(visibility=visibility), self.assertRaises(ValueError):
                courseware.validate_editable_authority(self.root, self.plan)

    def test_duplicate_or_unknown_reveal_membership_fails(self):
        for member in ('answer', 'missing'):
            self.page['reveal_steps'].append({'step_id': 'R02', 'unit_ids': [member]})
            self.save_pages()
            with self.subTest(member=member), self.assertRaises(ValueError):
                courseware.validate_editable_authority(self.root, self.plan)
            self.page['reveal_steps'].pop()

    def shared_plan(self):
        self.teaching()
        self.plan['text_units'][0] = {'page_id': 'P001', 'unit_id': 'question', 'text': '40/100＝（ ）%',
            'segments': [{'object_id': 'fixed-fraction', 'text': '40/100＝'},
                         {'object_id': 'blank', 'text': '（ ）'},
                         {'object_id': 'fixed-percent', 'text': '%'}]}
        self.plan['text_units'][1] = {'page_id': 'P001', 'unit_id': 'answer', 'text': '40/100＝40%',
            'segments': [{'reuse_object_id': 'fixed-fraction', 'text': '40/100＝'},
                         {'object_id': 'answer-number', 'text': '40'},
                         {'reuse_object_id': 'fixed-percent', 'text': '%'}]}

    def test_shared_initial_objects_do_not_create_duplicate_equations(self):
        self.shared_plan()
        expanded = editor.expand_text_units(self.plan['text_units'])
        self.assertEqual([unit['unit_id'] for unit, _ in expanded],
                         ['fixed-fraction', 'blank', 'fixed-percent', 'answer-number'])
        result = courseware.validate_editable_authority(self.root, self.plan)
        self.assertEqual(len(result['shared_text']), 2)

    def test_shared_object_requires_exact_same_page_text(self):
        self.shared_plan()
        original = copy.deepcopy(self.plan['text_units'])
        for patch in ({'reuse_object_id': 'missing'}, {'text': '44/100＝'},
                      {'reuse_object_id': 'fixed-fraction', 'box': {}}):
            units = copy.deepcopy(original)
            units[1]['segments'][0].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                editor.expand_text_units(units)
        units = copy.deepcopy(original)
        units[1]['page_id'] = 'P002'
        with self.assertRaises(ValueError):
            editor.expand_text_units(units)

    def test_cannot_reuse_another_reveal_object_as_initial_text(self):
        self.shared_plan()
        self.page['text_units'].append({'unit_id': 'second-answer', 'text': '40', 'visible_at': 'R02'})
        self.page['reveal_steps'].append({'step_id': 'R02', 'unit_ids': ['second-answer']})
        self.plan['text_units'].append({'page_id': 'P001', 'unit_id': 'second-answer', 'text': '40',
            'segments': [{'reuse_object_id': 'answer-number', 'text': '40'}]})
        self.save_pages()
        with self.assertRaisesRegex(ValueError, 'initial'):
            courseware.validate_editable_authority(self.root, self.plan)

    def test_teaching_needs_mode_bound_authorization_not_generic_b(self):
        self.teaching()
        self.plan['source_sha256'] = 'synthetic-source'
        data = {'authorized': True, 'scope': 'editable-build', 'source_sha256': 'synthetic-source',
                'page_ids': ['P001'], 'requested_by': 'synthetic-user', 'user_instruction': 'Synthetic instruction',
                'evidence_ref': 'Synthetic test only'}
        def write():
            evidence = self.root / '_state' / ('synthetic-authorization-' + uuid.uuid4().hex + '.json')
            state.write_json(evidence, data)
            self.plan['authorization'] = {'evidence': '_state/' + evidence.name,
                                          'sha256': state.sha256(evidence)}
        write()
        with self.assertRaisesRegex(ValueError, 'mode'):
            editor._review(self.root, self.plan)
        data['refill_modes'] = {'P001': 'teaching_reveal'}
        write()
        editor._review(self.root, self.plan)
        data['refill_modes'] = {'P001': 'faithful_restore'}
        write()
        with self.assertRaisesRegex(ValueError, 'mode'):
            editor._review(self.root, self.plan)


class RefillBuildTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs' / ('refill-build-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic two-mode PPTX test')
        self.inventory = editor.import_deck(self.root, layered_deck(self.root), {'P001': 1})
        self.source = self.root / self.inventory['source_deck']
        self.page = {'page_id': 'P001', 'order': 1, 'text_units': [
            {'unit_id': 'question', 'text': '40/100＝（ ）%', 'visible_at': 'initial'},
            {'unit_id': 'answer', 'text': '40/100＝40%', 'visible_at': 'R01'}],
            'reveal_steps': [{'step_id': 'R01', 'unit_ids': ['answer']}],
            'image': {'path': 'inputs/fixture-image.png',
                      'sha256': state.sha256(self.root / 'inputs/fixture-image.png')}}
        self.save_pages()
        target = next(shape for shape in self.inventory['slides'][0]['shapes'] if shape['name'] == 'existing-title')
        self.plan = {'source_deck': self.inventory['source_deck'], 'source_sha256': editor.sha256(self.source),
            'output': 'editable/output/restore.pptx', 'mapping': {'P001': 1}, 'build_scope': 'text-refill',
            'text_units': [{'page_id': 'P001', 'unit_id': 'question', 'text': '40/100＝（ ）%', 'segments': [
                {'object_id': 'fixed-fraction', 'text': '40/100＝',
                 'target_shape_id': target['shape_id'], 'expected_text': target['text'],
                 'expected_geometry_sha256': target['geometry_sha256'],
                 'box': {'x': 60, 'y': 100, 'width': 250, 'height': 70}},
                {'object_id': 'blank', 'text': '（ ）', 'box': {'x': 310, 'y': 100, 'width': 130, 'height': 70}},
                {'object_id': 'fixed-percent', 'text': '%', 'box': {'x': 440, 'y': 100, 'width': 80, 'height': 70}}]}]}

    def save_pages(self):
        state.write_json(self.root / '_state/pages.json', {'pages': [self.page]})
        state.record_approval(self.root, {'targets': [{'path': '_state/pages.json',
            'sha256': state.sha256(self.root / '_state/pages.json')}], 'user_evidence': 'Synthetic mode fixture only'})
        enable_modules(self.root, deck=self.inventory['source_deck'])

    def authorize(self, modes=None):
        name = 'synthetic-' + Path(self.plan['output']).stem + '-authorization-' + uuid.uuid4().hex + '.json'
        evidence = self.root / '_state' / name
        data = {'authorized': True, 'scope': 'editable-build', 'source_sha256': self.plan['source_sha256'],
                'page_ids': ['P001'], 'requested_by': 'synthetic-user', 'user_instruction': 'Synthetic mode build',
                'evidence_ref': 'Synthetic test only, never real course approval'}
        if modes is not None:
            data['refill_modes'] = modes
        state.write_json(evidence, data)
        self.plan['authorization'] = {'evidence': '_state/' + name, 'sha256': state.sha256(evidence)}

    def build(self):
        plan_path = self.root / '_state' / (Path(self.plan['output']).stem + '-plan.json')
        state.write_json(plan_path, self.plan)
        return courseware.execute(argparse.Namespace(command='editable-build', project=self.root, plan=plan_path))

    def test_explicit_student_override_is_usable_through_actual_cli(self):
        from runtime import editable_delivery
        request = '_state/student-request.json'
        state.write_json(self.root / request, {'user_evidence':'Synthetic explicit no-answer student copy'})
        self.plan['delivery_override'] = {'variant':'student_without_answers',
            'user_instruction':'Synthetic explicit no-answer student copy',
            'evidence_ref':{'path':request,'sha256':state.sha256(self.root / request)}}
        self.authorize()
        result = self.build()
        final = editable_delivery.current(self.root)
        self.assertEqual(final['path'], result['output'])
        self.assertEqual(final['refill_stage'], 'explicit_no_answers')
        self.assertEqual(result['next_step'], 'review-current-delivery')

    def test_actual_cli_builds_both_modes_and_preserves_the_restore_copy(self):
        self.authorize()
        restored = self.build()
        restored_path = self.root / restored['output']
        before = restored_path.read_bytes()
        self.assertEqual(restored['refill']['page_modes']['P001'], 'faithful_restore')
        self.assertEqual(len(restored['refill']['pages']['P001']['deferred_text_units']), 1)
        self.assertEqual(restored['refill']['teaching_animation'], 'not_requested')
        self.assertEqual(len(restored['units']), 3)
        self.plan.update(refill_mode='teaching_reveal', output='editable/output/teaching.pptx')
        self.plan['text_units'].append({'page_id': 'P001', 'unit_id': 'answer', 'text': '40/100＝40%',
            'segments': [{'reuse_object_id': 'fixed-fraction', 'text': '40/100＝'},
                         {'object_id': 'answer-number', 'text': '40', 'font': {'color': 'B45309'},
                          'box': {'x': 345, 'y': 100, 'width': 65, 'height': 70}},
                         {'reuse_object_id': 'fixed-percent', 'text': '%'}]})
        self.authorize({'P001': 'teaching_reveal'})
        teaching = self.build()
        self.assertEqual(len(teaching['units']), 4)
        self.assertEqual(len(teaching['refill']['shared_text']), 2)
        self.assertEqual(teaching['refill']['pages']['P001']['deferred_text_units'], [])
        self.assertEqual(teaching['refill']['teaching_animation'], 'pending')
        shapes = editor.inspect_deck(self.root / teaching['output'])['slides'][0]['shapes']
        texts = [s for s in shapes if s['name'].startswith('mcw:')]
        self.assertEqual([s['text'] for s in texts], ['40/100＝', '（ ）', '%', '40'])
        self.assertTrue(all(f['color'] == 'B45309' for f in texts[-1]['fonts']))
        self.assertEqual(restored_path.read_bytes(), before)
        self.assertEqual(editor.sha256(self.source), self.inventory['source_sha256'])
        self.assertTrue(teaching['media_preserved'] and teaching['non_target_parts_preserved'])
        self.assertTrue(self.build()['idempotent'])
        self.plan['output'] = restored['output']
        self.authorize({'P001': 'teaching_reveal'})
        with self.assertRaisesRegex(ValueError, 'another plan'):
            self.build()
        self.assertEqual(restored_path.read_bytes(), before)

    def test_changed_reference_rejected_before_output(self):
        self.authorize()
        with (self.root / 'inputs/fixture-image.png').open('ab') as stream:
            stream.write(b'synthetic reference change')
        with self.assertRaisesRegex(ValueError, 'reference image changed'):
            self.build()
        self.assertFalse((self.root / self.plan['output']).exists())

    def test_replay_rejects_changed_reference_without_rebinding_old_output(self):
        self.authorize()
        result = self.build()
        output = self.root / result['output']
        saved = {p: p.read_bytes() for p in (output, output.with_suffix('.report.json'))}
        image = self.root / 'inputs/reference-v2.png'
        image.write_bytes((self.root / self.page['image']['path']).read_bytes() + b'new reference')
        self.page['image'] = {'path': 'inputs/reference-v2.png', 'sha256': state.sha256(image)}
        self.save_pages()
        registry = (self.root / '_state/project.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'source|reference'):
            self.build()
        self.assertEqual((self.root / '_state/project.json').read_bytes(), registry)
        for path, content in saved.items():
            self.assertEqual(path.read_bytes(), content)

    def test_unchanged_replay_preserves_registry_and_build_sources(self):
        self.authorize()
        first = self.build()
        registry = (self.root / '_state/project.json').read_bytes()
        repeat = self.build()
        self.assertTrue(repeat['idempotent'])
        self.assertEqual((self.root / '_state/project.json').read_bytes(), registry)
        self.assertEqual(first['source_versions']['_state/pages.json'], state.sha256(self.root / '_state/pages.json'))

    def test_exact_pre_mode_result_is_reused_without_reclassification(self):
        # Build a synthetic legacy-shaped result; no real report or adoption is edited.
        self.page['text_units'][1]['visible_at'] = 'initial'
        self.page['reveal_steps'] = []
        self.save_pages()
        self.plan['text_units'].append({'page_id': 'P001', 'unit_id': 'answer', 'text': '40/100＝40%',
            'box': {'x': 60, 'y': 180, 'width': 500, 'height': 70}})
        self.authorize()
        result = self.build()
        result.pop('refill')
        output = self.root / result['output']
        state.write_json(output.with_suffix('.report.json'), result)
        self.page['text_units'][1]['visible_at'] = 'R01'
        self.page['reveal_steps'] = [{'step_id': 'R01', 'unit_ids': ['answer']}]
        self.save_pages()
        before = output.read_bytes()
        before_report = output.with_suffix('.report.json').read_bytes()
        before_registry = (self.root / '_state/project.json').read_bytes()
        repeat = self.build()
        self.assertTrue(repeat['idempotent'])
        self.assertNotIn('refill', repeat)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(output.with_suffix('.report.json').read_bytes(), before_report)
        self.assertEqual((self.root / '_state/project.json').read_bytes(), before_registry)
        self.plan['output'] = 'editable/output/new-default.pptx'
        self.authorize()
        with self.assertRaisesRegex(ValueError, 'refill mode'):
            self.build()


if __name__ == '__main__':
    unittest.main()
