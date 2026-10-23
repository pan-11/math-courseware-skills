"""A newly refilled base must never silently become the selected answer deck."""
from pathlib import Path
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
from runtime import state, editable_delivery
import courseware
from fixture_factory import layered_deck


class EditableDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs' / ('editable-delivery-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic final selection')
        self.deck = layered_deck(self.root)
        self.path = state.relative_path(self.root, self.deck)
        self.source = 'planning/request.json'
        state.write_json(state.resolve(self.root, self.source), {'user_evidence':'Synthetic explicit student copy'})
        self.versions = {self.source: state.sha256(state.resolve(self.root, self.source))}

    def base(self):
        return state.register_artifact(self.root, 'editable-base-pptx', self.path, metadata={
            'source_versions':self.versions, 'intermediate':True, 'refill_stage':'base'})

    def test_legacy_current_selection_remains_unchanged_without_new_base(self):
        state.register_artifact(self.root, 'editable-pptx', self.path, metadata={'source_versions':self.versions})
        self.assertEqual(editable_delivery.current(self.root)['path'], self.path)

    def test_new_base_blocks_absent_or_legacy_final_and_is_not_collectible(self):
        self.base()
        with self.assertRaisesRegex(ValueError, 'answer|答案'):
            editable_delivery.current(self.root)
        state.register_artifact(self.root, 'editable-pptx', self.path, metadata={'source_versions':self.versions})
        with self.assertRaisesRegex(ValueError, 'answer|答案'):
            editable_delivery.current(self.root)

    def test_explicit_student_override_requires_actual_bound_evidence(self):
        base = self.base()
        override = {'variant':'student_without_answers', 'user_instruction':'Synthetic user explicitly asks student copy',
                    'evidence_ref':{'path':self.source,'sha256':self.versions[self.source]}}
        editable_delivery.register_override(self.root, base, override)
        self.assertEqual(editable_delivery.current(self.root)['path'], base['path'])
        self.deck.write_bytes(self.deck.read_bytes() + b'tampered')
        with self.assertRaises(ValueError): editable_delivery.current(self.root)

    def test_override_cannot_be_inferred_from_boolean_or_unknown_variant(self):
        base = self.base()
        for value in (True, {'variant':'default'}, {'variant':'faithful_restore_only','user_instruction':'Synthetic'}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                editable_delivery.register_override(self.root, base, value)

    def test_selected_complete_rejects_old_delivery_when_new_base_has_no_answers(self):
        from runtime import workflow
        from workflow_fixture import enable_modules, evidence, delivery_manifest
        base = self.base()
        data = enable_modules(self.root, ['editable'], deck=self.path)
        data['stages']['delivery'] = evidence(self.root, 'old-delivery')
        state.write_json(state.resolve(self.root, '_state/workflow.json'), data)
        checked = workflow.check(self.root, 'complete')
        self.assertFalse(checked['allowed'])
        self.assertTrue(any('answer' in issue for issue in checked['issues']))
        editable_delivery.register_override(self.root, base, {
            'variant':'student_without_answers', 'user_instruction':'Synthetic explicit student request',
            'evidence_ref':{'path':self.source, 'sha256':self.versions[self.source]}})
        self.assertFalse(workflow.check(self.root, 'complete')['allowed'])
        data['stages']['delivery'] = evidence(self.root, 'current-delivery',
            sources={base['path']:base['sha256']},
            files={'manifest': delivery_manifest(self.root, 'student-copy', {'pptx': base})})
        state.write_json(state.resolve(self.root, '_state/workflow.json'), data)
        self.assertTrue(workflow.check(self.root, 'complete')['allowed'])

    def test_cli_builds_and_selects_real_answer_file_then_rejects_wrong_stage_pointer(self):
        from test_click_answers import fixture, answer
        from workflow_fixture import enable_modules
        original, plan = fixture()
        root = self.root / 'integrated'
        state.init_project(root, 'Synthetic CLI integration')
        for relative in plan['source_versions']:
            state.resolve(root, relative).write_bytes((original / relative).read_bytes())
        plan['pages'][0]['items'] = [answer()]
        state.write_json(state.resolve(root, '_state/pages.json'), {'pages':[{'page_id':'P001','order':1}]})
        enable_modules(root, ['editable'], deck=plan['source_deck'], route='B')
        path = root / 'planning/answer-plan.json'; state.write_json(path, plan)
        result = courseware.execute(courseware.parser().parse_args([
            'editable-answers','--project',str(root),'--plan',str(path)]))
        selected = editable_delivery.current(root)
        self.assertTrue(result['ready_for_final'])
        self.assertEqual(selected['path'], result['output'])
        self.assertEqual(selected['refill_stage'], 'click_answers')
        self.assertNotEqual(selected['path'], plan['source_deck'])
        with self.assertRaisesRegex(ValueError, 'Selected PPT'):
            editable_delivery.current(root, {'path':plan['source_deck'],'sha256':plan['source_sha256']})
        output = state.resolve(root, selected['path']); output.write_bytes(output.read_bytes()+b'tamper')
        with self.assertRaises(ValueError): editable_delivery.current(root)


if __name__ == '__main__': unittest.main()
