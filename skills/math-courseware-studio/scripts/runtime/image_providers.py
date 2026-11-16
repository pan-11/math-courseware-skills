"""Documented provider settings; no network access or credential loading."""
import re

PROVIDERS = ('grsai', 'duomi', 'toapis')
DUOMI_BASE_URL = 'https://duomiapi.com'
DUOMI_ENDPOINT = '/v1/images/generations?async=true'
DUOMI_MODELS = ('gpt-image-2', 'gpt-image-2.5-flare', 'gpt-image-2.5-sunburst')


def provider_name(value=None):
    value = value or 'grsai'
    if value not in PROVIDERS:
        raise ValueError('Unsupported image API provider')
    return value


def job_provider(job):
    provider = provider_name(job.get('provider'))
    recorded = job.get('image_api_input', {}).get('provider')
    if recorded is not None and recorded != provider:
        raise ValueError('Job provider differs from recorded API input')
    return provider


def make_input(provider=None, model=None, size=None, high=False):
    provider = provider_name(provider)
    if provider == 'toapis':
        from . import image_toapis
        selection = {'high_resolution': high}
        if model is not None: selection['api_options'] = {'model': model}
        return image_toapis.job_options(selection, {}, size or '1672x941')
    if provider == 'grsai':
        expected = 'gpt-image-2-vip' if high else 'gpt-image-2.5'
        if model is not None and model != expected:
            raise ValueError('Grsai model differs from the selected resolution tier')
        size = size or ('3840x2160' if high else '1672x941')
        if not re.fullmatch(r'[1-9]\d{1,4}x[1-9]\d{1,4}', size):
            raise ValueError('Invalid pixel dimensions')
        return {'endpoint': '/v1/draw/completions', 'model': expected,
                'size': size, 'aspectRatio': size, 'shutProgress': True}
    model = model or 'gpt-image-2'
    if model not in DUOMI_MODELS:
        raise ValueError('Unsupported Duomi image model')
    size = size or ('3840x2160' if high else '1792x1008')
    if not re.fullmatch(r'[1-9]\d{1,4}x[1-9]\d{1,4}', size):
        raise ValueError('Duomi requires explicit pixel dimensions for courseware')
    width, height = map(int, size.split('x'))
    if (any(side % 16 or not 16 <= side <= 3840 for side in (width, height))
            or not 655360 <= width * height <= 8294400):
        raise ValueError('Duomi dimensions must be divisible by 16, within 16..3840 per side '
                         'and 655360..8294400 total pixels; preserve the source or select another provider')
    return {'provider': provider, 'endpoint': DUOMI_ENDPOINT, 'model': model, 'size': size,
            'quality': 'high' if high else 'medium', 'background': 'auto'}
