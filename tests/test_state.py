import json
from pathlib import Path
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
try:
    from runtime import state
except ImportError:
    state = None


class StateTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(state, 'state runtime must exist')
        self.root = ROOT / 'tests/runs' / ('state-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic test only', route='openai_image_api')

    def save(self, name, data):
        state.write_json(self.root / '_state' / (name + '.json'), data)

    def test_init_does_not_overwrite_and_paths_stay_inside_project(self):
        path = self.root / '_state/project.json'
        old = path.read_bytes()
        state.init_project(self.root, 'Wrong title')
        self.assertEqual(old, path.read_bytes())
        with self.assertRaises(ValueError):
            state.resolve(self.root, '../outside.json')

    def test_approval_binds_bytes_not_file_existence(self):
        path = self.root / '_state/math.json'
        rec = {'targets': [{'path': '_state/math.json', 'sha256': state.sha256(path)}],
               'user_evidence': 'Synthetic approval fixture, not a real user decision.'}
        state.record_approval(self.root, rec)
        state.record_approval(self.root, rec)
        self.assertEqual(len(state.read_lines(self.root / '_state/decisions.jsonl')), 1)
        self.assertTrue(state.is_approved(self.root, '_state/math.json'))
        self.save('math', {'problems': [{'math_id': 'M001', 'answer': 15}]})
        self.assertFalse(state.is_approved(self.root, '_state/math.json'))

    def test_changed_math_only_invalidates_dependent_pages_and_outputs(self):
        self.save('math', {'revision': 'v001', 'problems': [{'math_id': 'M001', 'groups': 5}]})
        self.save('pages', {'pages': [
            {'page_id': 'P001', 'order': 1, 'math_ids': ['M001']},
            {'page_id': 'P002', 'order': 2, 'math_ids': []}]})
        path = self.root / '_state/math.json'
        change = {'path': '_state/math.json', 'expected_sha256': state.sha256(path),
                  'replacement': {'problems': [{'math_id': 'M001', 'groups': 6}]},
                  'reason': 'Synthetic correction', 'user_evidence': 'Synthetic authorized test'}
        before = path.read_bytes()
        impact = state.impact(self.root, change)
        self.assertIn('P001', impact['affected_ids'])
        self.assertNotIn('P002', impact['affected_ids'])
        self.assertEqual(path.read_bytes(), before)
        result = state.record_change(self.root, change)
        self.assertTrue((self.root / result['previous_version']).exists())
        self.assertIn('P001', state.status(self.root)['stale_targets'])
        self.assertEqual(state.read_json(path)['revision'], 'v002')

    def test_stale_change_rejected_before_writes(self):
        path = self.root / '_state/math.json'
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            state.record_change(self.root, {'path': '_state/math.json', 'expected_sha256': 'wrong',
                'replacement': {}, 'reason': 'test', 'user_evidence': 'test'})
        self.assertEqual(path.read_bytes(), before)

    def test_empty_approval_not_accepted(self):
        with self.assertRaises(ValueError):
            state.record_approval(self.root, {'targets': [], 'user_evidence': ''})

    def test_reorder_does_not_invalidate_unchanged_page_images(self):
        before = {'pages': [{'page_id': 'P001', 'order': 1, 'title': 'A'},
                            {'page_id': 'P002', 'order': 2, 'title': 'B'}]}
        self.save('pages', before)
        replacement = {'pages': [{**before['pages'][0], 'order': 2},
                                 {**before['pages'][1], 'order': 1}]}
        result = state.impact(self.root, {'path': '_state/pages.json', 'replacement': replacement})
        self.assertTrue(result['order_changed'])
        self.assertNotIn('P001', result['affected_ids'])
        self.assertNotIn('P002', result['affected_ids'])

    def test_style_change_invalidates_pages_using_global_style(self):
        self.save('story', {'events': [], 'visual_style': 'blue'})
        self.save('pages', {'pages': [{'page_id': 'P001', 'order': 1}]})
        result = state.impact(self.root, {'path': '_state/story.json',
                                        'replacement': {'events': [], 'visual_style': 'green'}})
        self.assertIn('P001', result['affected_ids'])

    def test_reapproval_after_rejection_is_not_dropped(self):
        target = {'path': '_state/math.json', 'sha256': state.sha256(self.root / '_state/math.json')}
        record = {'targets': [target], 'user_evidence': 'Synthetic approval'}
        state.record_approval(self.root, record)
        state.record_approval(self.root, {**record, 'decision': 'rejected'})
        state.record_approval(self.root, record)
        self.assertTrue(state.is_approved(self.root, target['path']))

    def test_group_reapproval_after_subset_rejection(self):
        targets = [{'path': f'_state/{name}.json', 'sha256': state.sha256(self.root / f'_state/{name}.json')}
                   for name in ('story', 'math')]
        record = {'targets': targets, 'user_evidence': 'Synthetic group approval'}
        state.record_approval(self.root, record)
        state.record_approval(self.root, {**record, 'targets': targets[:1], 'decision': 'rejected'})
        state.record_approval(self.root, record)
        self.assertTrue(state.is_approved(self.root, '_state/story.json'))


if __name__ == '__main__':
    unittest.main()
