"""Startup settings and real media authorization boundaries; synthetic retained data only."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
import courseware
from runtime import state, autopilot, prompts, image_api, workflow
from workflow_fixture import enable_modules
from test_image_api import Transport


class StartupPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs/autopilot-abcd1-20261004/fixtures' / ('a-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic startup preferences')
        enable_modules(self.root, ['analyze', 'plan', 'editable'])
        self.source = 'planning/source.md'
        (self.root / self.source).write_text('Synthetic 2 + 3 = 5.', encoding='utf-8')

    def task(self, name='analysis', step='analysis', **extra):
        return dict(id=name, step=step, inputs=[self.source], outputs=['report'],
                    instruction='Synthetic authorized work', **extra)

    def image(self, route='openai_image_api', **changes):
        auth = dict(scope='run', purposes=['test'], paid_generation=True,
                    include_rework=False, scope_evidence='Synthetic explicit run test generation consent')
        auth.update(changes)
        return {'route': route, 'evidence': 'Synthetic actual route choice', 'authorization': auth}

    def start(self, settings=None, tasks=None):
        self.plan = {'activation_evidence': 'Synthetic explicit automatic request',
                     'tasks': tasks or [self.task()]}
        if settings is not None: self.plan['preferences'] = settings
        return autopilot.start(self.root, self.plan)

    def configure(self, settings):
        self.assertTrue(callable(getattr(autopilot, 'configure', None)), 'run-configure implementation required')
        return autopilot.configure(self.root, settings)

    def prepare(self, target='TEST001', version='v001'):
        return prompts.prepare(self.root, {'tasks': [{'purpose': 'test', 'target_id': target,
            'version': version, 'prompt': 'Synthetic image; no network'}]})

    def run_batch(self, batch, resume=False):
        transport = Transport()
        with patch.object(image_api, 'HttpTransport', lambda key: transport):
            result = image_api.run_batch(self.root, batch, 'synthetic-key', resume=resume)
        return result, transport

    def test_start_records_preferences_and_evidence_without_inventing_authorization(self):
        result = self.start({'video': {'platform': 'Synthetic', 'evidence': 'Actual synthetic choice'}})
        self.assertIn('preferences', result)
        self.assertEqual(result['preferences']['video']['platform'], 'Synthetic')
        self.assertEqual(result['preferences']['editable']['route'], 'A')
        self.assertNotIn('authorization', result['preferences'].get('image', {}))
        self.assertIn('video.model', result['missing_preferences'])
        self.assertIn('editable.entry', result['missing_preferences'])

    def test_same_start_and_resume_preserve_configured_values(self):
        first = self.start()
        configured = self.configure({'editable': {'route': 'B', 'entry': 'returned', 'evidence': 'Synthetic clear B return'}})
        autopilot.control(self.root, mode='manual', evidence='Synthetic manual')
        self.assertTrue(workflow.check(self.root, 'editable-handoff', route='B')['allowed'])
        again = autopilot.start(self.root, self.plan)
        self.assertEqual(again['run_id'], first['run_id'])
        self.assertEqual(again['preferences'], configured['preferences'])
        self.assertEqual(again['mode'], 'manual')

    def test_partial_updates_retain_omitted_values_and_revisions(self):
        self.start({'image': self.image()})
        first = self.configure({'video': {'platform': 'Synthetic', 'model': 'm1', 'sound': 'silent', 'evidence': 'Synthetic all video settings'}})
        second = self.configure({'video': {'model': 'm2', 'evidence': 'Synthetic model change'}})
        self.assertEqual(second['preferences']['video']['platform'], 'Synthetic')
        self.assertEqual(second['preferences']['video']['sound'], 'silent')
        self.assertEqual(second['preferences']['image'], first['preferences']['image'])
        folder = state.resolve(self.root, '_state/automation/runs/' + first['run_id'])
        saved = state.read_json(folder / ('revision-%05d.json' % first['revision']))
        self.assertEqual(saved['preferences']['video']['model'], 'm1')

    def test_invalid_updates_leave_run_bytes_unchanged(self):
        result = self.start()
        path = state.resolve(self.root, '_state/automation/runs/' + result['run_id'] + '/run.json')
        invalid = [{}, {'unknown': {}}, {'video': None}, {'image': {'route': 'builtin'}},
                   {'editable': {'route': 'C', 'evidence': 'Synthetic'}},
                   {'editable': {'entry': None, 'evidence': 'Synthetic'}},
                   {'video': {'sound': '  ', 'evidence': 'Synthetic'}},
                   {'video': {'model': 'm', 'evidence': None}},
                   {'image': self.image(paid_generation='true')},
                   {'image': self.image(purposes=['extra'])},
                   {'image': self.image(scope='all-courses')},
                   {'image': self.image(scope_evidence='  ')}]
        for value in invalid:
            with self.subTest(value=value):
                before = path.read_bytes()
                with self.assertRaises(ValueError): self.configure(value)
                self.assertEqual(before, path.read_bytes())

    def test_missing_preferences_block_only_actual_dependent_tasks(self):
        self.start(tasks=[self.task('cover', 'cover'), self.task()])
        action = autopilot.next_task(self.root, 'synthetic-host')
        self.assertEqual(action['task']['id'], 'analysis')
        self.assertIn('preferences', action)
        waiting = autopilot.status(self.root)['tasks'][0]
        self.assertTrue(any('image' in issue for issue in waiting.get('issues', [])))

    def test_video_and_editable_requirements_do_not_block_text_preparation(self):
        self.start(tasks=[self.task('dependent', requires_preferences=['video']), self.task()])
        self.assertEqual(autopilot.next_task(self.root, 'synthetic-host')['task']['id'], 'analysis')
        data = autopilot.status(self.root)
        self.assertTrue(any('video' in issue for issue in data['tasks'][0]['issues']))

    def test_explicit_image_requests_cannot_be_hidden_by_empty_requirements(self):
        self.start(tasks=[self.task('image', requires_preferences=[],
            image_requests=[{'purpose': 'test', 'target_id': 'TEST001', 'version': 'v001'}]), self.task()])
        self.assertEqual(autopilot.next_task(self.root, 'synthetic-host')['task']['id'], 'analysis')

    def test_human_operation_respects_declared_preferences_without_blocking_other_work(self):
        self.start(tasks=[self.task('external', kind='human', requires_preferences=['video']), self.task()])
        action = autopilot.next_task(self.root, 'synthetic-host')
        self.assertEqual(action['task']['id'], 'analysis')
        self.assertEqual(action['human_tasks'], [])

    def test_unrelated_configuration_retains_and_reports_existing_route_conflict(self):
        self.start({'image': self.image('builtin', paid_generation=False)})
        project = state.load_project(self.root)
        project['image_route'] = 'openai_image_api'
        state.write_json(self.root / '_state/project.json', project)
        result = self.configure({'video': {'sound': 'silent', 'evidence': 'Synthetic known sound'}})
        self.assertTrue(result['preference_issues'])
        self.assertEqual(autopilot.next_task(self.root, 'synthetic-host')['action'], 'produce')

    def test_current_project_choice_reused_and_another_course_isolated(self):
        project = state.load_project(self.root)
        project['image_route'] = 'builtin'
        state.write_json(self.root / '_state/project.json', project)
        result = self.start()
        self.assertIn('preferences', result)
        self.assertEqual(result['preferences']['image']['route'], 'builtin')
        other = self.root.parent / ('a-isolated-' + uuid.uuid4().hex)
        state.init_project(other, 'Synthetic isolated course')
        before = sorted(str(p) for p in other.rglob('*'))
        self.assertIsNone(autopilot.status(other)['run_id'])
        self.assertEqual(before, sorted(str(p) for p in other.rglob('*')))
        with self.assertRaises(ValueError): autopilot.configure(other, {'image': self.image()})

    def test_canonical_conflict_reported_then_explicitly_reconciled(self):
        self.start({'image': self.image('builtin', paid_generation=False)})
        project = state.load_project(self.root)
        project['image_route'] = 'openai_image_api'
        state.write_json(self.root / '_state/project.json', project)
        result = autopilot.status(self.root)
        self.assertTrue(result.get('preference_issues'), 'Conflicting canonical choice must be reported')
        with self.assertRaisesRegex(ValueError, 'conflict'): self.prepare()
        self.configure({'image': {'route': 'openai_image_api', 'evidence': 'Synthetic explicit new API choice'}})
        self.assertEqual(self.prepare()['route'], 'openai_image_api')
        self.assertFalse(autopilot.status(self.root)['preference_issues'])

    def test_newer_canonical_evidence_detected_even_when_route_returns_to_original_value(self):
        self.start({'editable': {'route': 'B', 'entry': 'returned', 'evidence': 'Synthetic actual B choice'}})
        autopilot.control(self.root, mode='manual', evidence='Synthetic manual continuation')
        path = self.root / '_state/workflow.json'
        canonical = state.read_json(path)
        canonical['route_choice']['user_evidence'] = 'Synthetic later actual switch back to A'
        state.write_json(path, canonical)
        autopilot.control(self.root, mode='automatic', evidence='Synthetic return to the retained run')
        self.assertTrue(autopilot.status(self.root)['preference_issues'])
        check = workflow.check(self.root, 'editable-handoff', route='B')
        self.assertFalse(check['allowed'])
        self.assertTrue(any('conflict' in issue for issue in check['issues']))
        with self.assertRaisesRegex(ValueError, 'conflict'):
            self.configure({'editable': {'entry': 'returned', 'evidence': 'Synthetic entry confirmation only'}})
        self.configure({'editable': {'route': 'B', 'evidence': 'Synthetic newest explicit reaffirm B'}})
        self.assertFalse(autopilot.status(self.root)['preference_issues'])
        self.assertTrue(workflow.check(self.root, 'editable-handoff', route='B')['allowed'])

    def test_unchanged_canonical_evidence_and_unrelated_metadata_do_not_create_conflict(self):
        self.start({'editable': {'route': 'B', 'entry': 'returned', 'evidence': 'Synthetic actual B choice'}})
        path = self.root / '_state/workflow.json'
        canonical = state.read_json(path)
        canonical['current_task']['focus'] = 'Synthetic ordinary progress note'
        state.write_json(path, canonical)
        self.assertFalse(autopilot.status(self.root)['preference_issues'])
        self.assertTrue(workflow.check(self.root, 'editable-handoff', route='B')['allowed'])

    def test_prepare_and_api_use_run_route_and_applicable_consent(self):
        self.start({'image': self.image()})
        batch = self.prepare()
        self.assertEqual(batch['route'], 'openai_image_api')
        self.assertFalse(batch['authorization_evidence'])
        result, transport = self.run_batch(batch)
        self.assertEqual(result['results'][0]['status'], 'downloaded')
        self.assertEqual(len([p for p in transport.posts if p[0].endswith('completions')]), 1)

    def test_cli_accepts_applicable_run_consent_before_reading_key(self):
        self.start({'image': self.image()})
        batch = self.prepare()
        args = courseware.parser().parse_args(['image-run', '--project', str(self.root), '--batch', str(self.root / batch['path'])])
        transport = Transport()
        with patch.object(image_api, 'read_key', return_value='synthetic-key'), patch.object(image_api, 'HttpTransport', lambda key: transport):
            self.assertEqual(courseware.execute(args)['results'][0]['status'], 'downloaded')

    def test_run_configure_cli_is_noninteractive_partial_update(self):
        self.start()
        path = self.root / 'planning/preferences.json'
        state.write_json(path, {'editable': {'entry': 'returned', 'evidence': 'Synthetic actual returned entry'}})
        self.assertIn('run-configure', courseware.parser().format_help())
        args = courseware.parser().parse_args(['run-configure', '--project', str(self.root), '--settings', str(path)])
        self.assertEqual(courseware.execute(args)['preferences']['editable']['entry'], 'returned')

    def test_route_choice_and_broad_sentence_do_not_authorize_fee_or_extra_purpose(self):
        self.start({'image': self.image(paid_generation=False, purposes=['asset'])})
        batch = self.prepare()
        with self.assertRaises(ValueError): self.run_batch(batch)
        self.configure({'image': {'authorization': {'purposes': ['test'], 'scope_evidence': 'Synthetic tests only; no paid consent'}}})
        with self.assertRaisesRegex(ValueError, 'paid'): self.run_batch(batch)
        self.assertEqual(state.read_json(self.root / batch['jobs'][0])['status'], 'pending')

    def test_scope_targets_and_rework_are_not_implicitly_authorized(self):
        self.start({'image': self.image(scope='targets', targets=[{'target_id': 'ONLY', 'version': 'v001'}])})
        with self.assertRaisesRegex(ValueError, 'target'): self.run_batch(self.prepare('EXTRA'))
        self.run_batch(self.prepare('ONLY'))
        self.configure({'image': {'authorization': {'scope': 'run', 'scope_evidence': 'Synthetic all first production tests'}}})
        with self.assertRaisesRegex(ValueError, 'rework'): self.run_batch(self.prepare('ONLY', 'v002'))
        self.configure({'image': {'authorization': {'include_rework': True, 'scope_evidence': 'Synthetic explicit test rework and paid consent retained'}}})
        result, _ = self.run_batch(self.prepare('ONLY', 'v002'))
        self.assertEqual(result['results'][0]['status'], 'downloaded')

    def test_normal_focus_progress_preserves_consent_but_new_modules_do_not(self):
        self.start({'image': self.image()})
        batch = self.prepare()
        path = self.root / '_state/workflow.json'
        data = state.read_json(path)
        data['current_task']['focus'] = 'Next ordinary stage'
        state.write_json(path, data)
        self.run_batch(batch)
        data['current_task']['modules'].append('documents')
        state.write_json(path, data)
        with self.assertRaisesRegex(ValueError, 'scope'): self.run_batch(self.prepare('EXTRA'))

    def test_new_route_does_not_rewrite_old_job_and_resume_does_not_submit(self):
        self.start({'image': self.image()})
        batch = self.prepare()
        path = self.root / batch['jobs'][0]
        job = state.read_json(path)
        job.update(status='running', task_id='provider-test-id')
        state.write_json(path, job)
        self.configure({'image': {'route': 'builtin', 'evidence': 'Synthetic actual new route'}})
        result, transport = self.run_batch(batch, resume=True)
        self.assertEqual(result['results'][0]['status'], 'downloaded')
        self.assertEqual(state.read_json(path)['route'], 'openai_image_api')
        self.assertEqual([p[0] for p in transport.posts], ['/v1/draw/result'])

    def test_direct_api_job_cannot_bypass_run_authorization(self):
        self.start({'image': self.image(paid_generation=False)})
        batch = self.prepare()
        transport = Transport()
        with self.assertRaisesRegex(ValueError, 'paid'):
            image_api.run_job(self.root, batch['jobs'][0], transport, timeout=1, poll_interval=0)
        self.assertEqual(transport.posts, [])

    def test_no_run_manual_resume_retains_existing_batch_evidence_requirement(self):
        project = state.load_project(self.root)
        project['image_route'] = 'openai_image_api'
        state.write_json(self.root / '_state/project.json', project)
        batch = self.prepare()
        with self.assertRaisesRegex(ValueError, 'authorization'):
            self.run_batch(batch, resume=True)
        self.assertIsNone(autopilot.status(self.root)['run_id'])

    def test_manual_prepare_reused_after_start_preserves_job_and_uses_current_consent(self):
        project = state.load_project(self.root)
        project['image_route'] = 'openai_image_api'
        state.write_json(self.root / '_state/project.json', project)
        manual = self.prepare()
        path = self.root / manual['jobs'][0]
        before = path.read_bytes()
        self.assertEqual(self.prepare(), manual)
        self.start({'image': self.image()})
        reused = self.prepare()
        self.assertEqual(reused['jobs'], manual['jobs'])
        self.assertEqual(path.read_bytes(), before)
        result, transport = self.run_batch(reused)
        self.assertEqual(result['results'][0]['status'], 'downloaded')
        self.assertEqual(len([p for p in transport.posts if p[0].endswith('completions')]), 1)
        self.assertEqual(len(list((self.root / '_state/jobs').glob('*/job.json'))), 1)

    def test_manual_prepare_submitted_job_is_preserved_for_original_recovery(self):
        project = state.load_project(self.root)
        project['image_route'] = 'openai_image_api'
        state.write_json(self.root / '_state/project.json', project)
        manual = self.prepare()
        path = self.root / manual['jobs'][0]
        job = state.read_json(path)
        job.update(status='running', task_id='provider-test-id')
        state.write_json(path, job)
        before = path.read_bytes()
        self.start({'image': self.image()})
        reused = self.prepare()
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(autopilot.status(self.root).get('image_job_bindings'))
        result, transport = self.run_batch(reused, resume=True)
        self.assertEqual(result['results'][0]['status'], 'downloaded')
        self.assertEqual([p[0] for p in transport.posts], ['/v1/draw/result'])


if __name__ == '__main__': unittest.main()
