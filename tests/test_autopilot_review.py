"""Behavior checks for optional dispatch and independent review; all data synthetic."""
from pathlib import Path
import json
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
from runtime import state, autopilot, review
from workflow_fixture import enable_modules


class AutopilotReviewTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs/autopilot-review-20261004/fixtures' / uuid.uuid4().hex
        state.init_project(self.root, 'Synthetic optional-mode test')
        enable_modules(self.root, ['analyze'])
        self.source = 'planning/source.md'
        (self.root / self.source).write_text('Synthetic source: 2 + 3 = 5.\n', encoding='utf-8')

    def task(self, name='analysis', **updates):
        return dict(id=name, step='analysis', kind='produce', depends_on=[],
                    inputs=[self.source], outputs=['report'], instruction='Analyze synthetic source.',
                    **updates)

    def start(self, tasks=None):
        return autopilot.start(self.root, {'activation_evidence': 'Synthetic explicit automatic mode request',
                                          'tasks': tasks or [self.task()]})

    def produce(self, task_id='analysis'):
        action = autopilot.next_task(self.root, 'synthetic-maker')
        self.assertEqual(action['action'], 'produce')
        path = 'planning/' + task_id + '-' + uuid.uuid4().hex + '.md'
        (self.root / path).write_text('Synthetic checked report: 2 + 3 = 5.\n', encoding='utf-8')
        return autopilot.record(self.root, {'task_id': task_id, 'claim': action['claim'],
            'status': 'produced', 'artifacts': {'report': path}})

    def report(self, packet, verdict='pass', reviewer='synthetic-independent-reader'):
        data = state.read_json(self.root / packet)
        return {'packet_sha256': state.sha256(self.root / packet), 'reviewer_id': reviewer,
                'method': 'independent_agent', 'source_versions': data['versions'],
                'checks': [{'id': item['id'], 'verdict': verdict,
                            'evidence': list(data['artifacts']), 'note': 'Synthetic observed evidence'}
                           for item in data['criteria']]}

    def pass_review(self):
        action = autopilot.next_task(self.root, 'synthetic-host')
        self.assertEqual(action['action'], 'review')
        review.record(self.root, action['packet'], self.report(action['packet']))
        return action

    def test_absent_queue_is_manual_and_read_only(self):
        before = sorted(str(p) for p in self.root.rglob('*'))
        self.assertEqual(autopilot.status(self.root)['mode'], 'manual')
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'manual')
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob('*')))

    def test_activation_needs_real_explicit_evidence(self):
        with self.assertRaises(ValueError):
            autopilot.start(self.root, {'tasks': [self.task()]})
        self.start()
        self.assertEqual(autopilot.status(self.root)['mode'], 'automatic')

    def test_claim_is_not_dispatched_twice(self):
        self.start()
        first = autopilot.next_task(self.root, 'maker')
        again = autopilot.next_task(self.root, 'other-host')
        self.assertEqual(first['action'], 'produce')
        self.assertEqual(again['action'], 'recover')
        self.assertEqual(first['claim'], again['claim'])

    def test_review_then_dependency_then_queue_completion(self):
        tasks = [self.task(), {**self.task('second'), 'depends_on': ['analysis']}]
        self.start(tasks)
        self.produce()
        self.pass_review()
        next_action = autopilot.next_task(self.root, 'maker')
        self.assertEqual(next_action['task']['id'], 'second')
        self.assertFalse(autopilot.status(self.root)['whole_course_complete'])

    def test_queue_complete_is_not_whole_course_complete(self):
        self.start(); self.produce(); self.pass_review()
        result = autopilot.next_task(self.root, 'host')
        self.assertEqual(result['action'], 'queue_complete')
        self.assertIs(result['whole_course_complete'], False)

    def test_manual_pause_and_resume_preserve_claim(self):
        self.start()
        action = autopilot.next_task(self.root, 'maker')
        autopilot.control(self.root, mode='manual', evidence='Synthetic switch')
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'manual')
        autopilot.control(self.root, mode='automatic', evidence='Synthetic resume')
        autopilot.control(self.root, paused=True, evidence='Synthetic pause')
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'paused')
        autopilot.control(self.root, paused=False, evidence='Synthetic resume')
        self.assertEqual(autopilot.next_task(self.root, 'host')['claim'], action['claim'])

    def test_source_change_blocks_old_claim(self):
        self.start(); action = autopilot.next_task(self.root, 'maker')
        (self.root / self.source).write_text('Revised source', encoding='utf-8')
        with self.assertRaises(ValueError):
            autopilot.record(self.root, {'task_id': 'analysis', 'claim': action['claim'],
                'status': 'produced', 'artifacts': {'report': self.source}})

    def test_standalone_review_does_not_enable_auto_or_approve(self):
        log = self.root / '_state/decisions.jsonl'; before = log.read_bytes()
        packet = review.prepare(self.root, {'rubric': 'source', 'producer_id': 'maker',
            'artifacts': [self.source], 'sources': [self.source], 'instruction': 'Review synthetic source.'})['packet']
        report = self.report(packet)
        review.record(self.root, packet, report)
        self.assertTrue(review.status(self.root, packet)['valid'])
        self.assertEqual(before, log.read_bytes())
        self.assertEqual(autopilot.status(self.root)['mode'], 'manual')

    def test_self_review_and_missing_criteria_rejected(self):
        self.start(); self.produce()
        packet = autopilot.next_task(self.root, 'host')['packet']
        with self.assertRaises(ValueError):
            review.record(self.root, packet, self.report(packet, reviewer='synthetic-maker'))
        report = self.report(packet); report['checks'].pop()
        with self.assertRaises(ValueError): review.record(self.root, packet, report)

    def test_unverified_is_not_pass(self):
        self.start(); self.produce()
        packet = autopilot.next_task(self.root, 'host')['packet']
        result = review.record(self.root, packet, self.report(packet, verdict='unverified'))
        self.assertEqual(result['verdict'], 'unverified')
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'waiting')

    def test_failed_review_retries_with_bound(self):
        self.start(); self.produce()
        packet = autopilot.next_task(self.root, 'host')['packet']
        review.record(self.root, packet, self.report(packet, verdict='changes_required'))
        action = autopilot.next_task(self.root, 'maker')
        self.assertEqual(action['action'], 'produce')
        self.assertEqual(action['attempt'], 2)
        self.assertTrue(action['findings'])

    def test_review_stales_when_source_or_adoption_changes(self):
        self.start(); self.produce(); action = self.pass_review()
        state.record_approval(self.root, {'targets': [{'path': self.source,
            'sha256': state.sha256(self.root / self.source)}], 'decision': 'rejected',
            'user_evidence': 'Synthetic explicit rejection'})
        self.assertFalse(review.status(self.root, action['packet'])['valid'])
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'waiting')

    def test_unknown_external_submission_never_redispatched(self):
        self.start(); action = autopilot.next_task(self.root, 'maker')
        autopilot.record(self.root, {'task_id': 'analysis', 'claim': action['claim'],
            'status': 'unknown', 'message': 'Synthetic submission outcome unknown'})
        for _ in range(3): self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'waiting')
        with self.assertRaises(ValueError): autopilot.retry(self.root, 'analysis', 'Blind retry')

    def test_human_wait_allows_independent_task_and_requires_receipt(self):
        tasks = [{**self.task('external'), 'kind': 'human'}, self.task()]
        self.start(tasks)
        action = autopilot.next_task(self.root, 'maker')
        self.assertEqual(action['task']['id'], 'analysis')
        self.assertEqual(action['human_tasks'][0]['task']['id'], 'external')
        pending = action['human_tasks'][0]
        with self.assertRaises(ValueError):
            autopilot.record(self.root, {'task_id': 'external', 'claim': pending['claim'],
                'status': 'completed', 'artifacts': {'report': self.source}})

    def test_existing_workflow_adoption_gate_still_blocks(self):
        data = state.read_json(self.root / '_state/workflow.json')
        data.update(project_mode='full_course', stages={})
        data['current_task'].update(mode='full_course', modules=['studio'])
        state.write_json(self.root / '_state/workflow.json', data)
        self.start([{**self.task(), 'step': 'video-script', 'video_id': 'V001'}])
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'waiting')

    def test_invalid_graph_and_path_escape_fail(self):
        for tasks in ([{**self.task(), 'depends_on': ['missing']}],
                      [{**self.task(), 'depends_on': ['analysis']}],
                      [{**self.task(), 'inputs': ['../outside.md']}]):
            with self.assertRaises(ValueError): self.start(tasks)

    def test_review_result_cannot_turn_unverified_into_pass(self):
        self.start(); self.produce()
        packet = autopilot.next_task(self.root, 'host')['packet']
        review.record(self.root, packet, self.report(packet, verdict='unverified'))
        path = (self.root / packet).with_name('result.json')
        tampered = state.read_json(path); tampered['verdict'] = 'pass'
        state.write_json(path, tampered)
        self.assertFalse(review.status(self.root, packet)['valid'])

    def test_review_report_versions_cannot_be_changed_after_import(self):
        self.start(); self.produce(); action = self.pass_review()
        path = (self.root / action['packet']).with_name('result.json')
        tampered = state.read_json(path); tampered['report']['source_versions'] = {}
        state.write_json(path, tampered)
        self.assertFalse(review.status(self.root, action['packet'])['valid'])

    def test_selected_source_pointer_change_stales_preserved_old_file(self):
        data = state.read_json(self.root / '_state/workflow.json')
        data['stages']['blueprint'] = {'files': {'plan': {'path': self.source,
            'sha256': state.sha256(self.root / self.source)}}}
        state.write_json(self.root / '_state/workflow.json', data)
        packet = review.prepare(self.root, {'producer_id': 'maker', 'rubric': 'teaching',
            'artifacts': [self.source], 'sources': [self.source], 'instruction': 'Synthetic pointer review'})['packet']
        review.record(self.root, packet, self.report(packet))
        other = 'planning/source-v002.md'
        (self.root / other).write_text('A new version is now selected.', encoding='utf-8')
        data['stages']['blueprint']['files']['plan'] = {'path': other, 'sha256': state.sha256(self.root / other)}
        state.write_json(self.root / '_state/workflow.json', data)
        self.assertTrue((self.root / self.source).exists())
        self.assertFalse(review.status(self.root, packet)['valid'])

    def test_result_is_idempotent_but_different_report_cannot_overwrite(self):
        self.start(); produced = self.produce()
        packet = produced['packet']; report = self.report(packet)
        first = review.record(self.root, packet, report)
        self.assertEqual(first, review.record(self.root, packet, report))
        with self.assertRaises(ValueError): review.record(self.root, packet, self.report(packet, verdict='unverified'))

    def test_downstream_result_rejected_when_ancestor_changes_midflight(self):
        self.start([self.task(), {**self.task('second'), 'depends_on': ['analysis']}])
        self.produce(); self.pass_review()
        child = autopilot.next_task(self.root, 'maker')
        (self.root / self.source).write_text('Changed while second task was working.', encoding='utf-8')
        path = 'planning/second.md'; (self.root / path).write_text('Stale child result.', encoding='utf-8')
        with self.assertRaises(ValueError):
            autopilot.record(self.root, {'task_id': 'second', 'claim': child['claim'],
                'status': 'produced', 'artifacts': {'report': path}})

    def test_external_review_failure_is_not_retried(self):
        self.start([{**self.task(), 'side_effects': 'external'}]); self.produce()
        packet = autopilot.next_task(self.root, 'host')['packet']
        review.record(self.root, packet, self.report(packet, verdict='changes_required'))
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'waiting')
        with self.assertRaises(ValueError): autopilot.retry(self.root, 'analysis', 'Synthetic request')

    def test_second_failed_review_reaches_attempt_limit(self):
        self.start(); self.produce()
        packet = autopilot.next_task(self.root, 'host')['packet']
        review.record(self.root, packet, self.report(packet, verdict='changes_required'))
        self.produce()
        packet = autopilot.next_task(self.root, 'host')['packet']
        review.record(self.root, packet, self.report(packet, verdict='changes_required'))
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'waiting')
        with self.assertRaises(ValueError): autopilot.retry(self.root, 'analysis', 'Third attempt')

    def test_append_and_scope_reconcile_preserve_mode_and_tasks(self):
        self.start()
        task = {**self.task('later'), 'depends_on': ['analysis']}
        autopilot.extend(self.root, [task], 'Synthetic next scope')
        autopilot.extend(self.root, [task], 'Same extension')
        self.assertEqual(len(autopilot.status(self.root)['tasks']), 2)
        data = state.read_json(self.root / '_state/workflow.json')
        data['current_task']['evidence'] = 'Synthetic renewed request'
        state.write_json(self.root / '_state/workflow.json', data)
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'waiting')
        autopilot.reconcile(self.root, 'Synthetic instruction to continue same authorized scope')
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'produce')

    def test_all_five_rubrics_require_observations(self):
        for rubric in review.RUBRICS:
            packet = review.prepare(self.root, {'producer_id': 'maker', 'rubric': rubric,
                'artifacts': [self.source], 'sources': [self.source], 'instruction': 'Synthetic format check only'})['packet']
            report = self.report(packet); report['checks'][0]['note'] = ''
            with self.assertRaises(ValueError): review.record(self.root, packet, report)

    def test_os_lock_prevents_concurrent_writer(self):
        from runtime import automation_store
        script = ('import sys; sys.path.insert(0, sys.argv[1]); from runtime import automation_store; '
                  '\nwith automation_store.locked(sys.argv[2]): print("unexpected lock")')
        with automation_store.locked(self.root):
            result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', script,
                str(ROOT / 'skills/math-courseware-studio/scripts'), str(self.root)],
                capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Another automation command', result.stderr)

    def test_real_cli_default_and_activation(self):
        cli = ROOT / 'skills/math-courseware-studio/scripts/courseware.py'
        def call(*args):
            result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(cli),
                *args, '--project', str(self.root)], capture_output=True, text=True, encoding='utf-8', timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertEqual(call('run-status')['mode'], 'manual')
        plan = self.root / 'planning/queue.json'
        state.write_json(plan, {'activation_evidence': 'Synthetic explicit enable', 'tasks': [self.task()]})
        self.assertEqual(call('run-start', '--plan', str(plan))['mode'], 'automatic')
        action = call('run-next', '--actor', 'cli-maker')
        self.assertEqual(action['action'], 'produce')
        self.assertEqual(call('run-next', '--actor', 'cli-other')['action'], 'recover')
        artifact = 'planning/cli-report.md'
        (self.root / artifact).write_text('Synthetic requirements report; 2 + 3 = 5.', encoding='utf-8')
        result_file = self.root / 'planning/cli-result.json'
        state.write_json(result_file, {'task_id': 'analysis', 'claim': action['claim'],
            'status': 'produced', 'artifacts': {'report': artifact}})
        self.assertEqual(call('run-record', '--result', str(result_file))['status'], 'review_ready')
        packet = call('run-next', '--actor', 'cli-host')['packet']
        report_file = self.root / 'planning/cli-review.json'
        state.write_json(report_file, self.report(packet, verdict='unverified'))
        self.assertEqual(call('review-record', '--packet', packet, '--report', str(report_file))['verdict'], 'unverified')
        self.assertEqual(call('review-status', '--packet', packet)['verdict'], 'unverified')
        self.assertEqual(call('run-next', '--actor', 'cli-host')['action'], 'waiting')
        call('run-recheck', '--task-id', 'analysis', '--evidence', 'Synthetic viewing now available')
        packet = call('run-next', '--actor', 'cli-host')['packet']
        state.write_json(report_file, self.report(packet))
        call('review-record', '--packet', packet, '--report', str(report_file))
        call('run-mode', '--mode', 'manual', '--evidence', 'Synthetic switch')
        self.assertEqual(call('run-next', '--actor', 'cli-host')['action'], 'manual')
        call('run-pause', '--evidence', 'Synthetic pause')
        call('run-mode', '--mode', 'automatic', '--evidence', 'Synthetic opt in again')
        self.assertEqual(call('run-next', '--actor', 'cli-host')['action'], 'paused')
        call('run-resume', '--evidence', 'Synthetic resume')
        self.assertEqual(call('run-next', '--actor', 'cli-host')['action'], 'queue_complete')
        extension = self.root / 'planning/cli-extend.json'
        state.write_json(extension, {'activation_evidence': 'Synthetic scoped extension',
            'tasks': [{**self.task('second'), 'depends_on': ['analysis']}]})
        call('run-extend', '--plan', str(extension))
        call('run-reconcile', '--evidence', 'Synthetic same authorized scope')
        next_action = call('run-next', '--actor', 'cli-maker')
        state.write_json(result_file, {'task_id': 'second', 'claim': next_action['claim'],
            'status': 'failed', 'message': 'Synthetic verified local failure'})
        call('run-record', '--result', str(result_file))
        call('run-retry', '--task-id', 'second', '--evidence', 'Synthetic local issue resolved')
        self.assertEqual(call('run-next', '--actor', 'cli-maker')['attempt'], 2)
        standalone = self.root / 'planning/cli-review-request.json'
        state.write_json(standalone, {'producer_id': 'maker', 'rubric': 'teaching',
            'artifacts': [artifact], 'sources': [self.source], 'instruction': 'Synthetic standalone review'})
        self.assertIn('packet', call('review-prepare', '--request', str(standalone)))

    def test_completed_task_rechecks_its_review(self):
        self.start(); self.produce(); action = self.pass_review()
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'queue_complete')
        path = (self.root / action['packet']).with_name('result.json')
        report = state.read_json(path); report['report']['reviewer_id'] = 'changed-identity'
        state.write_json(path, report)
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'waiting')

    def test_interrupted_snapshot_save_recovers_without_overwriting_evidence(self):
        self.start()
        real_write = state.write_json
        def fail_active_run(path, data):
            if Path(path).name == 'run.json': raise OSError('Synthetic interruption before mutable pointer')
            return real_write(path, data)
        with patch.object(state, 'write_json', side_effect=fail_active_run):
            with self.assertRaises(OSError): autopilot.next_task(self.root, 'host')
        action = autopilot.next_task(self.root, 'host')
        self.assertEqual(action['action'], 'produce')
        versions = list((self.root / '_state/automation/runs').glob('*/revision-*.json'))
        self.assertEqual(len(versions), 3)

    def test_null_identity_or_optin_is_not_evidence(self):
        self.start()
        with self.assertRaises(ValueError): autopilot.extend(self.root, [self.task('extra')], None)
        with self.assertRaises(ValueError):
            review.prepare(self.root, {'producer_id': None, 'rubric': 'source',
                'artifacts': [self.source], 'sources': [self.source], 'instruction': 'Synthetic'})

    def test_recheck_unverified_preserves_actual_output_and_production_attempt(self):
        self.start(); produced = self.produce()
        original = autopilot.status(self.root)['tasks'][0]['output_versions']
        packet = autopilot.next_task(self.root, 'host')['packet']
        review.record(self.root, packet, self.report(packet, verdict='unverified'))
        autopilot.recheck(self.root, 'analysis', 'Synthetic viewing tool now available')
        action = autopilot.next_task(self.root, 'host')
        self.assertEqual(action['action'], 'review')
        self.assertNotEqual(action['packet'], produced['packet'])
        self.assertEqual(action['attempt'], 1)
        review.record(self.root, action['packet'], self.report(action['packet']))
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'queue_complete')
        self.assertEqual(original, autopilot.status(self.root)['tasks'][0]['output_versions'])

    def test_recheck_cannot_pass_changed_sources_or_repeat_forever(self):
        self.start(); self.produce()
        packet = autopilot.next_task(self.root, 'host')['packet']
        review.record(self.root, packet, self.report(packet, verdict='unverified'))
        autopilot.recheck(self.root, 'analysis', 'Synthetic second look')
        packet = autopilot.next_task(self.root, 'host')['packet']
        review.record(self.root, packet, self.report(packet, verdict='unverified'))
        with self.assertRaises(ValueError): autopilot.recheck(self.root, 'analysis', 'Third look')
        (self.root / self.source).write_text('Changed source', encoding='utf-8')
        with self.assertRaises(ValueError): autopilot.recheck(self.root, 'analysis', 'Changed source')

    def test_inflight_record_without_optional_review_counter_can_resume(self):
        self.start(); action = autopilot.next_task(self.root, 'maker')
        pointer = state.read_json(self.root / '_state/automation/active.json')
        path = self.root / '_state/automation/runs' / pointer['run_id'] / 'run.json'
        data = state.read_json(path); data['tasks'][0].pop('review_attempt')
        state.write_json(path, data)
        artifact = 'planning/recovered.md'
        (self.root / artifact).write_text('Actual retained output.', encoding='utf-8')
        result = autopilot.record(self.root, {'task_id': 'analysis', 'claim': action['claim'],
            'status': 'produced', 'artifacts': {'report': artifact}})
        self.assertEqual(result['status'], 'review_ready')


if __name__ == '__main__':
    unittest.main()
