"""Synthetic Duomi protocol checks; no live provider calls or real credentials."""
import base64
import io
import json
import os
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
from runtime import state, prompts, image_api
try:
    from runtime import image_providers
except ImportError:
    image_providers = None


class Transport:
    def __init__(self, raw, submit=None):
        self.raw, self.submit = raw, submit
        self.posts, self.queries, self.downloads = [], [], []

    def post(self, endpoint, payload, timeout):
        self.posts.append((endpoint, payload))
        if isinstance(self.submit, Exception): raise self.submit
        return self.submit or {'id': 'synthetic-task'}

    def get(self, endpoint, timeout):
        self.queries.append(endpoint)
        return {'id': 'synthetic-task', 'state': 'succeeded',
                'data': {'images': [{'url': 'https://example.com/result.png'}]}}

    def download(self, url, timeout):
        self.downloads.append(url)
        return self.raw


class DuomiApiTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs' / ('duomi-' + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        (self.root / 'AGENTS.md').write_text(
            '# Synthetic Duomi verification\nOnly mocked requests and generated test images; retain all outputs.\n',
            encoding='utf-8')
        self.root = self.root / 'project'
        state.init_project(self.root, 'Synthetic Duomi', 'openai_image_api', api_provider='grsai')
        self.batch = prompts.prepare(self.root, {'tasks': [{'purpose': 'test', 'target_id': 'DUOMI',
            'prompt': 'Synthetic ordered references'}], 'authorization_evidence': 'Synthetic fixture only'})
        self.path = self.root / self.batch['jobs'][0]
        out = io.BytesIO()
        Image.new('RGB', (32, 18), 'blue').save(out, 'PNG')
        self.raw = out.getvalue()
        self.ref = self.root / 'assets/reference.png'
        self.ref.write_bytes(self.raw)

    def duomi_job(self, references=True):
        self.assertIsNotNone(image_providers, 'provider settings must be implemented')
        job = state.read_json(self.path)
        job.update(provider='duomi', image_api_input=image_providers.make_input('duomi', None, None))
        if references:
            job['references'] = [{'path': 'assets/reference.png', 'sha256': state.sha256(self.ref),
                'provider_urls': {'duomi': 'https://example.com/reference.png'}}]
        state.write_json(self.path, job)
        return job

    def run_job(self, transport, resume=False):
        return image_api.run_job(self.root, self.batch['jobs'][0], transport,
                                 resume=resume, timeout=1, poll_interval=0)

    def test_payload_uses_documented_fields_and_reference_urls(self):
        job = self.duomi_job()
        payload = image_api.build_payload(self.root, job)
        self.assertEqual(payload, {'model': 'gpt-image-2', 'prompt': 'Synthetic ordered references',
            'size': '1792x1008', 'quality': 'medium', 'background': 'auto',
            'image': ['https://example.com/reference.png']})

    def test_local_reference_is_sent_unchanged_without_remote_reference_download(self):
        job = self.duomi_job()
        job['references'][0].pop('provider_urls')
        state.write_json(self.path, job)
        transport = Transport(self.raw)
        self.assertEqual(self.run_job(transport)['status'], 'downloaded')
        self.assertEqual(transport.downloads, ['https://example.com/result.png'])
        image = transport.posts[0][1]['image'][0]
        self.assertTrue(image.startswith('data:image/png;base64,'))
        self.assertEqual(base64.b64decode(image.split(',', 1)[1]), self.raw)

    def test_mixed_references_keep_order_and_detect_mime_from_original_bytes(self):
        job = self.duomi_job()
        png = self.root / 'assets/png-with-jpeg-extension.jpg'
        png.write_bytes(self.raw)
        output = io.BytesIO()
        Image.new('RGB', (48, 32), 'red').save(output, 'JPEG')
        jpeg_raw = output.getvalue()
        jpeg = self.root / 'assets/jpeg-with-png-extension.png'
        jpeg.write_bytes(jpeg_raw)
        job['references'] = [
            {'path': state.relative_path(self.root, png), 'sha256': state.sha256(png)},
            job['references'][0],
            {'path': state.relative_path(self.root, jpeg), 'sha256': state.sha256(jpeg),
             'provider_urls': {'grsai': 'https://example.com/unrelated.png'}}]
        images = image_api.build_payload(self.root, job)['image']
        self.assertEqual(images, ['data:image/png;base64,' + base64.b64encode(self.raw).decode('ascii'),
            'https://example.com/reference.png',
            'data:image/jpeg;base64,' + base64.b64encode(jpeg_raw).decode('ascii')])
        transport = Transport(self.raw)
        image_api._verify_duomi_references(job, transport, 1)
        self.assertEqual(transport.downloads, ['https://example.com/reference.png'])

    def test_explicit_invalid_duomi_url_cannot_fall_back_to_local_bytes(self):
        for url in (None, '', 'http://example.com/reference.png',
                    'data:image/png;base64,' + base64.b64encode(self.raw).decode('ascii')):
            with self.subTest(url=url):
                job = self.duomi_job()
                job['references'][0]['provider_urls']['duomi'] = url
                state.write_json(self.path, job)
                transport = Transport(self.raw)
                with patch.object(image_api.image_budget, 'reserve_api') as reserve:
                    with self.assertRaisesRegex(ValueError, 'HTTPS|provider_urls'):
                        self.run_job(transport)
                reserve.assert_not_called()
                self.assertEqual(transport.posts, [])
                self.assertEqual(transport.downloads, [])

    def test_invalid_local_reference_stops_before_reservation_or_submission(self):
        invalid = self.root / 'assets/not-an-image.png'
        invalid.write_bytes(b'synthetic invalid image')
        for ref, expected in (
                ({'path': 'assets/missing.png', 'sha256': state.sha256(self.ref)}, FileNotFoundError),
                ({'path': 'assets/reference.png', 'sha256': '0' * 64}, ValueError),
                ({'path': state.relative_path(self.root, invalid), 'sha256': state.sha256(invalid)}, OSError)):
            with self.subTest(path=ref['path'], expected=expected.__name__):
                job = self.duomi_job()
                job['references'] = [ref]
                state.write_json(self.path, job)
                transport = Transport(self.raw)
                with patch.object(image_api.image_budget, 'reserve_api') as reserve:
                    with self.assertRaises(expected):
                        self.run_job(transport)
                reserve.assert_not_called()
                self.assertEqual(transport.posts, [])
                self.assertEqual(transport.downloads, [])

    def test_reference_url_content_must_match_before_budget_or_submission(self):
        self.duomi_job()
        transport = Transport(b'not-the-local-image')
        with patch.object(image_api.image_budget, 'reserve_api') as reserve:
            with self.assertRaisesRegex(ValueError, 'Reference URL.*match'):
                self.run_job(transport)
        reserve.assert_not_called()
        self.assertEqual(transport.posts, [])
        self.assertEqual(state.read_json(self.path)['status'], 'pending')

    def test_create_query_download_and_resume_never_recreates(self):
        self.duomi_job()
        transport = Transport(self.raw)
        result = self.run_job(transport)
        self.assertEqual(result['status'], 'downloaded')
        self.assertEqual(result['provider'], 'duomi')
        self.assertEqual(result['api_base_url'], 'https://duomiapi.com')
        self.assertEqual(transport.queries, ['/v1/tasks/synthetic-task'])
        self.assertEqual(transport.downloads, ['https://example.com/reference.png', 'https://example.com/result.png'])
        self.run_job(transport, True)
        self.assertEqual(len(transport.posts), 1)

    def test_submission_unknown_is_not_retried(self):
        self.duomi_job(False)
        transport = Transport(self.raw, TimeoutError('synthetic timeout'))
        self.assertEqual(self.run_job(transport)['status'], 'submission_unknown')
        self.run_job(transport, True)
        self.assertEqual(len(transport.posts), 1)

    def test_unknown_query_state_stops_and_retains_the_task_id(self):
        self.duomi_job(False)
        transport = Transport(self.raw)
        with patch.object(transport, 'get', return_value={'id': 'synthetic-task', 'state': 'unrecognized'}) as query:
            result = self.run_job(transport)
        self.assertEqual(result['status'], 'running')
        self.assertEqual(result['task_id'], 'synthetic-task')
        self.assertEqual(result['error_code'], 'query_ValueError')
        query.assert_called_once()
        self.assertEqual(self.run_job(transport, True)['status'], 'downloaded')
        self.assertEqual(len(transport.posts), 1)

    def test_failed_download_retries_only_the_existing_result(self):
        self.duomi_job(False)
        transport = Transport(self.raw)
        with patch.object(transport, 'download', side_effect=TimeoutError('synthetic')):
            self.assertEqual(self.run_job(transport)['status'], 'download_failed')
        self.assertEqual(self.run_job(transport, True)['status'], 'downloaded')
        self.assertEqual(len(transport.posts), 1)
        self.assertEqual(len(transport.queries), 1)

    def test_documented_query_states_and_invalid_success(self):
        for status in ('pending', 'running'):
            self.assertEqual(image_api.parse_duomi_response({'id': 'fake', 'state': status}, True)['status'], 'running')
        self.assertEqual(image_api.parse_duomi_response({'id': 'fake', 'state': 'error'}, True)['status'], 'failed')
        for payload in ({'id': 'fake'}, {'id': '../other', 'state': 'running'},
                        {'id': 'fake', 'state': 'succeeded', 'data': {'images': []}}):
            with self.assertRaises(ValueError): image_api.parse_duomi_response(payload, True)

    def test_legacy_grsai_input_and_missing_provider_stay_compatible(self):
        job = state.read_json(self.path)
        job.pop('provider', None)
        state.write_json(self.path, job)
        self.assertEqual(image_api.batch_provider(self.root, self.batch), 'grsai')
        self.assertEqual(image_providers.make_input(), {'endpoint': '/v1/draw/completions',
            'model': 'gpt-image-2.5', 'size': '1672x941', 'aspectRatio': '1672x941', 'shutProgress': True})
        self.assertNotIn('provider', image_providers.make_input())

    def test_mixed_provider_batch_is_rejected_before_transport_construction(self):
        first = dict(self.batch)
        second = prompts.prepare(self.root, {'tasks': [{'purpose': 'test', 'target_id': 'LEGACY',
            'prompt': 'Synthetic second job'}], 'authorization_evidence': 'Synthetic fixture only'})
        self.duomi_job(False)
        first['jobs'] += second['jobs']
        with patch.object(image_api, 'DuomiTransport') as transport:
            with self.assertRaisesRegex(ValueError, 'one recorded provider'):
                image_api.run_batch(self.root, first, 'synthetic')
        transport.assert_not_called()

    def test_active_batch_verifies_all_references_before_any_reservation(self):
        from runtime import autopilot
        from workflow_fixture import enable_modules
        enable_modules(self.root, ['analyze', 'plan', 'editable'])
        (self.root / 'planning/source.md').write_text('Synthetic only', encoding='utf-8')
        autopilot.start(self.root, {'activation_evidence': 'Synthetic run',
            'preferences': {'image': {'route': 'openai_image_api', 'provider': 'duomi',
                'evidence': 'Synthetic Duomi choice', 'authorization': {'scope': 'run',
                    'purposes': ['test'], 'paid_generation': True, 'include_rework': True,
                    'scope_evidence': 'Synthetic paid consent'}}},
            'tasks': [{'id': 'analysis', 'step': 'analysis', 'inputs': ['planning/source.md'],
                       'outputs': ['report'], 'instruction': 'Synthetic task'}]})
        self.duomi_job()
        transport = Transport(b'wrong-image')
        with patch.object(image_api, 'DuomiTransport', return_value=transport), \
                patch.object(image_api.image_budget, 'reserve_api') as reserve:
            with self.assertRaisesRegex(ValueError, 'Reference URL.*match'):
                image_api.run_batch(self.root, self.batch, 'synthetic')
        reserve.assert_not_called()
        self.assertEqual(transport.posts, [])

    def test_saved_provider_controls_resume_after_selection_change(self):
        job = self.duomi_job(False)
        job.update(status='running', task_id='synthetic-task')
        state.write_json(self.path, job)
        project = state.load_project(self.root)
        project.update(image_route='builtin', image_provider='grsai')
        state.write_json(self.root / '_state/project.json', project)
        transport = Transport(self.raw)
        with patch.object(image_api, 'DuomiTransport', return_value=transport), \
                patch.object(image_api, 'HttpTransport', side_effect=AssertionError('wrong provider')):
            result = image_api.run_batch(self.root, self.batch, 'synthetic-key', resume=True)
        self.assertEqual(result['results'][0]['status'], 'downloaded')
        self.assertEqual(transport.posts, [])

    def test_provider_specific_key_lookup_and_legacy_signature(self):
        with patch.dict(os.environ, {'DUOMI_API_KEY': 'synthetic-duomi', 'GRSAI_API_KEY': 'synthetic-grsai'}):
            self.assertEqual(image_api.read_key(self.root, None, False), 'synthetic-grsai')
            self.assertEqual(image_api.read_key(self.root, provider='duomi'), 'synthetic-duomi')

    def test_invalid_size_prompt_model_and_provider_mismatch_stop(self):
        self.assertIsNotNone(image_providers)
        for size in ('1672x941', '16x16', '3840x3840', '4000x1008'):
            with self.subTest(size=size), self.assertRaises(ValueError):
                image_providers.make_input('duomi', None, size)
        with self.assertRaises(ValueError): image_providers.make_input('duomi', 'unapproved', None)
        job = self.duomi_job(False)
        prompt = self.root / job['prompt_path']
        prompt.write_text('x' * 5001, encoding='utf-8')
        job['prompt_sha256'] = state.sha256(prompt)
        with self.assertRaisesRegex(ValueError, '5000'): image_api.build_payload(self.root, job)
        job['provider'] = 'grsai'
        with self.assertRaises(ValueError): image_api.build_payload(self.root, job)

    def test_transport_uses_raw_authorization_post_json_and_get_query(self):
        self.assertTrue(hasattr(image_api, 'DuomiTransport'))
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"id":"synthetic-task"}'
        with patch.object(image_api.urllib.request, 'build_opener') as build:
            build.return_value.open.return_value = Response()
            transport = image_api.DuomiTransport('synthetic-key')
            transport.post('/v1/images/generations?async=true', {'model': 'gpt-image-2'}, 1)
            transport.get('/v1/tasks/synthetic-task', 1)
        requests = [call.args[0] for call in build.return_value.open.call_args_list]
        self.assertEqual(requests[0].full_url, 'https://duomiapi.com/v1/images/generations?async=true')
        self.assertEqual(requests[0].headers['Authorization'], 'synthetic-key')
        self.assertEqual(json.loads(requests[0].data), {'model': 'gpt-image-2'})
        self.assertEqual(requests[1].get_method(), 'GET')
        self.assertIsNone(requests[1].data)


if __name__ == '__main__':
    unittest.main()
