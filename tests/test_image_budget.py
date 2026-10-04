"""Same-run image budgets: retained synthetic courses and fake transports only."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
import uuid

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
import courseware
from runtime import state, autopilot, prompts, image_api, review, automation_store as store
from workflow_fixture import enable_modules
from test_image_api import Transport


class ImageBudgetTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs/autopilot-abcd1-20261004/fixtures' / ('b-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic image budget', 'openai_image_api')
        enable_modules(self.root, ['analyze', 'plan', 'editable'])
        self.source = 'planning/source.md'
        (self.root / self.source).write_text('Synthetic source: 2 + 3 = 5.', encoding='utf-8')

    def task(self, name='analysis', **extra):
        return dict(id=name, step='analysis', inputs=[self.source], outputs=['report'],
                    instruction='Synthetic content only', **extra)

    def start(self, limit=None, route='openai_image_api', tasks=None):
        self.plan = {'activation_evidence': 'Synthetic explicit automatic consent',
                     'preferences': {'image': {'route': route, 'evidence': 'Synthetic actual choice',
                         'authorization': {'scope': 'run', 'purposes': ['test', 'cover', 'asset', 'page', 'erase', 'repair'],
                             'paid_generation': route == 'openai_image_api', 'include_rework': True,
                             'scope_evidence': 'Synthetic actual consent including rework'}}},
                     'tasks': tasks or [self.task()]}
        if limit is not None:
            self.plan['limits'] = {'max_images': limit, 'evidence': 'Synthetic actual limit'}
        return autopilot.start(self.root, self.plan)

    def prepare(self, target='TEST001', version='v001'):
        return prompts.prepare(self.root, {'tasks': [{'purpose': 'test', 'target_id': target,
            'version': version, 'prompt': 'Synthetic image only; never call a real provider'}],
            'authorization_evidence': 'Synthetic explicit batch consent'})

    def batch(self, count, prefix='BATCH'):
        # Each prepare is a legitimate isolated synthetic connection test; combine existing
        # pending jobs only to exercise the executor's whole-batch capacity check.
        batches = [self.prepare(prefix + str(i)) for i in range(count)]
        result = {**batches[0], 'jobs': [b['jobs'][0] for b in batches], 'concurrency': count}
        result['path'] = '_state/jobs/budget-batch-' + uuid.uuid4().hex + '.json'
        state.write_json(self.root / result['path'], result)
        return result

    def execute(self, batch, transport=None, resume=False):
        transport = transport or Transport()
        with patch.object(image_api, 'HttpTransport', lambda key: transport):
            result = image_api.run_batch(self.root, batch, 'synthetic-key', resume=resume)
        return result, transport

    def direct(self, batch, transport=None, resume=False):
        return image_api.run_job(self.root, batch['jobs'][0], transport or Transport(),
                                 resume=resume, timeout=1, poll_interval=0,
                                 authorization_evidence=batch.get('authorization_evidence', ''))

    def summary(self):
        result = autopilot.status(self.root)
        self.assertIn('image_budget_status', result, 'run-status must expose actual image accounting')
        return result['image_budget_status']

    def run_path(self):
        return state.resolve(self.root, store.AREA + '/runs/' + store.load_run(self.root)['run_id'] + '/run.json')

    def legacy(self):
        data = store.load_run(self.root)
        data.pop('limits', None)
        data.pop('image_budget', None)
        state.write_json(self.run_path(), data)

    def configure(self, maximum):
        return autopilot.configure(self.root, {'limits': {'max_images': maximum,
            'evidence': 'Synthetic actual authorization for a new total cap'}})

    def builtin(self, batch, source=None):
        path = batch['jobs'][0]
        job = state.read_json(self.root / path)
        source = source or self.root / ('slides/synthetic-' + uuid.uuid4().hex + '.png')
        if not source.exists(): Image.new('RGB', (32, 18), 'white').save(source)
        return image_api.register_builtin(self.root, {'job_path': path,
            'input_digest': job['input_digest'], 'image_path': str(source),
            'tool_evidence': 'Synthetic successful builtin response'})

    def test_default_60_and_59_to_60_to_61_hard_boundary(self):
        result = self.start()
        self.assertEqual(result.get('limits', {}).get('max_images'), 60)
        for index in range(59): self.direct(self.prepare('LIMIT' + str(index)))
        self.assertEqual(self.summary()['used'], 59)
        self.direct(self.prepare('LIMIT59'))
        transport = Transport()
        with self.assertRaisesRegex(ValueError, 'budget|limit'):
            self.direct(self.prepare('LIMIT60'), transport)
        self.assertEqual(transport.posts, [])
        self.assertEqual((self.summary()['used'], self.summary()['remaining']), (60, 0))

    def test_start_rejects_nonpositive_noninteger_and_boolean_limits(self):
        for value in [0, -1, True, 1.5, '60']:
            with self.subTest(value=value), self.assertRaises(ValueError): self.start(value)
        self.assertIsNone(store.load_run(self.root))

    def test_four_pending_with_two_remaining_is_zero_requests_and_zero_charges(self):
        self.start(2)
        batch, transport = self.batch(4), Transport()
        with self.assertRaisesRegex(ValueError, 'budget|limit'): self.execute(batch, transport)
        self.assertEqual(transport.posts, [])
        self.assertEqual(self.summary()['used'], 0)
        self.assertTrue(all(state.read_json(self.root / p)['status'] == 'pending' for p in batch['jobs']))

    def test_complete_batch_reserves_once_and_repeated_execution_is_idempotent(self):
        self.start(4)
        batch, transport = self.batch(4), Transport()
        result, _ = self.execute(batch, transport)
        self.assertEqual([r['status'] for r in result['results']], ['downloaded'] * 4)
        self.execute(batch, transport)
        self.execute(batch, transport, resume=True)
        self.assertEqual(self.summary()['used'], 4)
        self.assertEqual(sum(p[0] == image_api.ENDPOINT for p in transport.posts), 4)

    def test_entire_batch_local_validation_precedes_any_charge_or_submission(self):
        self.start(4)
        batch, transport = self.batch(4), Transport()
        last = state.read_json(self.root / batch['jobs'][-1])
        (self.root / last['prompt_path']).write_text('Synthetic changed input', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Prompt changed'): self.execute(batch, transport)
        self.assertEqual(transport.posts, [])
        self.assertEqual(self.summary()['used'], 0)

    def test_direct_concurrent_last_slot_cannot_overspend(self):
        self.start(1)
        first, second = self.prepare('FIRST'), self.prepare('SECOND')
        started, release = threading.Event(), threading.Event()
        class Slow(Transport):
            def post(inner, endpoint, payload, timeout):
                if endpoint == image_api.ENDPOINT:
                    started.set()
                    release.wait(5)
                return super().post(endpoint, payload, timeout)
        transport = Slow()
        with ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(self.direct, first, transport)
            self.assertTrue(started.wait(5))
            try:
                other = Transport()
                with self.assertRaisesRegex(ValueError, 'budget|limit'): self.direct(second, other)
                self.assertEqual(other.posts, [])
            finally: release.set()
            self.assertEqual(future.result()['status'], 'downloaded')
        self.assertEqual(self.summary()['used'], 1)

    def test_simultaneous_independent_jobs_share_atomic_final_slot(self):
        self.start(1)
        batches = [self.prepare('RACE_A'), self.prepare('RACE_B')]
        barrier = threading.Barrier(2)
        transports = [Transport(), Transport()]
        def execute(index):
            barrier.wait(timeout=5)
            try: return self.direct(batches[index], transports[index])['status']
            except ValueError as exc: return str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(execute, range(2)))
        self.assertEqual(outcomes.count('downloaded'), 1)
        self.assertEqual(sum(p[0] == image_api.ENDPOINT for t in transports for p in t.posts), 1)
        self.assertEqual(self.summary()['used'], 1)

    def test_capacity_rechecked_under_lock_after_preflight_race(self):
        self.start(2)
        batch, racer = self.batch(2), self.prepare('RACER')
        original = image_api.validate_batch
        def race(project, candidate, resume=False):
            original(project, candidate, resume)
            self.direct(racer)
        transport = Transport()
        with patch.object(image_api, 'validate_batch', side_effect=race):
            with self.assertRaisesRegex(ValueError, 'budget|limit'): self.execute(batch, transport)
        self.assertEqual(transport.posts, [])
        self.assertEqual(self.summary()['used'], 1)

    def test_unknown_and_failed_attempts_remain_charged_without_retry(self):
        self.start(2)
        unknown = self.prepare('UNKNOWN')
        transport = Transport(TimeoutError('synthetic untrusted transport detail'))
        self.assertEqual(self.direct(unknown, transport)['status'], 'submission_unknown')
        self.direct(unknown, transport)
        self.direct(unknown, transport, resume=True)
        failed = self.prepare('FAILED')
        self.assertEqual(self.direct(failed, Transport({'code': 500}))['status'], 'failed')
        self.assertEqual(len(transport.posts), 1)
        self.assertEqual(self.summary()['used'], 2)
        with self.assertRaises(ValueError): self.direct(self.prepare('EXTRA'))

    def test_reservation_survives_crash_before_pending_job_state_is_written(self):
        self.start(2)
        batch, transport = self.prepare(), Transport()
        job_path = self.root / batch['jobs'][0]
        write = state.write_json
        def crash(path, value):
            if Path(path) == job_path and value.get('status') == 'submitting':
                raise OSError('Synthetic disk failure after durable reservation')
            return write(path, value)
        with patch.object(state, 'write_json', side_effect=crash):
            with self.assertRaises(OSError): self.direct(batch, transport)
        self.assertEqual(state.read_json(job_path)['status'], 'pending')
        self.assertEqual(self.summary()['used'], 1)
        with self.assertRaisesRegex(ValueError, 'reconcil|unknown|reservation'): self.direct(batch, transport)
        self.assertEqual(transport.posts, [])
        # Recovered provider evidence may resolve the old reservation, never a new submit.
        job = state.read_json(job_path)
        job.update(status='running', task_id='provider-test-id')
        state.write_json(job_path, job)
        self.assertEqual(self.direct(batch, transport, resume=True)['status'], 'downloaded')
        self.assertEqual([p[0] for p in transport.posts], [image_api.RESULT_ENDPOINT])
        self.assertEqual(self.summary()['used'], 1)

    def test_download_recovery_at_cap_does_not_recount_or_resubmit(self):
        self.start(1)
        batch, transport = self.prepare(), Transport(fail_download=True)
        self.assertEqual(self.direct(batch, transport)['status'], 'download_failed')
        transport.fail_download = False
        self.assertEqual(self.direct(batch, transport, resume=True)['status'], 'downloaded')
        self.assertEqual(sum(p[0] == image_api.ENDPOINT for p in transport.posts), 1)
        self.assertEqual(self.summary()['used'], 1)

    def test_rework_new_jobs_extensions_modes_and_start_do_not_reset(self):
        self.start(2)
        self.direct(self.prepare())
        autopilot.extend(self.root, [self.task('extra')], 'Synthetic actual extension')
        autopilot.control(self.root, mode='manual', evidence='Synthetic actual mode switch')
        self.direct(self.prepare(version='v002'))
        autopilot.start(self.root, self.plan)
        with self.assertRaises(ValueError): self.direct(self.prepare('NEW_ID'))
        self.assertEqual(self.summary()['used'], 2)
        self.assertEqual(autopilot.status(self.root)['mode'], 'manual')

    def test_all_actual_image_purposes_share_the_same_counter(self):
        state.write_json(self.root / '_state/story.json', {'visual_style': 'Synthetic clear style', 'events': []})
        state.write_json(self.root / '_state/assets.json', {'assets': [
            {'asset_id': 'CHAR001', 'version': 'v001', 'fixed_features': 'Synthetic red character'}]})
        state.write_json(self.root / '_state/pages.json', {'pages': [
            {'page_id': 'P001', 'order': 1, 'title': 'Synthetic page', 'layout': 'Central content',
             'visual_description': 'Two synthetic dots', 'math_ids': [], 'story_ids': [], 'asset_refs': [],
             'text_units': [{'unit_id': 'P001-T01', 'text': 'Two dots'}]}]})
        paths = ['_state/story.json', '_state/assets.json', '_state/pages.json']
        state.record_approval(self.root, {'targets': [{'path': p, 'sha256': state.sha256(self.root / p)} for p in paths],
                                         'user_evidence': 'Synthetic source approval only'})
        enable_modules(self.root, ['analyze', 'plan', 'pages', 'editable'], route='B')
        self.start(6)
        self.direct(self.prepare())
        page_image = None
        for purpose, target in [('cover', 'COVER'), ('asset', 'CHAR001'), ('page', 'P001'),
                                ('erase', 'P001'), ('repair', 'P001')]:
            task = {'purpose': purpose, 'target_id': target, 'prompt': 'Synthetic actual purpose'}
            if purpose in ('erase', 'repair'):
                task.update(source_image={'path': page_image['output_path'], 'sha256': page_image['sha256']},
                            remove_texts=['Two dots'], preserve_elements=['Two synthetic dots'])
            batch = prompts.prepare(self.root, {'tasks': [task]})
            result = self.direct(batch)
            if purpose == 'page':
                page_image = result
                state.record_approval(self.root, {'targets': [{'path': result['output_path'], 'sha256': result['sha256']}],
                                                 'user_evidence': 'Synthetic page image approval'})
        self.assertEqual(self.summary()['used'], 6)
        entries = store.load_run(self.root)['image_budget']['entries'].values()
        self.assertEqual({item['purpose'] for item in entries}, {'test', 'cover', 'asset', 'page', 'erase', 'repair'})
        with self.assertRaises(ValueError): self.direct(self.prepare('EXTRA'))

    def test_limit_extension_keeps_ledger_and_resume_alone_does_not_release(self):
        self.start(1)
        self.direct(self.prepare())
        before = store.load_run(self.root)['image_budget']
        autopilot.control(self.root, paused=False, evidence='Synthetic resume request')
        batch = self.prepare('NEXT')
        with self.assertRaises(ValueError): self.direct(batch)
        self.configure(2)
        self.assertEqual(store.load_run(self.root)['image_budget'], before)
        self.direct(batch)
        self.assertEqual(self.summary()['used'], 2)

    def test_invalid_configuration_is_atomic_and_cannot_replace_ledger(self):
        self.start(2)
        self.direct(self.prepare())
        before = self.run_path().read_bytes()
        for changes in [{'limits': {'max_images': True, 'evidence': 'Synthetic'}},
                        {'limits': {'max_images': 3}}, {'limits': {'max_images': 0, 'evidence': 'Synthetic'}},
                        {'limits': {'max_images': 3, 'evidence': ' '}},
                        {'limits': {'max_images': 3, 'evidence': 'Synthetic'}, 'image_budget': {}},
                        {'limits': {'max_images': 3, 'evidence': 'Synthetic'}, 'video': {'model': None, 'evidence': 'Synthetic'}}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError): autopilot.configure(self.root, changes)
            self.assertEqual(self.run_path().read_bytes(), before)

    def test_legacy_status_read_only_and_explicit_configure_starts_unknown_history(self):
        self.start()
        batch = self.prepare()
        self.legacy()
        before = self.run_path().read_bytes()
        info = self.summary()
        self.assertFalse(info['configured'])
        self.assertTrue(info['history_unknown'])
        self.assertEqual(self.run_path().read_bytes(), before)
        transport = Transport()
        with self.assertRaisesRegex(ValueError, 'run-configure|unconfigured'): self.direct(batch, transport)
        self.assertEqual(transport.posts, [])
        self.configure(3)
        info = self.summary()
        self.assertTrue(info['configured'])
        self.assertTrue(info['history_unknown'])
        self.assertTrue(info['accounting_started_at'])
        self.assertEqual(info['used'], 0)
        self.direct(batch)
        self.assertEqual(self.summary()['used'], 1)

    def test_legacy_submitted_jobs_recover_without_configuring_or_estimating(self):
        self.start()
        batch = self.prepare()
        job_path = self.root / batch['jobs'][0]
        job = state.read_json(job_path)
        job.update(status='running', task_id='provider-test-id')
        state.write_json(job_path, job)
        self.legacy()
        before = self.run_path().read_bytes()
        result, transport = self.execute(batch, resume=True)
        self.assertEqual(result['results'][0]['status'], 'downloaded')
        self.assertEqual([p[0] for p in transport.posts], [image_api.RESULT_ENDPOINT])
        self.assertEqual(self.run_path().read_bytes(), before)

    def test_no_run_manual_execution_and_registration_create_no_budget(self):
        self.direct(self.prepare())
        project = state.load_project(self.root)
        project['image_route'] = 'builtin'
        state.write_json(self.root / '_state/project.json', project)
        self.builtin(self.prepare('BUILTIN'))
        self.assertIsNone(store.load_run(self.root))
        self.assertFalse(state.resolve(self.root, store.AREA).exists())

    def test_pending_manual_job_bound_to_current_run_is_charged(self):
        manual = self.prepare()
        before = (self.root / manual['jobs'][0]).read_bytes()
        self.start(1)
        reused = self.prepare()
        self.assertEqual((self.root / manual['jobs'][0]).read_bytes(), before)
        self.assertTrue(store.load_run(self.root).get('image_job_bindings'))
        self.direct(reused)
        with self.assertRaises(ValueError): self.direct(self.prepare('SECOND'))
        self.assertEqual(self.summary()['used'], 1)

    def test_builtin_duplicate_and_new_version_count_actual_success_only(self):
        self.start(2, route='builtin')
        batch = self.prepare()
        self.assertEqual(self.summary()['used'], 0)
        first = self.builtin(batch)
        self.builtin(batch, self.root / first['output_path'])
        self.assertEqual(self.summary()['used'], 1)
        self.builtin(self.prepare(version='v002'))
        self.assertEqual(self.summary()['used'], 2)

    def test_builtin_different_result_cannot_reuse_successful_job_to_evade_count(self):
        self.start(2, route='builtin')
        batch = self.prepare()
        first = self.builtin(batch)
        changed = self.root / 'slides/different-result.jpg'
        Image.new('RGB', (32, 18), 'red').save(changed)
        with self.assertRaisesRegex(ValueError, 'different|new version'):
            self.builtin(batch, changed)
        saved = state.read_json(self.root / batch['jobs'][0])
        self.assertEqual(saved['sha256'], first['sha256'])
        self.assertEqual(self.summary()['used'], 1)

    def test_builtin_registration_crash_keeps_exactly_one_charge_on_recovery(self):
        self.start(1, route='builtin')
        batch = self.prepare()
        path = self.root / batch['jobs'][0]
        source = self.root / 'slides/builtin-recovered.png'
        Image.new('RGB', (32, 18), 'white').save(source)
        write = state.write_json
        def crash(target, value):
            if Path(target) == path and value.get('status') == 'downloaded':
                raise OSError('Synthetic disk failure after builtin accounting')
            return write(target, value)
        with patch.object(state, 'write_json', side_effect=crash):
            with self.assertRaises(OSError): self.builtin(batch, source)
        self.assertEqual(self.summary()['used'], 1)
        self.assertEqual(self.builtin(batch, source)['status'], 'downloaded')
        self.assertEqual(self.summary()['used'], 1)

    def test_invalid_builtin_result_is_not_counted(self):
        self.start(1, route='builtin')
        batch = self.prepare()
        source = self.root / 'slides/invalid.png'
        source.write_bytes(b'Synthetic invalid image')
        with self.assertRaises(OSError): self.builtin(batch, source)
        self.assertEqual(self.summary()['used'], 0)

    def test_builtin_overshoot_keeps_result_and_blocks_future_dispatch(self):
        requests = [{'purpose': 'test', 'target_id': 'NEXT', 'version': 'v001'}]
        self.start(1, route='builtin', tasks=[self.task('image', image_requests=requests)])
        self.builtin(self.prepare())
        result = self.builtin(self.prepare('ALREADY_GENERATED'))
        self.assertEqual(result['status'], 'downloaded')
        self.assertEqual(state.sha256(self.root / result['output_path']), result['sha256'])
        self.assertEqual((self.summary()['used'], self.summary()['overshoot']), (2, 1))
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'waiting')
        self.configure(3)
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'produce')

    def test_builtin_registration_at_legacy_unconfigured_run_keeps_actual_result(self):
        self.start(route='builtin')
        batch = self.prepare()
        self.legacy()
        self.assertEqual(self.builtin(batch)['status'], 'downloaded')
        self.assertFalse(self.summary()['configured'])
        self.assertEqual(self.summary()['used'], 1)
        self.configure(3)
        self.assertEqual(self.summary()['used'], 1)
        self.assertTrue(self.summary()['history_unknown'])

    def test_old_downloaded_builtin_is_not_scanned_into_new_legacy_accounting(self):
        project = state.load_project(self.root)
        project['image_route'] = 'builtin'
        state.write_json(self.root / '_state/project.json', project)
        batch = self.prepare()
        result = self.builtin(batch)
        self.start(route='builtin')
        self.legacy()
        self.configure(3)
        self.builtin(batch, self.root / result['output_path'])
        self.assertEqual(self.summary()['used'], 0)
        self.assertTrue(self.summary()['history_unknown'])

    def test_declared_four_separate_images_wait_but_one_composite_dispatches(self):
        self.start(2, route='builtin', tasks=[self.task('four', image_count=4), self.task('composite', image_count=1)])
        action = autopilot.next_task(self.root, 'host')
        self.assertEqual(action['task']['id'], 'composite')
        blocked = autopilot.status(self.root)['tasks'][0]
        self.assertTrue(any('4' in item and '2' in item for item in blocked['issues']))
        self.assertEqual(self.summary()['used'], 0)

    def test_malformed_or_mismatching_declared_counts_rejected(self):
        for value in [0, -1, True, '4', 1.5]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.start(tasks=[self.task(image_count=value)])
        with self.assertRaises(ValueError):
            self.start(tasks=[self.task(image_count=2, image_requests=[
                {'purpose': 'test', 'target_id': 'ONE', 'version': 'v001'}])])

    def test_image_step_requires_count_but_explicit_text_only_work_can_continue(self):
        self.start(route='builtin', tasks=[{**self.task('cover'), 'step': 'cover'},
                                         self.task('text', requires_preferences=[])])
        action = autopilot.next_task(self.root, 'host')
        self.assertEqual(action['task']['id'], 'text')
        cover = autopilot.status(self.root)['tasks'][0]
        self.assertTrue(any('image_count' in issue for issue in cover['issues']))

    def test_explicit_count_requires_consent_even_with_empty_preference_override(self):
        autopilot.start(self.root, {'activation_evidence': 'Synthetic explicit auto request',
            'tasks': [self.task('image', requires_preferences=[], image_count=1), self.task('text')]})
        action = autopilot.next_task(self.root, 'host')
        self.assertEqual(action['task']['id'], 'text')
        blocked = autopilot.status(self.root)['tasks'][0]
        self.assertTrue(any('image.authorization' in issue for issue in blocked['issues']))

    def test_declared_image_count_never_automatically_retries_review_failure(self):
        self.start(route='builtin', tasks=[self.task(image_count=1)])
        action = autopilot.next_task(self.root, 'synthetic-maker')
        self.assertTrue(action['external_submission_guard'])
        result = self.builtin(self.prepare())
        produced = autopilot.record(self.root, {'task_id': 'analysis', 'claim': action['claim'],
            'status': 'produced', 'artifacts': {'report': result['output_path']}})
        packet_path = state.resolve(self.root, produced['packet'])
        packet = state.read_json(packet_path)
        review.record(self.root, produced['packet'], {'packet_sha256': state.sha256(packet_path),
            'reviewer_id': 'synthetic-independent', 'method': 'independent_agent', 'source_versions': packet['versions'],
            'checks': [{'id': c['id'], 'verdict': 'changes_required', 'evidence': list(packet['artifacts']),
                        'note': 'Synthetic observed correction needed'} for c in packet['criteria']]})
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'waiting')
        self.assertEqual(autopilot.status(self.root)['tasks'][0]['status'], 'needs_revision')
        with self.assertRaisesRegex(ValueError, 'External'):
            autopilot.retry(self.root, 'analysis', 'Synthetic retry request cannot resubmit external work')

    def test_declared_image_requests_also_receive_external_retry_guard(self):
        self.start(tasks=[self.task(image_requests=[{'purpose': 'test', 'target_id': 'TEST', 'version': 'v001'}])])
        action = autopilot.next_task(self.root, 'synthetic-maker')
        self.assertTrue(action['external_submission_guard'])
        autopilot.record(self.root, {'task_id': 'analysis', 'claim': action['claim'],
                                    'status': 'failed', 'message': 'Synthetic actual external failure'})
        with self.assertRaisesRegex(ValueError, 'External'):
            autopilot.retry(self.root, 'analysis', 'Synthetic retry request')

    def test_legacy_new_image_dispatch_waits_until_configured(self):
        self.start(route='builtin', tasks=[self.task(image_count=1)])
        self.legacy()
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'waiting')
        self.configure(1)
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'produce')

    def test_cli_partial_limit_update_and_no_image_reserve_command(self):
        self.start(1)
        path = self.root / 'planning/limits.json'
        state.write_json(path, {'limits': {'max_images': 3, 'evidence': 'Synthetic actual extension'},
                               'video': {'sound': 'silent', 'evidence': 'Synthetic actual sound choice'}})
        args = courseware.parser().parse_args(['run-configure', '--project', str(self.root), '--settings', str(path)])
        result = courseware.execute(args)
        self.assertEqual(result['limits']['max_images'], 3)
        self.assertEqual(result['preferences']['video']['sound'], 'silent')
        self.assertNotIn('image-reserve', courseware.parser().format_help())

    def test_four_folder_course_budget_uses_existing_path_mapping(self):
        self.root = self.root.parent / ('b-layout-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic four folder budget', 'openai_image_api', layout='four-folders')
        state.resolve(self.root, self.source).write_text('Synthetic source', encoding='utf-8')
        self.start(1)
        batch = self.prepare()
        self.assertEqual(self.direct(batch)['status'], 'downloaded')
        with self.assertRaises(ValueError): self.direct(self.prepare('EXTRA'))
        self.assertEqual(self.summary()['used'], 1)
        self.assertTrue((self.root / '02_work/_state/automation').is_dir())
        self.assertFalse((self.root / '_state').exists())

    def test_legacy_missing_count_amendment_preserves_identity_and_unblocks_dependencies(self):
        cover = {**self.task('legacy-cover'), 'step': 'cover',
                 'outputs': ['cover1', 'cover2', 'cover3', 'cover4']}
        follow = self.task('after-cover', depends_on=['legacy-cover'])
        self.start(route='builtin', tasks=[cover, follow])
        self.legacy()
        original = store.load_run(self.root)
        self.configure(60)
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'waiting')
        before_ledger = store.load_run(self.root)['image_budget']
        settings = self.root / 'planning/legacy-count.json'
        declaration = {'task_id': 'legacy-cover', 'image_count': 4,
                       'evidence': 'Synthetic explicit future plan: four separate cover candidates'}
        state.write_json(settings, {'image_declarations': [declaration]})
        args = courseware.parser().parse_args(['run-configure', '--project', str(self.root), '--settings', str(settings)])
        courseware.execute(args)
        configured = store.load_run(self.root)
        self.assertEqual([t['spec'] for t in configured['tasks']], [cover, follow])
        self.assertEqual(configured['plan_digest'], original['plan_digest'])
        self.assertEqual(configured['image_budget'], before_ledger)
        self.assertEqual(configured['tasks'][0]['attempt'], 0)
        self.assertNotIn('claim', configured['tasks'][0])
        autopilot.start(self.root, self.plan)
        autopilot.extend(self.root, [cover, follow], 'Synthetic repeat of unchanged task definitions')
        with self.assertRaisesRegex(ValueError, 'Cannot rewrite'):
            autopilot.extend(self.root, [{**cover, 'image_count': 4}], 'Synthetic content rewrite remains disallowed')
        action = autopilot.next_task(self.root, 'synthetic-maker')
        self.assertEqual(action['task'], {**cover, 'image_count': 4})
        self.assertEqual(action['image_declaration']['evidence'], declaration['evidence'])
        self.assertTrue(action['external_submission_guard'])
        batch = prompts.prepare(self.root, {'tasks': [{'purpose': 'cover', 'target_id': 'COVER' + str(i),
            'prompt': 'Synthetic complete cover candidate'} for i in range(4)]})
        outputs = {role: self.builtin({'jobs': [path]})['output_path']
                   for role, path in zip(cover['outputs'], batch['jobs'])}
        produced = autopilot.record(self.root, {'task_id': cover['id'], 'claim': action['claim'],
            'status': 'produced', 'artifacts': outputs})
        packet_path = state.resolve(self.root, produced['packet'])
        packet = state.read_json(packet_path)
        review.record(self.root, produced['packet'], {'packet_sha256': state.sha256(packet_path),
            'reviewer_id': 'synthetic-independent', 'method': 'independent_agent', 'source_versions': packet['versions'],
            'checks': [{'id': c['id'], 'verdict': 'pass', 'evidence': list(packet['artifacts']),
                        'note': 'Synthetic independent observed images'} for c in packet['criteria']]})
        next_action = autopilot.next_task(self.root, 'synthetic-maker')
        self.assertEqual(next_action['task']['id'], follow['id'])
        self.assertEqual(next_action['task']['depends_on'], [cover['id']])
        self.assertEqual(self.summary()['used'], 4)
        self.assertTrue(self.summary()['history_unknown'])

    def test_legacy_future_count_amendment_checks_capacity_without_reset(self):
        self.start(2, route='builtin', tasks=[{**self.task('legacy-cover'), 'step': 'cover'}])
        self.builtin(self.prepare())
        ledger = store.load_run(self.root)['image_budget']
        autopilot.configure(self.root, {'image_declarations': [
            {'task_id': 'legacy-cover', 'image_count': 4, 'evidence': 'Synthetic known four future covers'}]})
        self.assertEqual(store.load_run(self.root)['image_budget'], ledger)
        action = autopilot.next_task(self.root, 'host')
        self.assertEqual(action['action'], 'waiting')
        self.assertTrue(any('requested 4, remaining 1' in issue for issue in action['blocked'][0]['issues']))
        self.configure(5)
        self.assertEqual(autopilot.next_task(self.root, 'host')['task']['image_count'], 4)
        self.assertEqual(self.summary()['used'], 1)

    def test_legacy_count_amendment_requires_image_consent_and_external_retry_guard(self):
        autopilot.start(self.root, {'activation_evidence': 'Synthetic actual auto request',
            'tasks': [self.task('legacy-image', requires_preferences=[])]})
        autopilot.configure(self.root, {'image_declarations': [
            {'task_id': 'legacy-image', 'image_count': 1, 'evidence': 'Synthetic planned image quantity'}]})
        action = autopilot.next_task(self.root, 'host')
        self.assertEqual(action['action'], 'waiting')
        self.assertTrue(any('image.authorization' in issue for issue in action['blocked'][0]['issues']))
        autopilot.configure(self.root, {'image': {'route': 'builtin', 'evidence': 'Synthetic actual route',
            'authorization': {'scope': 'run', 'purposes': ['erase'], 'paid_generation': False,
                              'scope_evidence': 'Synthetic actual specific generation consent'}}})
        action = autopilot.next_task(self.root, 'host')
        self.assertTrue(action['external_submission_guard'])
        self.assertEqual(action['task']['image_count'], 1)
        autopilot.record(self.root, {'task_id': 'legacy-image', 'claim': action['claim'],
                                    'status': 'failed', 'message': 'Synthetic actual external failure'})
        with self.assertRaisesRegex(ValueError, 'External'):
            autopilot.retry(self.root, 'legacy-image', 'Synthetic retry request does not authorize resubmission')

    def test_legacy_count_amendment_rejects_invalid_input_atomically(self):
        self.start(tasks=[self.task('missing'), self.task('declared', image_count=1),
            self.task('requested', image_requests=[{'purpose': 'test', 'target_id': 'ONE', 'version': 'v001'}])])
        valid = {'task_id': 'missing', 'image_count': 4, 'evidence': 'Synthetic actual future count'}
        invalid = [None, {}, [], [valid, valid], [{**valid, 'task_id': 'unknown'}],
            [{**valid, 'task_id': 'declared'}], [{**valid, 'task_id': 'requested'}],
            [{**valid, 'evidence': ''}], [{**valid, 'evidence': None}],
            [{**valid, 'instruction': 'Unsupported content rewrite'}],
            [valid, {'task_id': 'unknown', 'image_count': 1, 'evidence': 'Synthetic'}]]
        invalid += [[{**valid, 'image_count': value}] for value in [0, -1, True, '4', 1.5]]
        before = self.run_path().read_bytes()
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                autopilot.configure(self.root, {'image_declarations': value,
                    'limits': {'max_images': 61, 'evidence': 'Synthetic combined update'},
                    'video': {'sound': 'silent', 'evidence': 'Synthetic combined preference update'}})
            self.assertEqual(self.run_path().read_bytes(), before)
        autopilot.configure(self.root, {'image_declarations': [valid]})
        after = self.run_path().read_bytes()
        with self.assertRaises(ValueError): autopilot.configure(self.root, {'image_declarations': [{**valid, 'image_count': 3}]})
        self.assertEqual(self.run_path().read_bytes(), after)

    def test_legacy_count_amendment_rejects_claimed_completed_and_previous_attempts(self):
        self.start(tasks=[self.task()])
        original = store.load_run(self.root)
        cases = [{'status': 'running', 'attempt': 1, 'claim': 'synthetic-existing-claim'},
                 {'status': 'done', 'attempt': 1}, {'status': 'pending', 'attempt': 1},
                 {'status': 'pending', 'claim': 'synthetic-old-claim'},
                 {'status': 'pending', 'history': [{'claim': 'synthetic-old-claim'}]}]
        for changes in cases:
            with self.subTest(changes=changes):
                data = {**original, 'tasks': [{**original['tasks'][0], **changes}]}
                state.write_json(self.run_path(), data)
                before = self.run_path().read_bytes()
                with self.assertRaises(ValueError):
                    autopilot.configure(self.root, {'image_declarations': [
                        {'task_id': 'analysis', 'image_count': 1, 'evidence': 'Synthetic unsupported later declaration'}]})
                self.assertEqual(self.run_path().read_bytes(), before)

    def test_legacy_count_amendment_without_run_creates_nothing(self):
        before = sorted(str(path) for path in self.root.rglob('*'))
        with self.assertRaises(ValueError):
            autopilot.configure(self.root, {'image_declarations': [
                {'task_id': 'unknown', 'image_count': 1, 'evidence': 'Synthetic no-run declaration'}]})
        self.assertEqual(sorted(str(path) for path in self.root.rglob('*')), before)


if __name__ == '__main__': unittest.main()
