"""Grsai old API transport and resumable jobs; credentials never enter job records."""
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import io
import json
import mimetypes
import os
import re
from pathlib import Path
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from PIL import Image
from . import state

BASE_URL = 'https://grsai.dakka.com.cn'
ENDPOINT = '/v1/draw/completions'
RESULT_ENDPOINT = '/v1/draw/result'


def read_key(project, key_file=None, stdin=False):
    if key_file and stdin:
        raise ValueError('Choose one credential source')
    if stdin:
        import sys
        value = sys.stdin.read().strip()
    elif key_file:
        path = Path(key_file).resolve()
        if path.is_relative_to(Path(project).resolve()):
            raise ValueError('Secret file must be outside the project')
        value = path.read_text(encoding='utf-8').strip()
    else:
        value = os.environ.get('GRSAI_API_KEY', '').strip()
    if not value:
        raise ValueError('No Grsai credential available; use environment, stdin or an external secret file')
    return value


class HttpTransport:
    def __init__(self, key):
        self.key = key

    def post(self, endpoint, payload, timeout):
        if endpoint not in (ENDPOINT, RESULT_ENDPOINT):
            raise ValueError('Unsupported Grsai endpoint')
        req = urllib.request.Request(BASE_URL + endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'}, method='POST')
        # Disable redirects so Authorization cannot be forwarded to another origin.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args):
                return None
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(req, timeout=timeout) as response:
            raw = response.read().decode('utf-8')
        if self.key in raw:
            raise ValueError('Provider returned credential material; response discarded')
        if raw.lstrip().startswith('data:'):
            events = [json.loads(line[5:].strip()) for line in raw.splitlines()
                      if line.startswith('data:') and line[5:].strip() not in ('', '[DONE]')]
            if not events:
                raise ValueError('Empty event stream')
            return events[-1]
        return json.loads(raw)

    def download(self, url, timeout):
        if urllib.parse.urlsplit(url).scheme != 'https':
            raise ValueError('Image result must be an HTTPS URL')
        # No Authorization on provider image downloads.
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read()


def build_payload(project, job):
    options = job['image_api_input']
    if options.get('endpoint') != ENDPOINT or options.get('shutProgress') is not True:
        raise ValueError('Invalid endpoint or shutProgress')
    if options.get('model') not in ('gpt-image-2.5', 'gpt-image-2-vip'):
        raise ValueError('Model differs from approved rules')
    if options.get('aspectRatio') != options.get('size'):
        raise ValueError('Request aspectRatio and recorded size differ')
    expected_model = 'gpt-image-2-vip' if job.get('resolution_tier') == 'high' else 'gpt-image-2.5'
    if options['model'] != expected_model:
        raise ValueError('Model differs from the selected resolution tier')
    if not re.fullmatch(r'[1-9]\d{1,4}x[1-9]\d{1,4}', options['size']):
        raise ValueError('Invalid pixel dimensions')
    if job['purpose'] in ('page', 'cover', 'test') and options['size'] != \
            ('3840x2160' if job.get('resolution_tier') == 'high' else '1672x941'):
        raise ValueError('Slide/test dimensions differ from the selected resolution tier')
    prompt = state.resolve(project, job['prompt_path'])
    if state.sha256(prompt) != job['prompt_sha256']:
        raise ValueError('Prompt changed after dispatch; prepare a new version')
    payload = {'model': options['model'], 'prompt': prompt.read_text(encoding='utf-8'),
               'aspectRatio': options['aspectRatio'], 'shutProgress': True}
    urls = []
    for ref in job.get('references', []):
        path = state.resolve(project, ref['path'])
        if state.sha256(path) != ref['sha256']:
            raise ValueError('Reference changed after dispatch')
        with Image.open(path) as image:
            mime = Image.MIME.get(image.format) or mimetypes.guess_type(path)[0]
            image.verify()
        urls.append(f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii'))
    if urls:
        payload['urls'] = urls
    return payload


def parse_response(payload):
    if not isinstance(payload, dict):
        raise ValueError('Provider response is not an object')
    if payload.get('code', 0) != 0:
        return {'status': 'failed', 'error_code': payload['code']}
    data = payload.get('data', payload)
    if not isinstance(data, dict):
        raise ValueError('Provider data is not an object')
    task_id = data.get('id') or payload.get('id')
    if task_id is not None and not isinstance(task_id, str):
        raise ValueError('Invalid provider task ID')
    status = data.get('status')
    result = {'task_id': task_id, 'response_id': task_id}
    if status in ('failed', 'failure', 'error'):
        return {**result, 'status': 'failed', 'error_code': 'provider_task_failed'}
    if status in ('succeeded', 'success', 'finish', 'finished'):
        results = data.get('results', [])
        first = results[0] if results else {'url': data.get('url')}
        if isinstance(first, str):
            first = {'url': first}
        url = first.get('url') if isinstance(first, dict) else None
        if not url or urllib.parse.urlsplit(url).scheme != 'https':
            raise ValueError('Successful result missing HTTPS image URL')
        return {**result, 'status': 'result_ready', 'provider_image_url': url}
    if task_id:
        return {**result, 'status': 'running'}
    raise ValueError('Provider response has neither completed result nor task ID')


@contextmanager
def job_lock(path):
    # Persistent lock file, OS-released on process exit; no destructive stale-lock cleanup.
    with Path(path).open('a+b') as stream:
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('Image job is already being executed') from exc
        try:
            yield
        finally:
            stream.seek(0)
            if sys.platform == 'win32':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def run_job(project, relative, transport, resume=False, timeout=500, poll_interval=5):
    with job_lock(state.resolve(project, relative).with_suffix('.lock')):
        return _run_job_locked(project, relative, transport, resume, timeout, poll_interval)


def _run_job_locked(project, relative, transport, resume=False, timeout=500, poll_interval=5):
    path = state.resolve(project, relative)
    job = state.read_json(path)
    if job['route'] != 'openai_image_api':
        raise ValueError('Built-in image tasks must be executed with the Codex image tool')
    if job['status'] == 'downloaded':
        if state.sha256(state.resolve(project, job['output_path'])) != job['sha256']:
            raise ValueError('Downloaded image changed; preserve it and prepare a new version')
        return job
    if job['status'] in ('submitting', 'submission_unknown', 'failed'):
        if job['status'] == 'submitting':
            job['status'] = 'submission_unknown'
            state.write_json(path, job)
        return job
    changed = []
    for target, expected in job.get('input_versions', {}).items():
        target_path = state.resolve(project, target)
        if not target_path.is_file() or state.sha256(target_path) != expected:
            changed.append(target)
        if job['status'] == 'pending':
            state.require_approved(project, target)
    if job['status'] == 'pending':
        if job['target_id'] in state.load_project(project).get('stale_targets', []):
            raise ValueError('Target is stale; update and confirm it before generation')
        if changed:
            from . import prompts
            equivalent = job.get('purpose') == 'page' and job.get('semantic_fingerprint') == \
                         prompts.page_fingerprint(prompts.records(project), job['target_id'])
            if not equivalent:
                raise ValueError('Upstream input changed before submission: ' + ', '.join(changed))
            job['execution_input_versions'] = {target: state.sha256(state.resolve(project, target))
                                                for target in job['input_versions']}
            changed = []
    # Already-paid work must remain downloadable even if later project versions change.
    job['stale_inputs'] = changed
    started = time.monotonic()
    deadline = started + timeout
    def remaining():
        return max(0.1, deadline - time.monotonic())
    def save():
        job['elapsed_seconds'] = round(job.get('prior_elapsed_seconds', 0) + time.monotonic() - started, 3)
        state.write_json(path, job)
    job['prior_elapsed_seconds'] = job.get('elapsed_seconds', 0)
    if job['status'] == 'pending':
        if resume:
            return job
        body = build_payload(project, job)
        job.update(status='submitting', api_base_url=BASE_URL, api_endpoint=ENDPOINT,
                   model=body['model'], aspectRatio=body['aspectRatio'], size=body['aspectRatio'])
        save()
        try:
            parsed = parse_response(transport.post(ENDPOINT, body, remaining()))
            job.update({k: v for k, v in parsed.items() if v is not None})
        except Exception as exc:
            # A timeout/connection/parse failure cannot establish whether billing occurred.
            job.update(status='submission_unknown', error_code=type(exc).__name__)
        save()
    while job['status'] == 'running' and time.monotonic() < deadline:
        try:
            parsed = parse_response(transport.post(RESULT_ENDPOINT, {'id': job['task_id']}, remaining()))
            if parsed.get('task_id') not in (None, job['task_id']):
                raise ValueError('Provider returned a different task ID')
            job.update({k: v for k, v in parsed.items() if v is not None})
        except Exception as exc:
            job['error_code'] = 'query_' + type(exc).__name__
            save()
            return job
        save()
        if job['status'] == 'running':
            time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
    if job['status'] in ('result_ready', 'download_failed'):
        try:
            raw = transport.download(job['provider_image_url'], remaining())
            with Image.open(io.BytesIO(raw)) as img:
                img.verify()
            with Image.open(io.BytesIO(raw)) as img:
                width, height, fmt = img.width, img.height, img.format
            suffix = {'PNG': '.png', 'JPEG': '.jpg', 'WEBP': '.webp'}.get(fmt)
            if not suffix:
                raise ValueError('Unsupported image format')
            output = state.resolve(project, job['output_path']).with_suffix(suffix)
            if output.exists() and output.read_bytes() != raw:
                raise ValueError('Existing output differs; do not overwrite')
            output.write_bytes(raw)
            job.update(output_path=output.relative_to(Path(project).resolve()).as_posix(),
                       status='downloaded', width_px=width, height_px=height, sha256=state.sha256(output),
                       size_matches_request=job['image_api_input']['size'] == f'{width}x{height}',
                       review_status='pending_visual_review')
            job['api_evidence_path'] = str(Path(relative).with_name('evidence.json')).replace('\\', '/')
            save()
            state.write_json(state.resolve(project, job['api_evidence_path']), job)
        except Exception as exc:
            job.update(status='download_failed', error_code=type(exc).__name__)
            save()
    return job


def run_batch(project, batch, key, resume=False):
    if batch.get('route') != 'openai_image_api':
        raise ValueError('Only Grsai batches use the HTTP executor')
    if not resume and batch.get('route') != state.load_project(project).get('image_route'):
        raise ValueError('Batch route differs from project selection')
    if not batch.get('authorization_evidence', '').strip():
        raise ValueError('Record the actual generation authorization before running a batch')
    if not batch.get('jobs') or len(set(batch['jobs'])) != len(batch['jobs']):
        raise ValueError('Empty or duplicate batch jobs')
    concurrency = min(6, max(1, int(batch.get('concurrency', 6))), len(batch['jobs']))
    transport = HttpTransport(key)
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [(path, pool.submit(run_job, project, path, transport, resume,
                                     int(batch.get('timeout_seconds', 500)))) for path in batch['jobs']]
        results = []
        for path, future in futures:
            try:
                job = future.result()
                results.append({'job': path, 'status': job['status']})
            except Exception as exc:
                results.append({'job': path, 'status': 'blocked', 'error_code': type(exc).__name__})
    result = {**batch, 'results': results, 'completed_at': state.now()}
    state.write_json(state.resolve(project, batch['path']), result)
    return result


def register_builtin(project, result):
    relative = result['job_path']
    path = state.resolve(project, relative)
    job = state.read_json(path)
    if job['route'] != 'builtin' or not result.get('tool_evidence', '').strip():
        raise ValueError('Actual built-in tool evidence and matching route required')
    if result.get('input_digest') != job['input_digest']:
        raise ValueError('Result does not identify the dispatched input version')
    for file in [{'path': job['prompt_path'], 'sha256': job['prompt_sha256']}, *job.get('references', [])]:
        if state.sha256(state.resolve(project, file['path'])) != file['sha256']:
            raise ValueError('Built-in task input changed after dispatch')
    source = Path(result['image_path']).resolve()
    with Image.open(source) as img:
        img.verify()
    with Image.open(source) as img:
        width, height = img.size
    output = state.resolve(project, job['output_path']).with_suffix(source.suffix.lower())
    if output.exists() and state.sha256(output) != state.sha256(source):
        raise ValueError('Output already exists with different bytes')
    if source != output:
        shutil.copy2(source, output)
    job.update(status='downloaded', output_path=output.relative_to(Path(project).resolve()).as_posix(),
               width_px=width, height_px=height, sha256=state.sha256(output),
               tool_evidence=result['tool_evidence'], review_status='pending_visual_review',
               response_id=result.get('response_id'), task_id=result.get('task_id'),
               registered_at=state.now())
    state.write_json(path, job)
    return job
