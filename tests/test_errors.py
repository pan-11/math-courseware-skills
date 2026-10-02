"""P0 diagnostics through real CLI/job paths; no live network or real credentials."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import urllib.error
from urllib.parse import quote
import uuid
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
import courseware
from runtime import state, prompts, image_api, pptx_editor


class ErrorTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GRSAI_API_KEY': ''})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.run = ROOT / 'tests/runs' / ('errors-' + uuid.uuid4().hex)
        self.run.mkdir()
        (self.run / 'AGENTS.md').write_text(
            'Synthetic diagnostic tests only. Fake credentials, no live services. Retain evidence.',
            encoding='utf-8')
        self.root = self.run / 'project'
        state.init_project(self.root, 'Synthetic P0 errors', 'openai_image_api')

    def cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = courseware.main(args)
        return code, out.getvalue(), err.getvalue()

    def exception_output(self, exc):
        with patch.object(courseware, 'execute', side_effect=exc):
            code, out, err = self.cli(['doctor'])
        self.assertEqual((code, out), (1, ''))
        return json.loads(err)

    def batch(self, suffix='1'):
        return prompts.prepare(self.root, {'tasks': [
            {'purpose': 'test', 'target_id': 'P0-' + suffix, 'prompt': 'Synthetic diagnostics, no live API'}],
            'authorization_evidence': 'Synthetic fixture, not real user authorization'})

    def job(self, batch):
        return state.read_json(self.root / batch['jobs'][0])

    def http_error(self, code, body, stream=None):
        stream = stream or io.BytesIO(body.encode('utf-8'))
        return urllib.error.HTTPError('https://example.invalid/image?token=fake-query-token',
                                      code, 'Synthetic HTTP failure', {}, stream)

    def no_secret(self, secret, *output):
        for value in output:
            self.assertNotIn(secret, value)
        for path in self.root.rglob('*.json'):
            self.assertNotIn(secret, path.read_text(encoding='utf-8'))

    def helpers(self):
        self.assertIsNotNone(importlib.util.find_spec('runtime.errors'),
                             'P0 error helpers must exist')
        from runtime import errors
        return errors

    def test_validate_names_missing_unit_id(self):
        state.write_json(self.root / '_state/pages.json', {'pages': [
            {'page_id': 'P001', 'order': 1, 'text_units': [{'text': 'Synthetic'}]}]})
        code, out, err = self.cli(['validate', '--project', str(self.root)])
        self.assertEqual((code, out), (1, ''))
        result = json.loads(err)
        self.assertIn('unit_id', result['error'])
        self.assertEqual(result.get('error_type'), 'KeyError')
        self.assertEqual(result.get('command'), 'validate')

    def test_permission_diagnostic_names_path_without_claiming_cause(self):
        result = self.exception_output(PermissionError(13, 'Access denied', 'synthetic/deck.pptx'))
        self.assertIn('synthetic/deck.pptx', result['error'])
        self.assertIn('没有权限或文件被占用', result['error'])

    def test_missing_file_diagnostic(self):
        result = self.exception_output(FileNotFoundError(2, 'Missing', 'synthetic/missing.pptx'))
        self.assertIn('找不到文件', result['error'])
        self.assertIn('synthetic/missing.pptx', result['error'])

    def test_bad_json_has_real_line_and_column(self):
        (self.root / '_state/pages.json').write_text('{"pages":\n}', encoding='utf-8')
        code, out, err = self.cli(['validate', '--project', str(self.root)])
        result = json.loads(err)
        self.assertEqual((code, out), (1, ''))
        self.assertIn('JSON 格式错误', result['error'])
        self.assertIn('第 2 行第 1 列', result['error'])
        self.assertNotIn('pages.json', result['error'])  # This exception carries no filename.

    def test_cli_success_contract_is_unchanged(self):
        expected = courseware.execute(argparse.Namespace(command='status', project=self.root))
        code, out, err = self.cli(['status', '--project', str(self.root)])
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(json.loads(out), expected)

    def test_parser_errors_and_interrupts_keep_original_exit_behavior(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            courseware.main(['not-a-command'])
        self.assertEqual(caught.exception.code, 2)
        with patch.object(courseware, 'execute', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                courseware.main(['doctor'])

    def test_office_missing_and_failed_errors_are_distinct(self):
        with patch.object(pptx_editor.shutil, 'which', return_value=None):
            with self.assertRaises(RuntimeError) as caught:
                pptx_editor._office([])
        missing = self.exception_output(caught.exception)
        self.assertIn('没有找到 OfficeCLI', missing['error'])
        completed = subprocess.CompletedProcess([], 9, 'synthetic output ', 'unsupported input')
        with patch.object(pptx_editor.shutil, 'which', return_value='synthetic-officecli'), \
                patch.object(pptx_editor.subprocess, 'run', return_value=completed):
            with self.assertRaises(RuntimeError) as caught:
                pptx_editor._office(['synthetic.pptx'])
        failed = self.exception_output(caught.exception)
        self.assertIn('退出码 9', failed['error'])
        self.assertIn('unsupported input', failed['error'])

    def test_timeout_names_program_and_duration_without_arguments(self):
        exc = subprocess.TimeoutExpired(
            [r'C:\Program Files\OfficeCLI\officecli.exe', '--key', 'fake-sensitive-argument'], 120)
        result = self.exception_output(exc)
        self.assertIn('officecli.exe', result['error'])
        self.assertIn('120', result['error'])
        self.assertIn('超时', result['error'])
        self.assertNotIn('fake-sensitive-argument', result['error'])
        self.assertNotIn('--key', result['error'])

    def test_office_failure_reports_exit_code(self):
        completed = subprocess.CompletedProcess([], 9, 'synthetic output ', 'unsupported input')
        with patch.object(pptx_editor.shutil, 'which', return_value='synthetic-officecli'), \
                patch.object(pptx_editor.subprocess, 'run', return_value=completed):
            with self.assertRaises(RuntimeError) as caught:
                pptx_editor._office(['synthetic.pptx'])
        self.assertIn('退出码 9', str(caught.exception))
        self.assertIn('unsupported input', str(caught.exception))

    def test_office_exception_never_retains_credential_output(self):
        key = 'fake-office-environment-key'
        completed = subprocess.CompletedProcess([], 3, key, 'Authorization: Bearer fake-office-token')
        with patch.dict(os.environ, {'GRSAI_API_KEY': key}), \
                patch.object(pptx_editor.shutil, 'which', return_value='synthetic-officecli'), \
                patch.object(pptx_editor.subprocess, 'run', return_value=completed):
            with self.assertRaises(RuntimeError) as caught:
                pptx_editor._office([])
        self.assertNotIn(key, str(caught.exception))
        self.assertNotIn('fake-office-token', str(caught.exception))

    def test_redaction_covers_known_and_structured_secrets_before_truncation(self):
        errors = self.helpers()
        key = 'fake-runtime/credential+value'
        samples = [
            (key, [key]), (quote(key, safe=''), [key]),
            ('Bearer fake-bearer-token', ['fake-bearer-token']),
            ('sk-fake-pattern-token', ['sk-fake-pattern-token']),
            ('{"api_key":"fake-json-secret","password":"fake-password"}',
             ['fake-json-secret', 'fake-password']),
            ('https://example.invalid/?token=fake-query-secret&api_key=fake-url-key',
             ['fake-query-secret', 'fake-url-key']),
            ('Authorization: Bearer fake-header-token', ['fake-header-token'])]
        for text, values in samples:
            with self.subTest(text=text):
                safe = errors.redact(text, secrets=(key,))
                for value in values:
                    self.assertNotIn(value, safe)
                self.assertIn('***', safe)
        safe = errors.redact('x' * 595 + key + 'tail', secrets=(key,))
        self.assertLessEqual(len(safe), 600)
        self.assertNotIn('fake-', safe)

    def test_cli_and_office_output_redact_environment_credentials(self):
        key = 'fake-environment-credential'
        with patch.dict(os.environ, {'GRSAI_API_KEY': key}):
            result = self.exception_output(ValueError('Synthetic failure ' + key))
            self.assertNotIn(key, json.dumps(result))
            completed = subprocess.CompletedProcess([], 3, key, 'Authorization: Bearer fake-office-token')
            with patch.object(pptx_editor.shutil, 'which', return_value='synthetic-officecli'), \
                    patch.object(pptx_editor.subprocess, 'run', return_value=completed):
                with self.assertRaises(RuntimeError) as caught:
                    pptx_editor._office([])
            self.assertNotIn(key, str(caught.exception))
            self.assertNotIn('fake-office-token', str(caught.exception))

    def test_http_status_and_message_do_not_change_unknown_submission(self):
        for status in (401, 402, 429):
            with self.subTest(status=status):
                batch = self.batch(str(status))
                exc = self.http_error(status, '{"message":"synthetic provider explanation"}')
                with patch.object(image_api.HttpTransport, 'post', side_effect=exc) as post:
                    image_api.run_batch(self.root, batch, 'fake-current-key')
                    job = self.job(batch)
                    self.assertEqual(job['status'], 'submission_unknown')
                    self.assertEqual(job['error_code'], 'HTTPError')
                    self.assertEqual(job.get('http_status'), status)
                    self.assertIn('synthetic provider explanation', job.get('provider_message', ''))
                    image_api.run_batch(self.root, batch, 'fake-current-key', resume=True)
                    self.assertEqual(post.call_count, 1)

    def test_all_credential_inputs_discard_leaking_http_body(self):
        for source in ('environment', 'file', 'stdin'):
            with self.subTest(source=source):
                key = 'fake-opaque-credential-' + source
                batch = self.batch(source)
                args = ['image-run', '--project', str(self.root),
                        '--batch', str(self.root / batch['path'])]
                if source == 'file':
                    path = self.run / 'fake-credential-source.txt'
                    path.write_text(key, encoding='utf-8')
                    args += ['--key-file', str(path)]
                elif source == 'stdin':
                    args += ['--key-stdin']
                exc = self.http_error(401, json.dumps({'message': 'leaking ' + key}))
                with patch.dict(os.environ, {'GRSAI_API_KEY': key if source == 'environment' else ''}), \
                        patch.object(sys, 'stdin', io.StringIO(key)), \
                        patch.object(image_api.HttpTransport, 'post', side_effect=exc):
                    code, out, err = self.cli(args)
                job = self.job(batch)
                self.assertEqual(code, 1)
                self.assertEqual(job.get('http_status'), 401)
                self.assertNotIn('provider_message', job)
                self.assertTrue(job.get('error_detail'))
                self.no_secret(key, out, err)

    def test_http_body_read_is_bounded_and_malformed_body_is_not_logged(self):
        class Body(io.BytesIO):
            def __init__(self, data):
                super().__init__(data)
                self.read_sizes = []
            def read(self, size=-1):
                self.read_sizes.append(size)
                return super().read(size)
        body = Body(b'{"message":"' + b'x' * 3000 + b'"}')
        batch = self.batch()
        with patch.object(image_api.HttpTransport, 'post',
                          side_effect=self.http_error(429, '', stream=body)):
            image_api.run_batch(self.root, batch, 'fake-current-key')
        job = self.job(batch)
        self.assertEqual(body.read_sizes, [2048])
        self.assertEqual(job.get('http_status'), 429)
        self.assertNotIn('provider_message', job)

    def test_broken_error_body_does_not_mask_original_failure(self):
        class Body(io.BytesIO):
            def read(self, size=-1):
                raise OSError('fake-body-reader-detail')
        batch = self.batch()
        with patch.object(image_api.HttpTransport, 'post',
                          side_effect=self.http_error(402, '', stream=Body(b'x'))):
            image_api.run_batch(self.root, batch, 'fake-current-key')
        job = self.job(batch)
        self.assertEqual((job['status'], job['error_code']), ('submission_unknown', 'HTTPError'))
        self.assertEqual(job.get('http_status'), 402)
        self.no_secret('fake-body-reader-detail')

    def test_overdeep_error_json_cannot_replace_original_job_state(self):
        batch = self.batch()
        with patch.object(image_api.HttpTransport, 'post',
                          side_effect=self.http_error(429, '[' * 1500 + '0' + ']' * 1500)):
            result = image_api.run_batch(self.root, batch, 'fake-key')
        self.assertEqual(result['results'][0]['status'], 'submission_unknown')
        job = self.job(batch)
        self.assertEqual((job['status'], job['error_code']), ('submission_unknown', 'HTTPError'))
        self.assertEqual(job.get('http_status'), 429)

    def test_query_failure_keeps_query_code_and_can_resume_without_submit(self):
        batch = self.batch()
        job = self.job(batch)
        job.update(status='running', task_id='synthetic-task')
        state.write_json(self.root / batch['jobs'][0], job)
        with patch.object(image_api.HttpTransport, 'post', side_effect=[
                self.http_error(429, '{"message":"retry query later"}'),
                TimeoutError('fake-opaque-network-detail')]) as post:
            image_api.run_batch(self.root, batch, 'fake-key', resume=True)
            job = self.job(batch)
            self.assertEqual(job['error_code'], 'query_HTTPError')
            self.assertEqual(job.get('http_status'), 429)
            image_api.run_batch(self.root, batch, 'fake-key', resume=True)
            job = self.job(batch)
            self.assertEqual((job['status'], job['error_code']), ('running', 'query_TimeoutError'))
            self.assertIn('超时', job.get('error_detail', ''))
            self.assertNotIn('http_status', job)
            self.assertNotIn('provider_message', job)
            self.assertEqual([call.args[0] for call in post.call_args_list],
                             [image_api.RESULT_ENDPOINT, image_api.RESULT_ENDPOINT])
        self.no_secret('fake-opaque-network-detail')

    def test_download_failure_retains_safe_detail_and_resumes_only_download(self):
        batch = self.batch()
        result = {'code': 0, 'data': {'id': 'synthetic-task', 'status': 'succeeded',
                  'results': [{'url': 'https://example.invalid/image.png'}]}}
        buf = io.BytesIO()
        Image.new('RGB', (32, 18), 'white').save(buf, format='PNG')
        with patch.object(image_api.HttpTransport, 'post', return_value=result) as post, \
                patch.object(image_api.HttpTransport, 'download', side_effect=[
                    TimeoutError('fake-download-detail'), buf.getvalue()]) as download:
            image_api.run_batch(self.root, batch, 'fake-key')
            job = self.job(batch)
            self.assertEqual(job['status'], 'download_failed')
            self.assertEqual(job['error_code'], 'TimeoutError')
            self.assertIn('超时', job.get('error_detail', ''))
            image_api.run_batch(self.root, batch, 'fake-key', resume=True)
            self.assertEqual(self.job(batch)['status'], 'downloaded')
            self.assertEqual((post.call_count, download.call_count), (1, 2))
        self.no_secret('fake-download-detail')

    def test_batch_worker_failure_redacts_the_current_key(self):
        batch = self.batch()
        key = 'fake-worker-credential'
        with patch.object(image_api, 'run_job', side_effect=ValueError('Synthetic error: ' + key)):
            result = image_api.run_batch(self.root, batch, key)
        item = result['results'][0]
        self.assertEqual((item['status'], item['error_code']), ('blocked', 'ValueError'))
        self.assertIn('Synthetic error', item.get('error_detail', ''))
        self.no_secret(key, json.dumps(result))

    def test_unknown_transport_error_never_emits_arbitrary_request_text(self):
        batch = self.batch()
        with patch.object(image_api.HttpTransport, 'post',
                          side_effect=urllib.error.URLError('fake-unknown-request-data')):
            image_api.run_batch(self.root, batch, 'fake-key')
        job = self.job(batch)
        self.assertEqual(job['error_code'], 'URLError')
        self.assertTrue(job.get('error_detail'))
        self.assertNotIn('http_status', job)
        self.no_secret('fake-unknown-request-data')


if __name__ == '__main__':
    unittest.main()
