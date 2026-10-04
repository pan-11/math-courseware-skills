"""One run's API attempt ledger and builtin successful-registration soft limit."""
from copy import deepcopy

from . import state, preferences, automation_store as store


def _ledger(history_unknown):
    return {'accounting_started_at': state.now(), 'history_unknown': history_unknown, 'entries': {}}


def configure(data, limits):
    if (not isinstance(limits, dict) or set(limits) != {'max_images', 'evidence'}
            or type(limits['max_images']) is not int or limits['max_images'] <= 0
            or not preferences._text(limits['evidence'])):
        raise ValueError('limits requires positive integer max_images and actual nonempty evidence')
    data['limits'] = deepcopy(limits)
    if 'image_budget' not in data:
        data['image_budget'] = _ledger(history_unknown=True)


def initialize(data, limits=None):
    data['image_budget'] = _ledger(history_unknown=False)
    data['limits'] = {'max_images': 60}
    if limits is not None: configure(data, limits)


def summary(data):
    ledger = data.get('image_budget', {})
    maximum = data.get('limits', {}).get('max_images')
    configured = type(maximum) is int and maximum > 0 and 'image_budget' in data
    used = len(ledger.get('entries', {}))
    return {'configured': configured, 'max_images': maximum if configured else None,
            'used': used, 'remaining': max(0, maximum - used) if configured else None,
            'overshoot': max(0, used - maximum) if configured else None,
            'accounting_started_at': ledger.get('accounting_started_at'),
            'history_unknown': ledger.get('history_unknown', True),
            'generation_blocked': not configured or used >= maximum}


def capacity_issues(data, count):
    status = summary(data)
    if not status['configured']:
        return ['Image budget unconfigured; use run-configure limits with actual evidence; earlier usage is unknown']
    if count > status['remaining']:
        return ['Image budget limit: requested %d, remaining %d, used %d, max_images %d; '
                'new generation waits for an evidenced run-configure limit increase' %
                (count, status['remaining'], status['used'], status['max_images'])]
    return []


def validate_declaration(spec):
    if 'image_count' in spec:
        if type(spec['image_count']) is not int or spec['image_count'] <= 0:
            raise ValueError('image_count must be a positive integer, not a boolean')
        if 'image_requests' in spec and spec['image_count'] != len(spec['image_requests']):
            raise ValueError('image_count must match the actual image_requests quantity')


def amend_declarations(data, declarations):
    """Supply only a missing future quantity; never rewrite a task or infer old usage."""
    if not isinstance(declarations, list) or not declarations:
        raise ValueError('image_declarations requires a nonempty list')
    tasks = {task['spec']['id']: task for task in data['tasks']}
    seen = set()
    for declaration in declarations:
        if (not isinstance(declaration, dict) or set(declaration) != {'task_id', 'image_count', 'evidence'}
                or not isinstance(declaration['task_id'], str)
                or not preferences._text(declaration['evidence'])):
            raise ValueError('Each image declaration requires task_id, image_count and actual evidence')
        validate_declaration(declaration)
        task_id = declaration['task_id']
        if task_id not in tasks or task_id in seen:
            raise ValueError('Image declarations require known unique task IDs')
        seen.add(task_id)
        task = tasks[task_id]
        if (task['status'] != 'pending' or task.get('attempt', 0) != 0
                or 'claim' in task or task.get('history')):
            raise ValueError('Only pending tasks that were never attempted or claimed can receive an image declaration')
        if ('image_count' in task['spec'] or 'image_requests' in task['spec'] or 'image_declaration' in task):
            raise ValueError('Existing image declarations cannot be changed; only missing quantities may be supplied')
        task['image_declaration'] = {'image_count': declaration['image_count'],
                                     'evidence': declaration['evidence'], 'declared_at': state.now()}


def task_spec(task):
    declaration = task.get('image_declaration')
    return {**task['spec'], 'image_count': declaration['image_count']} if declaration else task['spec']


def task_issues(project, spec, data):
    validate_declaration(spec)
    count = spec.get('image_count', len(spec['image_requests']) if 'image_requests' in spec else None)
    human = spec.get('kind', 'produce') == 'human'
    defaults = ['image'] if not human and spec['step'] in preferences.IMAGE_STEPS else []
    groups = spec.get('requires_preferences', defaults)
    editable = preferences.effective(project, data, strict=False)['editable']
    image_work = ('image' in groups or (not human and spec['step'] == 'editable-handoff'
                  and editable.get('route') == 'B' and editable.get('entry') == 'full'))
    if count is None:
        return ['Image-producing task must declare image_count or actual image_requests'] if image_work else []
    return capacity_issues(data, count)


def _key(job):
    return state.digest({'job_id': job['job_id'], 'input_digest': job['input_digest']})


def _entry(job, relative, kind):
    return {'job_id': job['job_id'], 'input_digest': job['input_digest'], 'job_path': relative,
            'purpose': job['purpose'], 'version': job.get('version'), 'route': job['route'],
            'kind': kind, 'counted_at': state.now()}


def _pending(project, paths):
    return [(path, job) for path in paths
            if (job := state.read_json(state.resolve(project, path))).get('status') == 'pending']


def _check_pending(data, jobs):
    if not jobs: return
    ledger = data.get('image_budget', {}).get('entries', {})
    if any(_key(job) in ledger for _, job in jobs):
        raise ValueError('Image reservation already exists for a pending job; outcome unknown, '
                         'reconcile actual provider evidence before recovery; never resubmit')
    issues = capacity_issues(data, len(jobs))
    if issues: raise ValueError('; '.join(issues))


def preflight(project, paths, resume=False):
    data = store.load_run(project)
    if data and not resume: _check_pending(data, _pending(project, paths))


def reserve_api(project, paths, evidence=''):
    """Caller holds all job locks. Persist the whole pending set before any HTTP call."""
    if not store.load_run(project): return set()
    with store.locked(project):
        data = store.load_run(project)
        jobs = _pending(project, paths)
        _check_pending(data, jobs)
        for _, job in jobs: preferences.require_image_job(project, job, evidence)
        for relative, job in jobs:
            data['image_budget']['entries'][_key(job)] = _entry(job, relative, 'api_attempt')
        if jobs: store.save_run(project, data, 'reserve-api-images')
        return {_key(job) for _, job in jobs}


def registered_builtin(project, relative, job, already_downloaded):
    """Called only after validating/preserving real image bytes, while holding its job lock."""
    active = store.load_run(project)
    if not active: return
    with store.locked(project):
        data = store.load_run(project, job.get('run_id'))
        if not data: return
        ledger = data.get('image_budget', {}).get('entries', {})
        key = _key(job)
        if key in ledger:
            if ledger[key].get('sha256') != job['sha256']:
                raise ValueError('Builtin registration has a different result; use a new version')
            return
        if already_downloaded: return
        if 'image_budget' not in data:
            data['image_budget'] = _ledger(history_unknown=True)
        entry = _entry(job, relative, 'builtin_registered')
        entry.update(output_path=job['output_path'], sha256=job['sha256'], tool_evidence=job['tool_evidence'])
        data['image_budget']['entries'][key] = entry
        store.save_run(project, data, 'register-builtin-image')
