"""Retained synthetic five-folder courses; never migrates real course files."""
from pathlib import Path
import json
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
from runtime import state, checks, exports, autopilot, review, automation_store


class FiveFolderLayoutTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs/five-folder-layout-20261014/fixtures' / uuid.uuid4().hex

    def initialize(self):
        return state.init_project(self.root, 'Synthetic five-folder course', layout='five-folders')

    def raw(self, relative, content='Synthetic retained file.\n'):
        self.root.mkdir(parents=True, exist_ok=True)
        rules = self.root / 'AGENTS.md'
        if not rules.exists():
            rules.write_text('# Synthetic fixture\nPreserve all existing files; no real lesson.\n', encoding='utf-8')
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        return target

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): state.sha256(p)
                for p in self.root.rglob('*') if p.is_file()}

    def test_cli_creates_five_chinese_folders_at_supplied_root(self):
        cli = ROOT / 'skills/math-courseware-studio/scripts/courseware.py'
        result = subprocess.run([sys.executable, '-B', str(cli), 'init', '--project',
            str(self.root), '--title', 'Synthetic supplied address', '--layout', 'five-folders'],
            capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual({p.name for p in self.root.iterdir() if p.is_dir()},
                         {'原始资料', '中间文件', '最终产品', '笔记素材', '商品详情'})
        self.assertTrue((self.root / '中间文件/_state/workflow.json').is_file())
        self.assertTrue(checks.validate(self.root)['ok'])

    def test_populated_chinese_folders_are_reused_without_overwriting(self):
        for relative in ('原始资料/source.pptx', '中间文件/planning/old.md',
                         '中间文件/videos/returned.mp4', '最终产品/v001/lesson.pptx',
                         '笔记素材/v001/copy.md', '商品详情/v001/main-01.png',
                         'HANDOFF.md', 'original-at-root.pptx'):
            self.raw(relative)
        before = self.snapshot()
        self.initialize()
        for relative, digest in before.items():
            if relative != 'AGENTS.md':
                self.assertEqual(state.sha256(self.root / relative), digest, relative)
        self.assertTrue((self.root / 'AGENTS.md').read_text(encoding='utf-8').startswith('# Synthetic fixture'))
        self.assertEqual(state.storage_layout(self.root), 'five-folders')
        self.assertFalse((self.root / '02_work').exists())

    def test_repeated_init_preserves_records_rules_and_user_files(self):
        self.initialize()
        self.raw('中间文件/planning/continued.md')
        before = self.snapshot()
        state.init_project(self.root, 'Ignored different title', route='builtin', layout='five-folders')
        state.init_project(self.root, 'Old caller without a layout')
        self.assertEqual(self.snapshot(), before)

    def test_existing_five_folder_course_recreates_only_missing_top_folders(self):
        self.raw('中间文件/_state/project.json', json.dumps({'schema_version': '1.0',
            'project_id': self.root.name, 'title': 'Existing synthetic course', 'revision': 'v003',
            'storage_layout': 'five-folders'}, ensure_ascii=False))
        self.raw('原始资料/source.pptx')
        before = self.snapshot()
        self.initialize()
        for name in ('原始资料', '中间文件', '最终产品', '笔记素材', '商品详情'):
            self.assertTrue((self.root / name).is_dir())
        for relative, digest in before.items():
            self.assertEqual(state.sha256(self.root / relative), digest)

    def test_old_layouts_stay_in_place_when_five_folders_requested(self):
        for layout in ('legacy', 'four-folders'):
            with self.subTest(layout=layout):
                self.root = self.root.with_name(uuid.uuid4().hex)
                state.init_project(self.root, 'Existing synthetic course', layout=layout)
                before = self.snapshot()
                self.initialize()
                self.assertEqual(state.storage_layout(self.root), layout)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse((self.root / '中间文件').exists())

    def test_multiple_initialized_layouts_are_rejected_without_writes(self):
        for other in ('_state/project.json', '02_work/_state/project.json'):
            with self.subTest(other=other):
                self.root = self.root.with_name(uuid.uuid4().hex)
                self.initialize()
                self.raw(other, '{}')
                before = self.snapshot()
                with self.assertRaises(ValueError):
                    self.initialize()
                self.assertEqual(self.snapshot(), before)

    def test_partial_internal_state_is_not_reinitialized(self):
        self.raw('中间文件/_state/math.json', '{"keep": true}')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.initialize()
        self.assertEqual(self.snapshot(), before)

    def test_existing_old_work_area_without_state_is_not_ignored(self):
        self.raw('02_work/planning/unfinished.md')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.initialize()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / '中间文件').exists())

    def test_file_directory_collisions_fail_before_writing(self):
        for occupied in ('商品详情', '中间文件/planning', '中间文件/assets/characters'):
            with self.subTest(occupied=occupied):
                self.root = self.root.with_name(uuid.uuid4().hex)
                self.raw(occupied)
                before = self.snapshot()
                with self.assertRaises(ValueError):
                    self.initialize()
                self.assertEqual(self.snapshot(), before)
                self.assertFalse((self.root / '中间文件/_state/project.json').exists())

    def test_logical_physical_and_english_aliases_share_paths(self):
        self.initialize()
        paths = [
            ('inputs/a.pptx', '原始资料/a.pptx', '01_source/a.pptx'),
            ('planning/a.md', '中间文件/planning/a.md', '02_work/planning/a.md'),
            ('_state/math.json', '中间文件/_state/math.json', '02_work/_state/math.json'),
            ('deliveries/v001/a.md', '中间文件/deliveries/v001/a.md', '02_work/deliveries/v001/a.md'),
            ('03_final/v001/a.pptx', '最终产品/v001/a.pptx', '03_final/v001/a.pptx'),
            ('04_notes/v001/copy.md', '笔记素材/v001/copy.md', '04_notes/v001/copy.md'),
            ('product-images/v001/main-01.png', '商品详情/v001/main-01.png', '04_notes/product-images/v001/main-01.png'),
            ('notes/product-images/v001/job.json', '中间文件/notes/product-images/v001/job.json', '02_work/notes/product-images/v001/job.json')]
        for logical, physical, alias in paths:
            with self.subTest(logical=logical):
                target = self.root / physical
                for value in (logical, physical, alias, str(target)):
                    self.assertEqual(state.resolve(self.root, value), target)
                    self.assertEqual(state.relative_path(self.root, value), logical)
        self.assertEqual(state.resolve(self.root, 'AGENTS.md'), self.root / 'AGENTS.md')

    def test_work_rules_are_distinct_and_paths_cannot_escape(self):
        self.initialize()
        for relative in ('中间文件/AGENTS.md', '中间文件/HANDOFF.md', '中间文件/03_final/nested.md'):
            target = self.raw(relative)
            recorded = state.relative_path(self.root, target)
            self.assertEqual(state.resolve(self.root, recorded), target)
            self.assertNotEqual(recorded, target.name)
        for outside in ('../outside.txt', '原始资料/../outside.txt', self.root.parent / 'outside.txt'):
            with self.subTest(outside=outside), self.assertRaises(ValueError):
                state.resolve(self.root, outside)

    def test_approval_and_change_history_keep_logical_identity(self):
        self.initialize()
        physical = '中间文件/_state/math.json'
        path = state.resolve(self.root, physical)
        state.record_approval(self.root, {'user_evidence': 'Synthetic authorization only',
            'targets': [{'path': physical, 'sha256': state.sha256(path)}]})
        self.assertTrue(state.is_approved(self.root, '_state/math.json'))
        self.assertTrue(state.is_approved(self.root, '02_work/_state/math.json'))
        decision = state.read_lines(state.resolve(self.root, '_state/decisions.jsonl'))[-1]
        self.assertEqual(decision['targets'][0]['path'], '_state/math.json')
        report = state.record_change(self.root, {'path': physical, 'expected_sha256': state.sha256(path),
            'replacement': {'problems': [{'math_id': 'M001', 'question': '1+1', 'answer': '2'}]},
            'reason': 'Synthetic update', 'user_evidence': 'Synthetic scope'})
        self.assertTrue(state.resolve(self.root, report['previous_version']).is_file())
        self.assertFalse(state.is_approved(self.root, '_state/math.json'))
        self.assertEqual(report['path'], '_state/math.json')

    def test_artifacts_and_jobs_use_canonical_record_paths(self):
        self.initialize()
        self.raw('最终产品/v001/lesson.pptx')
        item = state.register_artifact(self.root, 'synthetic', '最终产品/v001/lesson.pptx',
                                      ['中间文件/_state/math.json'])
        self.assertEqual(item['path'], '03_final/v001/lesson.pptx')
        self.assertEqual(item['dependencies'], ['_state/math.json'])
        self.raw('中间文件/_state/jobs/job-test/job.json', '{"status":"prepared"}')
        self.assertEqual(state.status(self.root)['jobs'][0]['path'], '_state/jobs/job-test/job.json')

    def test_exports_and_collection_use_chinese_work_area(self):
        from test_exports import fixture
        original = fixture()
        self.initialize()
        for source in original.rglob('*'):
            if not source.is_file() or source.name in ('AGENTS.md', 'HANDOFF.md'):
                continue
            target = state.resolve(self.root, source.relative_to(original))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        results = [exports.export_slides(self.root), exports.export_documents(self.root), exports.collect(self.root)]
        for result in results:
            name = result.get('manifest') or result['output']
            self.assertTrue(state.resolve(self.root, name).is_relative_to(self.root / '中间文件'))
        for item in results[-1]['artifacts'].values():
            self.assertEqual(state.sha256(state.resolve(self.root, item['delivery_path'])), item['sha256'])
        self.assertFalse(list((self.root / '最终产品').glob('v*')))

    def test_returned_editable_deck_preserves_original(self):
        from fixture_factory import retained_project, layered_deck
        from runtime import pptx_editor
        self.initialize()
        source = layered_deck(retained_project('five-layout-import'))
        digest = state.sha256(source)
        result = pptx_editor.import_deck(self.root, source, {'P001': 1})
        target = state.resolve(self.root, result['source_deck'])
        self.assertTrue(target.is_relative_to(self.root / '中间文件/editable/returned'))
        self.assertEqual(state.sha256(source), digest)
        self.assertEqual(state.sha256(target), digest)

    def test_queue_and_review_use_chinese_paths_without_adoption(self):
        self.initialize()
        from runtime import workflow
        path = state.resolve(self.root, '_state/workflow.json')
        flow = workflow.load(self.root)
        flow.update(project_mode='full_course', scope_evidence='Synthetic scope',
                    current_task={'mode': 'full_course', 'evidence': 'Synthetic scope'})
        state.write_json(path, flow)
        self.raw('中间文件/planning/source.md')
        task = {'id': 'analysis', 'step': 'analysis', 'kind': 'produce', 'depends_on': [],
                'inputs': ['planning/source.md'], 'outputs': ['report'], 'instruction': 'Synthetic task'}
        autopilot.start(self.root, {'activation_evidence': 'Synthetic explicit mode', 'tasks': [task]})
        action = autopilot.next_task(self.root, 'synthetic-maker')
        self.assertEqual(action['action'], 'produce')
        self.raw('中间文件/planning/report.md')
        autopilot.record(self.root, {'task_id': 'analysis', 'claim': action['claim'],
            'status': 'produced', 'artifacts': {'report': '中间文件/planning/report.md'}})
        action = autopilot.next_task(self.root, 'synthetic-host')
        packet_path = state.resolve(self.root, action['packet'])
        self.assertTrue(packet_path.is_relative_to(self.root / '中间文件/_state/automation'))
        packet = state.read_json(packet_path)
        report = {'packet_sha256': state.sha256(packet_path), 'reviewer_id': 'synthetic-reader',
            'method': 'independent_agent', 'source_versions': packet['versions'],
            'checks': [{'id': item['id'], 'verdict': 'pass', 'evidence': packet['artifacts'],
                        'note': 'Synthetic mechanics only'} for item in packet['criteria']]}
        review.record(self.root, action['packet'], report)
        self.assertTrue(autopilot.status(self.root)['queue_complete'])
        self.assertFalse(autopilot.status(self.root)['whole_course_complete'])
        self.assertEqual(state.resolve(self.root, '_state/decisions.jsonl').read_bytes(), b'')
        for value in ('_state/automation/active.json', '02_work/_state/automation/active.json',
                      '中间文件/_state/automation/active.json'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                automation_store.relative(self.root, value)


if __name__ == '__main__':
    unittest.main()
