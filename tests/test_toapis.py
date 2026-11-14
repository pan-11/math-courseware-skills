"""Offline protocol and resume tests; no real credentials or network calls."""
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
from runtime import image_api, image_toapis, prompts, state


class FakeTransport:
    key = 'synthetic-test-credential'

    def __init__(self, submit=None, fail_download=False):
        self.posts, self.queries, self.uploads, self.gets = [], [], [], []
        self.submit = submit
        self.fail_submit = False
        self.fail_download = fail_download

    def post(self, endpoint, payload, timeout):
        self.posts.append((endpoint, payload))
        if self.fail_submit:
            raise TimeoutError(self.key)
        if isinstance(self.submit, Exception):
            raise self.submit
        if endpoint == image_toapis.ENDPOINT:
            return self.submit or {'id': 'task_offline_1', 'status': 'completed',
                                   'result': {'data': [{'url': 'https://example.com/result.png'}]}}
        return {'data': {'id': 'legacy_1', 'status': 'succeeded',
                         'results': [{'url': 'https://example.com/legacy.png'}]}}

    def query(self, task_id, timeout):
        self.queries.append(task_id)
        return {'id': task_id, 'status': 'completed',
                'result': {'data': [{'url': 'https://example.com/result.png'}]}}

    def upload(self, path, timeout):
        self.uploads.append(path)
        return 'https://example.com/reference.png'

    def download(self, url, timeout):
        self.gets.append(url)
        if self.fail_download:
            raise TimeoutError('Synthetic download timeout')
        out = io.BytesIO()
        Image.new('RGB', (32, 18), 'white').save(out, format='PNG')
        return out.getvalue()


