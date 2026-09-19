import io
from pathlib import Path
import sys
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import patch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
from runtime import state, prompts
try:
    from runtime import image_api
except ImportError:
    image_api = None


class Transport:
    def __init__(self, submit=None, fail_download=False):
        self.posts = []
        self.gets = []
        self.submit = submit
        self.fail_download = fail_download

    def post(self, endpoint, payload, timeout):
        self.posts.append((endpoint, payload))
        if endpoint.endswith('completions'):
            if isinstance(self.submit, Exception):
                raise self.submit
            return self.submit or {'code': 0, 'data': {'id': 'provider-test-id', 'status': 'running'}}
        return {'code': 0, 'data': {'id': 'provider-test-id', 'status': 'succeeded',
                'results': [{'url': 'https://example.com/synthetic.png'}]}}

    def download(self, url, timeout):
        self.gets.append(url)
        if self.fail_download:
            raise TimeoutError('synthetic download failure')
        out = io.BytesIO()
        Image.new('RGB', (32, 18), 'white').save(out, format='PNG')
        return out.getvalue()


class ImageApiTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(image_api, 'image API runtime must exist')
        self.root = ROOT / 'tests/runs' / ('api-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic test only', 'openai_image_api')
        self.batch = prompts.prepare(self.root, {'tasks': [{'purpose': 'test', 'target_id': 'TEST001',
            'prompt': 'Synthetic complex image test, no live API'}], 'authorization_evidence': 'Synthetic fixture only'})
        self.path = self.root / self.batch['jobs'][0]

    def run_job(self, transport, resume=False):
        return image_api.run_job(self.root, self.batch['jobs'][0], transport=transport,
                                 resume=resume, timeout=1, poll_interval=0)

    def test_real_payload_mapping_and_reference_bytes(self):
        ref = self.root / 'assets/ref.png'
        Image.new('RGB', (16, 9), 'red').save(ref)
        job = state.read_json(self.path)
        job['references'] = [{'path': 'assets/ref.png', 'sha256': state.sha256(ref)}]
        payload = image_api.build_payload(self.root, job)
        self.assertEqual(payload['model'], 'gpt-image-2.5')
        self.assertEqual(payload['aspectRatio'], '1672x941')
        self.assertIs(payload['shutProgress'], True)
        self.assertNotIn('size', payload)
        self.assertTrue(payload['urls'][0].startswith('data:image/png;base64,'))

    def test_task_id_resumes_without_second_generation(self):
        t = Transport()
        result = self.run_job(t)
        self.assertEqual(result['status'], 'downloaded')
        self.assertEqual(result['width_px'], 32)
        self.assertFalse(result['size_matches_request'])
        self.assertEqual([x[0] for x in t.posts].count('/v1/draw/completions'), 1)
        self.run_job(t, resume=True)
        self.assertEqual([x[0] for x in t.posts].count('/v1/draw/completions'), 1)
        self.assertEqual(len(t.gets), 1)

    def test_download_retry_does_not_resubmit(self):
        t = Transport(fail_download=True)
        self.assertEqual(self.run_job(t)['status'], 'download_failed')
        t.fail_download = False
        self.assertEqual(self.run_job(t, resume=True)['status'], 'downloaded')
        self.assertEqual([x[0] for x in t.posts].count('/v1/draw/completions'), 1)

    def test_unknown_submission_is_not_retried_or_logged_verbatim(self):
        secret = 'synthetic-secret-never-save'
        t = Transport(TimeoutError(secret))
        self.assertEqual(self.run_job(t)['status'], 'submission_unknown')
        self.run_job(t, resume=True)
        self.assertEqual(len(t.posts), 1)
        for path in self.root.rglob('*.json'):
            self.assertNotIn(secret, path.read_text(encoding='utf-8'))

    def test_single_test_cannot_contain_production_batch(self):
        with self.assertRaises(ValueError):
            prompts.prepare(self.root, {'tasks': [{'purpose': 'test', 'target_id': 'TEST2'},
                                                {'purpose': 'page', 'target_id': 'P001'}]})

    def test_pending_formal_job_checks_current_scope_before_submission(self):
        job = state.read_json(self.path)
        job.update(purpose='page', target_id='P001')
        state.write_json(self.path, job)
        transport = Transport()
        with self.assertRaisesRegex(ValueError, 'workflow|Workflow|scope|mode'):
            self.run_job(transport)
        self.assertEqual(transport.posts, [])
        self.assertEqual(state.read_json(self.path)['status'], 'pending')

    def test_pending_resume_never_submits_or_requires_new_scope(self):
        job = state.read_json(self.path)
        job.update(purpose='page', target_id='P001')
        state.write_json(self.path, job)
        transport = Transport()
        self.assertEqual(self.run_job(transport, resume=True)['status'], 'pending')
        self.assertEqual(transport.posts, [])

    def test_builtin_old_result_is_retained_with_stale_inputs(self):
        project = state.load_project(self.root)
        project['image_route'] = 'builtin'
        state.write_json(self.root / '_state/project.json', project)
        batch = prompts.prepare(self.root, {'tasks': [
            {'purpose': 'test', 'target_id': 'BUILTIN_OLD', 'prompt': 'Synthetic old result'}]})
        relative = batch['jobs'][0]
        job = state.read_json(self.root / relative)
        basis = '_state/pages.json'
        job['input_versions'] = {basis: state.sha256(self.root / basis)}
        state.write_json(self.root / relative, job)
        state.write_json(self.root / basis, {'pages': [{'page_id': 'P009'}]})
        source = self.root / 'slides/builtin-old.png'
        Image.new('RGB', (32, 18), 'white').save(source)
        result = image_api.register_builtin(self.root, {
            'job_path': relative, 'input_digest': job['input_digest'], 'image_path': str(source),
            'tool_evidence': 'Synthetic retained old response, not a new generation approval'})
        self.assertEqual(result['status'], 'downloaded')
        self.assertIn(basis, result.get('stale_inputs', []))
        self.assertEqual(result['review_status'], 'pending_visual_review')

    def test_submitted_task_can_download_old_version_after_upstream_change(self):
        job = state.read_json(self.path)
        basis = '_state/pages.json'
        job.update(status='running', task_id='provider-test-id',
                   input_versions={basis: state.sha256(self.root / basis)})
        state.write_json(self.path, job)
        state.write_json(self.root / basis, {'pages': [{'page_id': 'P009'}]})
        t = Transport()
        result = self.run_job(t, resume=True)
        self.assertEqual(result['status'], 'downloaded')
        self.assertIn(basis, result['stale_inputs'])
        self.assertEqual([x[0] for x in t.posts], ['/v1/draw/result'])

    def test_concurrent_workers_cannot_submit_one_job_twice(self):
        started, release = threading.Event(), threading.Event()
        class SlowTransport(Transport):
            def post(inner, endpoint, payload, timeout):
                if endpoint.endswith('completions'):
                    started.set()
                    release.wait(5)
                return super().post(endpoint, payload, timeout)
        t = SlowTransport()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.run_job, t)
            self.assertTrue(started.wait(5))
            try:
                with self.assertRaisesRegex(ValueError, 'already being executed'):
                    self.run_job(t)
            finally:
                release.set()
            first.result()
        self.assertEqual([x[0] for x in t.posts].count('/v1/draw/completions'), 1)

    def test_route_switch_still_allows_retrieval_of_paid_old_job(self):
        job = state.read_json(self.path)
        job.update(status='running', task_id='provider-test-id')
        state.write_json(self.path, job)
        project = state.load_project(self.root)
        project['image_route'] = 'builtin'
        state.write_json(self.root / '_state/project.json', project)
        t = Transport()
        with patch.object(image_api, 'HttpTransport', lambda key: t):
            result = image_api.run_batch(self.root, self.batch, 'synthetic', resume=True)
        self.assertEqual(result['results'][0]['status'], 'downloaded')
        self.assertNotIn('/v1/draw/completions', [x[0] for x in t.posts])

    def test_default_page_cannot_silently_switch_to_vip_model(self):
        job = state.read_json(self.path)
        job['image_api_input']['model'] = 'gpt-image-2-vip'
        with self.assertRaises(ValueError):
            image_api.build_payload(self.root, job)

    def test_builtin_result_has_real_dimensions_and_rejects_changed_prompt(self):
        data = state.load_project(self.root)
        data['image_route'] = 'builtin'
        state.write_json(self.root / '_state/project.json', data)
        batch = prompts.prepare(self.root, {'tasks': [{'purpose': 'test', 'target_id': 'BUILTIN', 'prompt': '合成测试'}]})
        path = batch['jobs'][0]
        job = state.read_json(self.root / path)
        source = self.root / 'slides/builtin-synthetic.png'
        Image.new('RGB', (64, 36), 'white').save(source)
        evidence = {'job_path': path, 'input_digest': job['input_digest'], 'image_path': str(source),
                    'tool_evidence': 'Synthetic image; no real tool call in this test'}
        result = image_api.register_builtin(self.root, evidence)
        self.assertEqual((result['width_px'], result['height_px']), (64, 36))
        self.assertEqual(result['sha256'], state.sha256(source))
        (self.root / job['prompt_path']).write_text('changed', encoding='utf-8')
        with self.assertRaises(ValueError):
            image_api.register_builtin(self.root, evidence)


if __name__ == '__main__':
    unittest.main()
