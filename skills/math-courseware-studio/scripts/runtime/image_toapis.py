"""ToAPIs image transport. Project settings contain no credential values."""
import json
from math import gcd
from pathlib import Path
import re
import urllib.parse
import urllib.request
import uuid

from PIL import Image
from . import state

ENDPOINT = '/v1/images/generations'
UPLOAD_ENDPOINT = '/v1/uploads/images'
ORIGINS = ('https://toapis.cn', 'https://toapis.com')
SKILLS_ROOT = Path(__file__).resolve().parents[3]
INSTALL_ROOT = SKILLS_ROOT.parent
if INSTALL_ROOT.name in ('.agents', '.codebuddy'):
    INSTALL_ROOT = INSTALL_ROOT.parent
SETTINGS = INSTALL_ROOT / 'tools/image-api-settings.json'
DEFAULTS = {
    'provider': 'toapis',
    'base_url': ORIGINS[0],
    'model': 'gpt-image-2-vip',
    'quality': 'low',
    'resolution': '1k',
}


def settings():
    try:
        overrides = json.loads(SETTINGS.read_text(encoding='utf-8-sig'))
    except FileNotFoundError:
        overrides = {}
    if not isinstance(overrides, dict) or set(overrides) - (DEFAULTS.keys() | {'key_file'}):
        raise ValueError('Invalid ToAPIs project settings')
    value = {**DEFAULTS, **overrides}
    if value.get('provider') != 'toapis' or value.get('base_url') not in ORIGINS:
        raise ValueError('Invalid ToAPIs project provider/base URL')
    validate_options(value)
    return value


def validate_options(options):
    if options.get('model') not in ('gpt-image-2-vip', 'gpt-image-2'):
        raise ValueError('Model needs a documented ToAPIs GPT-Image-2 compatible adapter')
    if options.get('quality') not in ('low', 'medium', 'high'):
        raise ValueError('ToAPIs quality must be low, medium or high')
    if options.get('resolution') not in ('1k', '2k', '4k'):
        raise ValueError('ToAPIs resolution must be 1k, 2k or 4k')


def job_options(selection, task, pixel_size):
    config = settings()
    options = {key: config[key] for key in ('model', 'quality', 'resolution')}
    for override in (selection.get('api_options', {}), task.get('api_options', {})):
        if not isinstance(override, dict) or set(override) - set(options):
            raise ValueError('api_options only accepts model, quality and resolution')
        options.update(override)
    validate_options(options)
    # high_resolution remains an explicit 4K request, never a quality change.
    if selection.get('high_resolution') and 'resolution' not in task.get('api_options', {}):
        options['resolution'] = '4k'
    width, height = map(int, pixel_size.split('x'))
    # Existing slide defaults are approximate pixels; send the exact slide ratio.
    if pixel_size in ('1672x941', '3840x2160'):
        ratio = '16:9'
    else:
        factor = gcd(width, height)
        ratio = f'{width // factor}:{height // factor}'
    return {**options, 'endpoint': ENDPOINT, 'base_url': config['base_url'], 'size': ratio}


def build_payload(project, job):
    options = job['image_api_input']
    validate_options(options)
    if options.get('endpoint') != ENDPOINT or options.get('base_url') not in ORIGINS:
        raise ValueError('Invalid ToAPIs endpoint')
    ratio = options.get('size', '')
    if not re.fullmatch(r'[1-9]\d*:[1-9]\d*', ratio):
        raise ValueError('ToAPIs size must be a width:height ratio')
    prompt = state.resolve(project, job['prompt_path'])
    if state.sha256(prompt) != job['prompt_sha256']:
        raise ValueError('Prompt changed after dispatch; prepare a new version')
    for ref in job.get('references', []):
        path = state.resolve(project, ref['path'])
        if state.sha256(path) != ref['sha256']:
            raise ValueError('Reference changed after dispatch')
        if path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError('ToAPIs reference exceeds 10MB upload limit')
        with Image.open(path) as image:
            if image.format not in ('PNG', 'JPEG', 'WEBP', 'GIF'):
                raise ValueError('Unsupported ToAPIs reference format')
            image.verify()
    text = prompt.read_text(encoding='utf-8')
    if len(text) > 32000:
        raise ValueError('ToAPIs prompt exceeds 32000 characters')
    return {key: options[key] for key in ('model', 'quality', 'resolution', 'size')} | {
        'prompt': text, 'n': 1, 'response_format': 'url'}