class ToapisTests(unittest.TestCase):
    def setUp(self):
        self.network = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No live network in tests'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.project = ROOT / 'tests/runs' / ('toapis-' + uuid.uuid4().hex)
        configuration = patch.object(image_toapis, 'SETTINGS', self.project / 'synthetic-settings.json')
        configuration.start()
        self.addCleanup(configuration.stop)
        state.init_project(self.project, 'Offline adapter fixture', 'openai_image_api')
        self.batch = prompts.prepare(self.project, {'tasks': [
            {'purpose': 'test', 'target_id': 'TEST001', 'prompt': 'Offline fixture only'}],
            'authorization_evidence': 'Offline synthetic test only'})
        self.relative = self.batch['jobs'][0]
        self.path = state.resolve(self.project, self.relative)

    def job(self):
        return state.read_json(self.path)

    def run_job(self, transport, resume=False):
        return image_api.run_job(self.project, self.relative, transport, resume, timeout=1, poll_interval=0)

    def test_default_payload_matches_documented_fields(self):
        job = self.job()
        self.assertEqual(job['provider'], 'toapis')
        self.assertEqual(self.batch['provider'], 'toapis')
        self.assertEqual(image_api.build_payload(self.project, job), {
            'model': 'gpt-image-2-vip', 'quality': 'low', 'resolution': '1k', 'size': '16:9',
            'prompt': 'Offline fixture only', 'n': 1, 'response_format': 'url'})

    def test_optional_workspace_settings_and_environment_key(self):
        settings_file = image_toapis.SETTINGS
        settings_file.write_text('{"base_url":"https://toapis.com","quality":"medium"}', encoding='utf-8')
        options = image_toapis.job_options({}, {}, '1672x941')
        self.assertEqual((options['base_url'], options['quality'], options['resolution']),
                         ('https://toapis.com', 'medium', '1k'))
        self.assertEqual(self.job()['image_api_input']['base_url'], 'https://toapis.cn')
        with patch.dict(os.environ, {'TOAPIS_API_KEY': 'synthetic-env-key'}):
            self.assertEqual(image_api.read_key(self.project, provider='toapis'), 'synthetic-env-key')

    def test_options_can_change_for_future_tasks(self):
        options = image_toapis.job_options({'api_options': {'quality': 'medium', 'resolution': '2k'}},
            {'api_options': {'model': 'gpt-image-2', 'resolution': '4k'}}, '1024x1024')
        self.assertEqual((options['model'], options['quality'], options['resolution'], options['size']),
                         ('gpt-image-2', 'medium', '4k', '1:1'))
        self.assertEqual(self.job()['image_api_input']['resolution'], '1k')
        with self.assertRaises(ValueError):
            image_toapis.job_options({'api_options': {'quality': 'invalid'}}, {}, '1024x1024')

    def test_reference_upload_precedes_generation_and_contains_no_base64(self):
        ref = self.project / 'assets/reference.png'
        Image.new('RGB', (16, 9), 'red').save(ref)
        job = self.job()
        job['references'] = [{'path': 'assets/reference.png', 'sha256': state.sha256(ref)}]
        state.write_json(self.path, job)
        transport = FakeTransport()
        result = self.run_job(transport)
        self.assertEqual(result['status'], 'downloaded')
        self.assertEqual(transport.uploads, [ref])
        body = transport.posts[0][1]
        self.assertEqual(body['reference_images'], ['https://example.com/reference.png'])
        self.assertNotIn('urls', body)
        self.assertNotIn('base64', json.dumps(body))
        self.assertNotIn(transport.key, self.path.read_text(encoding='utf-8'))

    def test_resume_queries_existing_id_without_resubmitting(self):
        job = self.job()
        job.update(status='running', task_id='task_offline_1')
        state.write_json(self.path, job)
        transport = FakeTransport()
        result = self.run_job(transport, resume=True)
        self.assertEqual(result['status'], 'downloaded')
        self.assertEqual(transport.posts, [])
        self.assertEqual(transport.queries, ['task_offline_1'])
        self.assertIsNone(result['size_matches_request'])
        self.assertTrue(result['aspect_ratio_matches_request'])
        self.assertEqual(result['requested_resolution'], '1k')

    def test_unknown_submission_never_retries_or_leaks_secret(self):
        transport = FakeTransport()
        transport.fail_submit = True
        self.assertEqual(self.run_job(transport)['status'], 'submission_unknown')
        self.run_job(transport, resume=True)
        self.assertEqual(len(transport.posts), 1)
        self.assertNotIn(transport.key, self.path.read_text(encoding='utf-8'))

    def test_download_retry_does_not_generate_again(self):
        transport = FakeTransport()
        transport.fail_download = True
        self.assertEqual(self.run_job(transport)['status'], 'download_failed')
        transport.fail_download = False
        self.assertEqual(self.run_job(transport, resume=True)['status'], 'downloaded')
        self.assertEqual(len(transport.posts), 1)

    def test_pending_resume_does_not_submit(self):
        transport = FakeTransport()
        self.assertEqual(self.run_job(transport, resume=True)['status'], 'pending')
        self.assertEqual(transport.posts, [])

    def test_legacy_grsai_recovery_uses_original_protocol(self):
        job = self.job()
        job.update(provider='grsai', status='running', task_id='legacy_1',
                   image_api_input={'size': '1672x941'})
        state.write_json(self.path, job)
        transport = FakeTransport()
        result = self.run_job(transport, resume=True)
        self.assertEqual(result['status'], 'downloaded')
        self.assertEqual(transport.posts[0], ('/v1/draw/result', {'id': 'legacy_1'}))
        self.assertEqual(transport.queries, [])

    def test_mismatched_provider_is_rejected_before_execution(self):
        with self.assertRaisesRegex(ValueError, 'provider'):
            image_api.validate_batch(self.project, {**self.batch, 'provider': 'grsai'})

    def test_changed_prompt_and_reference_are_rejected(self):
        job = self.job()
        state.resolve(self.project, job['prompt_path']).write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Prompt changed'):
            image_api.build_payload(self.project, job)

    def test_modified_reference_is_rejected_before_upload(self):
        ref = self.project / 'assets/changed.png'
        Image.new('RGB', (16, 9), 'red').save(ref)
        job = self.job()
        job['references'] = [{'path': 'assets/changed.png', 'sha256': state.sha256(ref)}]
        Image.new('RGB', (16, 9), 'blue').save(ref)
        with self.assertRaisesRegex(ValueError, 'Reference changed'):
            image_api.build_payload(self.project, job)

    def test_batch_dispatches_to_toapis_with_snapshotted_origin(self):
        transport = FakeTransport()
        with patch.object(image_toapis, 'HttpTransport', return_value=transport) as factory:
            result = image_api.run_batch(self.project, self.batch, 'synthetic-test-credential')
        factory.assert_called_once_with('synthetic-test-credential', 'https://toapis.cn')
        self.assertEqual(result['results'][0]['status'], 'downloaded')
        self.assertEqual(transport.posts[0][0], '/v1/images/generations')

    def test_failed_and_malformed_task_responses(self):
        self.assertEqual(image_toapis.parse_response({'id': 'task_x', 'status': 'failed'})['status'], 'failed')
        for payload in ({'id': 'x', 'status': 'unknown'}, {'id': 'x', 'status': 'completed'},
                        {'id': 123, 'status': 'queued'}):
            with self.assertRaises(ValueError):
                image_toapis.parse_response(payload)

    def test_http_headers_methods_upload_and_no_auth_on_download(self):
        transport = image_toapis.HttpTransport('offline-bearer', 'https://toapis.cn')
        class Response:
            def __init__(self, payload): self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return json.dumps(self.payload).encode()
        with patch('urllib.request.build_opener') as build:
            opener = build.return_value
            opener.open.return_value = Response({'id': 'task_x', 'status': 'queued'})
            transport.post(image_toapis.ENDPOINT, {'model': 'gpt-image-2-vip'}, 1)
            req = opener.open.call_args.args[0]
            self.assertEqual(req.full_url, 'https://toapis.cn/v1/images/generations')
            self.assertEqual(req.get_method(), 'POST')
            self.assertEqual(req.get_header('Authorization'), 'Bearer offline-bearer')
            self.assertEqual(req.get_header('Content-type'), 'application/json')
            transport.query('task_x', 1)
            req = opener.open.call_args.args[0]
            self.assertEqual(req.get_method(), 'GET')
            self.assertTrue(req.full_url.endswith('/task_x'))
            ref = self.project / 'assets/http-ref.png'
            Image.new('RGB', (2, 2)).save(ref)
            opener.open.return_value = Response({'success': True, 'data': {'url': 'https://example.com/ref.png'}})
            transport.upload(ref, 1)
            req = opener.open.call_args.args[0]
            self.assertTrue(req.full_url.endswith('/v1/uploads/images'))
            self.assertIn(b'name="file"', req.data)
            self.assertNotIn(str(ref).encode(), req.data)
            transport.download('https://example.com/result.png', 1)
            self.assertEqual(opener.open.call_args.args[0], 'https://example.com/result.png')

    def test_credential_response_is_discarded(self):
        transport = image_toapis.HttpTransport('synthetic-sensitive', 'https://toapis.cn')
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"message":"synthetic-sensitive"}'
        with patch('urllib.request.build_opener') as build:
            build.return_value.open.return_value = Response()
            with self.assertRaisesRegex(ValueError, 'discarded'):
                transport.query('task_x', 1)

    def test_real_secret_path_is_only_configuration(self):
        with patch.object(Path, 'read_text', return_value='offline-secret\n') as read:
            # Explicit synthetic key file: never open the user's real file.
            self.assertEqual(image_api.read_key(self.project, ROOT / 'tests/synthetic-key', provider='toapis'),
                             'offline-secret')
            self.assertEqual(read.call_args.kwargs['encoding'], 'utf-8-sig')


if __name__ == '__main__':
    unittest.main()
