"""Retained four-folder fixtures; no real lessons, migrations or media services."""
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
from runtime import state, checks, exports, autopilot, review, automation_store


class WorkspaceLayoutTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs/four-folder-layout-20261004/fixtures' / uuid.uuid4().hex

    def initialize(self):
        return state.init_project(self.root, 'Synthetic layout only', layout='four-folders')

    def put(self, path, content='Synthetic file, not production evidence.\n'):
        target = state.resolve(self.root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        return target

    def copy_export_fixture(self):
        from test_exports import fixture
        original = fixture()
        self.initialize()
        for source in original.rglob('*'):
            if not source.is_file() or source.name in ('AGENTS.md', 'HANDOFF.md'):
                continue
            target = state.resolve(self.root, source.relative_to(original))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        return original

    def test_new_course_has_only_four_production_directories(self):
        data = self.initialize()
        self.assertEqual(data['storage_layout'], 'four-folders')
        self.assertEqual({p.name for p in self.root.iterdir() if p.is_dir()},
                         {'01_source', '02_work', '03_final', '04_notes'})
        self.assertTrue((self.root / 'AGENTS.md').is_file())
        self.assertTrue((self.root / 'HANDOFF.md').is_file())
        self.assertTrue((self.root / '02_work/_state/workflow.json').is_file())
        self.assertTrue(checks.validate(self.root)['ok'])

    def test_cli_selects_layout_at_user_supplied_path(self):
        cli = ROOT / 'skills/math-courseware-studio/scripts/courseware.py'
        result = subprocess.run([sys.executable, '-B', str(cli), 'init', '--project',
            str(self.root), '--title', 'Synthetic supplied address', '--layout', 'four-folders'],
            capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / '02_work/_state/project.json').is_file())

    def test_populated_root_keeps_originals_rules_and_handoff(self):
        self.root.mkdir(parents=True)
        (self.root / 'AGENTS.md').write_text('# Existing user rules\n', encoding='utf-8')
        (self.root / 'HANDOFF.md').write_text('Existing handoff\n', encoding='utf-8')
        source = self.root / 'original.pptx'
        source.write_bytes(b'synthetic original bytes')
        self.initialize()
        self.assertEqual(source.read_bytes(), b'synthetic original bytes')
        self.assertTrue((self.root / 'AGENTS.md').read_text(encoding='utf-8').startswith('# Existing user rules\n'))
        self.assertEqual((self.root / 'HANDOFF.md').read_text(encoding='utf-8'), 'Existing handoff\n')
        before = {p.relative_to(self.root).as_posix(): state.sha256(p)
                  for p in self.root.rglob('*') if p.is_file()}
        state.init_project(self.root, 'A different title', layout='four-folders')
        after = {p.relative_to(self.root).as_posix(): state.sha256(p)
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_conflicting_work_area_is_not_overwritten(self):
        self.root.mkdir(parents=True)
        (self.root / 'AGENTS.md').write_text('# Synthetic conflict rules\n', encoding='utf-8')
        work = self.root / '02_work'
        work.mkdir()
        saved = work / 'unfinished.md'
        saved.write_bytes(b'preserve')
        with self.assertRaises(ValueError):
            self.initialize()
        self.assertEqual(saved.read_bytes(), b'preserve')
        self.assertFalse((work / '_state/project.json').exists())

    def test_legacy_project_remains_legacy_on_new_init_request(self):
        state.init_project(self.root, 'Synthetic existing lesson')
        original = (self.root / '_state/project.json').read_bytes()
        self.initialize()
        self.assertEqual((self.root / '_state/project.json').read_bytes(), original)
        self.assertFalse((self.root / '02_work').exists())
        self.assertEqual(state.resolve(self.root, 'planning/a.md'), self.root / 'planning/a.md')

    def test_mixed_initialized_roots_are_rejected(self):
        self.initialize()
        old = self.root / '_state/project.json'
        old.parent.mkdir()
        old.write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError):
            state.load_project(self.root)

    def test_logical_paths_roundtrip_to_four_physical_areas(self):
        self.initialize()
        locations = {'inputs/a.pptx': '01_source/a.pptx',
                     'planning/a.md': '02_work/planning/a.md',
                     'videos/V001/v001/a.txt': '02_work/videos/V001/v001/a.txt',
                     '_state/qa/a.json': '02_work/_state/qa/a.json',
                     'deliveries/delivery-v001/a.md': '02_work/deliveries/delivery-v001/a.md',
                     '03_final/v001/a.pptx': '03_final/v001/a.pptx',
                     '04_notes/v001/note-01/a.png': '04_notes/v001/note-01/a.png',
                     'notes/layout.json': '02_work/notes/layout.json',
                     'AGENTS.md': 'AGENTS.md'}
        for logical, physical in locations.items():
            with self.subTest(logical=logical):
                target = self.root / physical
                self.assertEqual(state.resolve(self.root, logical), target)
                self.assertEqual(state.resolve(self.root, physical), target)
                self.assertEqual(state.relative_path(self.root, target), logical)
        with self.assertRaises(ValueError):
            state.resolve(self.root, '../outside.txt')
        with self.assertRaises(ValueError):
            state.resolve(self.root, self.root.parent / 'outside.txt')

    def test_approval_aliases_and_change_history_share_identity(self):
        self.initialize()
        physical = '02_work/_state/math.json'
        path = self.root / physical
        state.record_approval(self.root, {'user_evidence': 'Synthetic evidence only',
            'targets': [{'path': physical, 'sha256': state.sha256(path)}]})
        self.assertTrue(state.is_approved(self.root, '_state/math.json'))
        self.assertTrue(state.is_approved(self.root, physical))
        old = state.sha256(path)
        report = state.record_change(self.root, {'path': physical, 'expected_sha256': old,
            'replacement': {'problems': [{'math_id': 'M001', 'question': '1+1', 'answer': '2'}]},
            'reason': 'Synthetic change', 'user_evidence': 'Synthetic authorization'})
        self.assertTrue(state.resolve(self.root, report['previous_version']).is_file())
        self.assertFalse(state.is_approved(self.root, '_state/math.json'))

    def test_work_rules_keep_their_own_file_identity(self):
        self.initialize()
        root_rules = state.sha256(self.root / 'AGENTS.md')
        rules = self.put('02_work/AGENTS.md', '# Synthetic work-area rules\n')
        name = state.relative_path(self.root, rules)
        self.assertEqual(state.resolve(self.root, name), rules)
        self.assertNotEqual(name, 'AGENTS.md')
        self.assertEqual(state.sha256(self.root / 'AGENTS.md'), root_rules)

    def test_exports_and_collection_stay_in_work_area(self):
        self.copy_export_fixture()
        slides = exports.export_slides(self.root)
        self.assertTrue(state.resolve(self.root, slides['manifest']).is_relative_to(self.root / '02_work'))
        documents = exports.export_documents(self.root)
        self.assertTrue(state.resolve(self.root, documents['output']).is_relative_to(self.root / '02_work'))
        for result in documents['documents'].values():
            self.assertTrue(state.resolve(self.root, result['manifest']).is_relative_to(self.root / '02_work/documents'))
        result = exports.collect(self.root)
        self.assertTrue(state.resolve(self.root, result['manifest']).is_relative_to(self.root / '02_work/deliveries'))
        self.assertTrue(result['artifacts'])
        for item in result['artifacts'].values():
            self.assertEqual(state.sha256(state.resolve(self.root, item['delivery_path'])), item['sha256'])
        self.assertFalse(list((self.root / '03_final').glob('v*')))

    def test_returned_ppt_uses_editable_work_area(self):
        from fixture_factory import retained_project, layered_deck
        from runtime import pptx_editor
        self.initialize()
        source = layered_deck(retained_project('layout-import'))
        sha = state.sha256(source)
        result = pptx_editor.import_deck(self.root, source, {'P001': 1})
        target = state.resolve(self.root, result['source_deck'])
        self.assertTrue(target.is_relative_to(self.root / '02_work/editable/returned'))
        self.assertEqual(state.sha256(target), sha)
        self.assertEqual(state.sha256(source), sha)

    def test_queue_and_review_use_same_course_without_adoption(self):
        self.initialize()
        flow = state.read_json(state.resolve(self.root, '_state/workflow.json'))
        flow.update(project_mode='full_course', scope_evidence='Synthetic full-course scope',
                    current_task={'mode': 'full_course', 'evidence': 'Synthetic full-course scope'})
        state.write_json(state.resolve(self.root, '_state/workflow.json'), flow)
        source = self.put('planning/source.md')
        task = {'id': 'analysis', 'step': 'analysis', 'kind': 'produce', 'depends_on': [],
                'inputs': ['planning/source.md'], 'outputs': ['report'], 'instruction': 'Synthetic analysis'}
        autopilot.start(self.root, {'activation_evidence': 'Synthetic explicit mode', 'tasks': [task]})
        action = autopilot.next_task(self.root, 'synthetic-maker')
        self.assertEqual(action['action'], 'produce')
        self.put('planning/report.md')
        autopilot.record(self.root, {'task_id': 'analysis', 'claim': action['claim'],
            'status': 'produced', 'artifacts': {'report': '02_work/planning/report.md'}})
        action = autopilot.next_task(self.root, 'synthetic-host')
        self.assertEqual(action['action'], 'review')
        packet_path = state.resolve(self.root, action['packet'])
        self.assertTrue(packet_path.is_relative_to(self.root / '02_work/_state/automation'))
        packet = state.read_json(packet_path)
        report = {'packet_sha256': state.sha256(packet_path), 'reviewer_id': 'synthetic-reader',
            'method': 'independent_agent', 'source_versions': packet['versions'],
            'checks': [{'id': item['id'], 'verdict': 'pass', 'evidence': packet['artifacts'],
                        'note': 'Synthetic mechanics only'} for item in packet['criteria']]}
        review.record(self.root, action['packet'], report)
        self.assertTrue(autopilot.status(self.root)['queue_complete'])
        self.assertFalse(autopilot.status(self.root)['whole_course_complete'])
        self.assertEqual(state.resolve(self.root, '_state/decisions.jsonl').read_bytes(), b'')
        self.assertTrue(source.is_file())

    def test_automation_management_cannot_become_course_artifact_via_alias(self):
        self.initialize()
        for value in ('_state/automation/active.json', '02_work/_state/automation/active.json'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                automation_store.relative(self.root, value)


if __name__ == '__main__':
    unittest.main()
