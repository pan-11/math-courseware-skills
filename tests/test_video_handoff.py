"""Exercise existing state contracts used by the video Skill; no media generation."""
from pathlib import Path
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
from runtime import checks, state


class VideoHandoffTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs' / ('video-state-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic video handoff only')
        self.story = {'revision': 'v001', 'events': [], 'video_nodes': [
            {'video_id': 'V01', 'dialogue': '请先观察，再想一想。'},
            {'video_id': 'V02', 'dialogue': '现在回顾刚才的方法。'}]}
        state.write_json(self.root / '_state/story.json', self.story)
        self.script = self.root / 'planning/video-handoff.md'
        self.script.write_text('Synthetic script draft; no video exists.\n', encoding='utf-8')
        state.register_artifact(self.root, 'video-V01-script', 'planning/video-handoff.md',
            dependencies=['V01', '_state/story.json'],
            metadata={'source_versions': {'_state/story.json': state.sha256(self.root / '_state/story.json')},
                      'review_status': 'draft'})

    def change_dialogue(self):
        replacement = {**self.story, 'video_nodes': [
            {**self.story['video_nodes'][0], 'dialogue': '请比较两种摆法。'},
            self.story['video_nodes'][1]]}
        return state.record_change(self.root, {
            'path': '_state/story.json',
            'expected_sha256': state.sha256(self.root / '_state/story.json'),
            'replacement': replacement, 'reason': 'Synthetic dialogue correction',
            'user_evidence': 'Synthetic authorized change, not a teacher approval'})

    def test_video_script_can_resume_before_any_pages_or_images(self):
        self.assertTrue(checks.validate(self.root)['ok'])
        self.assertEqual(checks.validate(self.root)['pages'], 0)
        artifact = state.status(self.root)['artifacts']['video-V01-script']
        self.assertEqual(artifact['sha256'], state.sha256(self.script))
        self.assertEqual(artifact['review_status'], 'draft')
        self.assertFalse(state.is_approved(self.root, 'planning/video-handoff.md'))

    def test_node_change_invalidates_its_page_and_script_but_not_unrelated_page(self):
        state.write_json(self.root / '_state/pages.json', {'pages': [
            {'page_id': 'P001', 'order': 1, 'video_ids': ['V01']},
            {'page_id': 'P002', 'order': 2, 'video_ids': ['V02']}]})
        report = self.change_dialogue()
        self.assertIn('V01', report['changed_ids'])
        self.assertIn('P001', report['affected_ids'])
        self.assertIn('video-V01-script', report['affected_ids'])
        self.assertNotIn('P002', report['affected_ids'])
        self.assertTrue((self.root / report['previous_version']).is_file())

    def test_approving_changed_story_does_not_refresh_old_video_artifact(self):
        self.change_dialogue()
        state.record_approval(self.root, {'targets': [{
            'path': '_state/story.json', 'sha256': state.sha256(self.root / '_state/story.json')}],
            'user_evidence': 'Synthetic content approval only'})
        self.assertTrue(state.is_approved(self.root, '_state/story.json'))
        self.assertIn('video-V01-script', state.status(self.root)['stale_targets'])
        artifact = state.status(self.root)['artifacts']['video-V01-script']
        self.assertNotEqual(artifact['source_versions']['_state/story.json'],
                            state.sha256(self.root / '_state/story.json'))


if __name__ == '__main__':
    unittest.main()