def parse_response(payload):
    if not isinstance(payload, dict):
        raise ValueError('ToAPIs response is not an object')
    task_id = payload.get('id')
    if task_id is not None and (not isinstance(task_id, str) or not task_id):
        raise ValueError('Invalid ToAPIs task ID')
    status = payload.get('status')
    result = {'task_id': task_id, 'response_id': task_id}
    if status == 'failed' or payload.get('error'):
        return {**result, 'status': 'failed', 'error_code': 'provider_task_failed'}
    if status == 'completed':
        items = payload.get('result', {}).get('data', [])
        url = items[0].get('url') if items and isinstance(items[0], dict) else None
        if not isinstance(url, str) or urllib.parse.urlsplit(url).scheme != 'https':
            raise ValueError('Completed ToAPIs task missing HTTPS result URL')
        return {**result, 'status': 'result_ready', 'provider_image_url': url}
    if task_id and status in ('queued', 'in_progress'):
        return {**result, 'status': 'running'}
    raise ValueError('Unknown ToAPIs task response')


class HttpTransport:
    def __init__(self, key, base_url):
        if base_url not in ORIGINS:
            raise ValueError('Unsupported ToAPIs origin')
        self.key, self.base_url = key, base_url

    def _request(self, endpoint, timeout, data=None, content_type=None):
        headers = {'Authorization': 'Bearer ' + self.key}
        if content_type:
            headers['Content-Type'] = content_type
        request = urllib.request.Request(self.base_url + endpoint, data=data, headers=headers,
                                         method='POST' if data is not None else 'GET')
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args):
                return None
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=timeout) as response:
            raw = response.read().decode('utf-8')
        payload = json.loads(raw)
        if self.key and (self.key in raw or self.key in json.dumps(payload, ensure_ascii=False)):
            raise ValueError('Provider returned credential material; response discarded')
        return payload

    def post(self, endpoint, payload, timeout):
        if endpoint != ENDPOINT:
            raise ValueError('Unsupported ToAPIs generation endpoint')
        return self._request(endpoint, timeout, json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                             'application/json')

    def query(self, task_id, timeout):
        if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', task_id):
            raise ValueError('Invalid ToAPIs task ID')
        return self._request(ENDPOINT + '/' + task_id, timeout)

    def upload(self, path, timeout):
        path = Path(path)
        with Image.open(path) as image:
            mime = Image.MIME[image.format]
        boundary = 'courseware-' + uuid.uuid4().hex
        # ASCII filename avoids leaking private local paths into multipart headers.
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="reference"\r\n'
                f'Content-Type: {mime}\r\n\r\n').encode('ascii')
        body += path.read_bytes() + f'\r\n--{boundary}--\r\n'.encode('ascii')
        payload = self._request(UPLOAD_ENDPOINT, timeout, body, 'multipart/form-data; boundary=' + boundary)
        url = payload.get('data', {}).get('url')
        if payload.get('success') is not True or not isinstance(url, str) or urllib.parse.urlsplit(url).scheme != 'https':
            raise ValueError('ToAPIs upload did not return a successful HTTPS URL')
        return url

    def download(self, url, timeout):
        if urllib.parse.urlsplit(url).scheme != 'https':
            raise ValueError('Image result must be an HTTPS URL')
        # Result hosts receive no bearer credential; also reject redirect downgrades.
        class HttpsRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                if urllib.parse.urlsplit(newurl).scheme != 'https':
                    raise ValueError('Result redirect must use HTTPS')
                return super().redirect_request(req, fp, code, msg, headers, newurl)
        with urllib.request.build_opener(HttpsRedirect()).open(url, timeout=timeout) as response:
            return response.read()
