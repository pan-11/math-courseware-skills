"""Shared course/run choices and bounded image consent; never adopts course artifacts."""
from copy import deepcopy
import re

from . import state, workflow, automation_store as store

GROUPS = {'image', 'video', 'editable'}
PURPOSES = {'test', 'cover', 'asset', 'page', 'erase', 'repair'}
IMAGE_STEPS = {'cover': 'cover', 'asset': 'asset', 'page-image': 'page',
               'video-script': 'asset', 'video-assets': 'asset', 'video-board': 'asset'}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def canonical(project):
    image = {}
    route = state.load_project(project).get('image_route')
    if route in state.ROUTES: image['route'] = route
    choice = workflow.load(project).get('route_choice', {})
    editable = {}
    if choice.get('route') in ('A', 'B') and _text(choice.get('user_evidence')):
        editable = {'route': choice['route'], 'evidence': choice['user_evidence']}
        if choice.get('entry') in ('full', 'returned'): editable['entry'] = choice['entry']
    return {'image': image, 'video': {}, 'editable': editable}


def conflicts(project, data):
    current = canonical(project)
    saved, basis = data.get('preferences', {}), data.get('preference_basis', {})
    return [group + '.' + field + ': canonical preference conflict; record the actual choice with run-configure'
            for group, fields in (('image', ('route',)), ('editable', ('route', 'entry')))
            for field in fields if field in current[group] and field in saved.get(group, {})
            and (current[group][field] != basis.get(group, {}).get(field)
                 or current[group].get('evidence') != basis.get(group, {}).get(
                     field + '_evidence', basis.get(group, {}).get('evidence')))
            and current[group][field] != saved[group][field]]


def effective(project, data=None, groups=GROUPS, strict=True):
    data = store.load_run(project) if data is None else data
    result = canonical(project)
    if data:
        issues = [item for item in conflicts(project, data) if item.split('.')[0] in groups]
        if strict and issues: raise ValueError('; '.join(issues))
        for group in GROUPS:
            result[group].update(deepcopy(data.get('preferences', {}).get(group, {})))
    return result


def scope(project):
    """Stage focus/evidence changes are not a change of the authorized course/module scope."""
    data = workflow.load(project)
    task = data.get('current_task', {})
    return {'project_mode': data.get('project_mode'), 'mode': task.get('mode'),
            'modules': sorted({m.removeprefix('math-courseware-') for m in task.get('modules', [])})
                       if task.get('mode') == 'selected_modules' else []}


def _requests(value, label):
    if not isinstance(value, list) or not value:
        raise ValueError(label + ' requires a nonempty list')
    for item in value:
        allowed = {'target_id', 'version', 'purpose'} if label == 'image_requests' else {'target_id', 'version'}
        if not isinstance(item, dict) or set(item) - allowed or not {'target_id', 'version'} <= set(item):
            raise ValueError(label + ' requires explicit target_id/version')
        if not isinstance(item['target_id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]+', item['target_id']):
            raise ValueError(label + ': invalid target_id')
        if not isinstance(item['version'], str) or not re.fullmatch(r'v\d{3,}', item['version']):
            raise ValueError(label + ': invalid version')
        if label == 'image_requests' and item.get('purpose') not in PURPOSES:
            raise ValueError('image_requests requires a supported purpose')
    if len({state.digest(item) for item in value}) != len(value):
        raise ValueError(label + ' contains duplicate requests')


def update(project, data, changes):
    if not isinstance(changes, dict) or not changes or set(changes) - GROUPS:
        raise ValueError('Provide nonempty known preference groups')
    result = effective(project, data, strict=False)
    basis = deepcopy(data.get('preference_basis', canonical(project)))
    context = deepcopy(data.get('image_authorization_context', {}))
    current = canonical(project)
    for group, patch in changes.items():
        fields = {'image': {'route', 'evidence', 'authorization'},
                  'video': {'platform', 'model', 'sound', 'evidence'},
                  'editable': {'route', 'entry', 'evidence'}}[group]
        if not isinstance(patch, dict) or not patch or set(patch) - fields:
            raise ValueError('Invalid or unknown ' + group + ' preference')
        if set(patch) - {'authorization'} and not _text(patch.get('evidence')):
            raise ValueError(group + ': actual nonempty evidence required with each update')
        for field, value in patch.items():
            if field == 'authorization': continue
            if not _text(value): raise ValueError(group + '.' + field + ': nonempty text required')
            options = (state.ROUTES if group == 'image' else ('A', 'B')) if field == 'route' else (
                ('full', 'returned') if field == 'entry' else None)
            if options and value not in options: raise ValueError(group + '.' + field + ': invalid choice')
            result[group][field] = value
            if field in ('route', 'entry'):
                basis.setdefault(group, {})[field] = current[group].get(field)
                basis[group][field + '_evidence'] = current[group].get('evidence')
        if 'authorization' in patch:
            auth_patch = patch['authorization']
            if (not isinstance(auth_patch, dict) or not auth_patch
                    or set(auth_patch) - {'scope', 'purposes', 'paid_generation', 'include_rework', 'scope_evidence', 'targets'}
                    or not _text(auth_patch.get('scope_evidence'))):
                raise ValueError('image.authorization requires actual scope_evidence and known fields')
            for field, value in auth_patch.items():
                if field == 'scope' and value not in ('run', 'targets'):
                    raise ValueError('image.authorization scope must be run or targets')
                if field in ('paid_generation', 'include_rework') and type(value) is not bool:
                    raise ValueError(field + ' must be an explicit boolean')
                if field == 'purposes' and (not isinstance(value, list) or not value
                        or any(not isinstance(v, str) or v not in PURPOSES for v in value)
                        or len(set(value)) != len(value)):
                    raise ValueError('image.authorization purposes must be known unique image purposes')
                if field == 'targets': _requests(value, 'targets')
            auth = {**result['image'].get('authorization', {}), **deepcopy(auth_patch)}
            if auth.get('scope') == 'targets' and not auth.get('targets'):
                raise ValueError('targets scope requires explicit target/version selection')
            if auth_patch.get('scope') == 'run' and 'targets' in auth_patch:
                raise ValueError('run scope conflicts with explicit targets; use targets scope')
            result['image']['authorization'] = auth
            context = {'scope': scope(project), 'route': result['image'].get('route')}
    # Do not let an unrelated update silently hide a new canonical route conflict.
    candidate = {**data, 'preferences': result, 'preference_basis': basis}
    unresolved = [item for item in conflicts(project, candidate) if item.split('.')[0] in changes]
    if unresolved: raise ValueError('; '.join(unresolved))
    data.update(preferences=result, preference_basis=basis, image_authorization_context=context)


def missing(values):
    required = {'image': ('route', 'authorization'), 'video': ('platform', 'model', 'sound', 'evidence'),
                'editable': ('route', 'entry', 'evidence')}
    result = [group + '.' + field for group, fields in required.items()
              for field in fields if not values.get(group, {}).get(field)]
    auth = values.get('image', {}).get('authorization', {})
    if auth:
        result += ['image.authorization.' + field for field in ('scope', 'purposes', 'scope_evidence', 'paid_generation')
                   if field not in auth]
    return result


def image_authorization_issues(project, requests, route, data=None):
    data = store.load_run(project) if data is None else data
    if not data: return ['image.authorization: actual batch authorization required']
    issues = [item for item in conflicts(project, data) if item.startswith('image.')]
    image = effective(project, data, strict=False)['image']
    auth = image.get('authorization', {})
    context = data.get('image_authorization_context', {})
    if not auth or any(field not in auth for field in ('scope', 'purposes', 'paid_generation', 'scope_evidence')):
        return issues + ['image.authorization: complete actual generation authorization required']
    if context.get('scope') != scope(project): issues.append('image.authorization: current course/module scope differs')
    if route != image.get('route') or route != context.get('route'):
        issues.append('image.authorization: route differs from authorized choice')
    if route == 'openai_image_api' and auth.get('paid_generation') is not True:
        issues.append('image.authorization: explicit paid generation authorization required')
    for job in requests:
        if job.get('run_id', data['run_id']) != data['run_id']:
            issues.append('image.authorization: job belongs to another run')
        if job.get('purpose') not in auth['purposes']:
            issues.append('image.authorization: purpose outside authorized scope')
        if (job.get('purpose') == 'repair' or job.get('version', 'v001') != 'v001') and not auth.get('include_rework', False):
            issues.append('image.authorization: rework is outside authorized scope')
        if auth['scope'] == 'targets' and {'target_id': job.get('target_id'), 'version': job.get('version', 'v001')} not in auth.get('targets', []):
            issues.append('image.authorization: target/version outside authorized scope')
    return list(dict.fromkeys(issues))


def task_issues(project, spec, data):
    values = effective(project, data, strict=False)
    step = spec['step']
    human = spec.get('kind', 'produce') == 'human'
    default = (['video'] if step == 'video-upload' else [] if human
               else ['image'] if step in IMAGE_STEPS
               else ['editable'] if step.startswith('editable-') else [])
    groups = set(spec.get('requires_preferences', default))
    if 'image_requests' in spec or (not human and step == 'editable-handoff'
            and values['editable'].get('route') == 'B' and values['editable'].get('entry') == 'full'):
        groups.add('image')
    issues = [item for item in conflicts(project, data) if item.split('.')[0] in groups]
    issues += ['Missing preference: ' + item for item in missing(values) if item.split('.')[0] in groups]
    if 'image' in groups:
        requests = spec.get('image_requests', [{'purpose': IMAGE_STEPS.get(step, 'erase'), 'version': 'v001'}])
        issues += image_authorization_issues(project, requests, values['image'].get('route'), data)
    return list(dict.fromkeys(issues))


def bind_pending_jobs(project, run_id, paths):
    """Reuse unchanged manual pending inputs without rewriting historical job records."""
    with store.locked(project):
        data = store.load_run(project)
        if not data or data['run_id'] != run_id: raise ValueError('Active run changed while preparing images')
        bindings = dict(data.get('image_job_bindings', {}))
        for path in paths:
            job = state.read_json(state.resolve(project, path))
            if job.get('status') == 'pending' and not job.get('run_id'):
                bindings[job['job_id']] = job['input_digest']
        if bindings != data.get('image_job_bindings', {}):
            data['image_job_bindings'] = bindings
            store.save_run(project, data, 'bind-pending-image-jobs')


def require_image_job(project, job, evidence=''):
    """Call only before new generation; recovered old responses never need a new grant."""
    data = store.load_run(project)
    if not data: return  # The existing manual batch entry enforces its route and explicit evidence.
    route = effective(project, data, groups={'image'})['image'].get('route')
    if job.get('route') != route: raise ValueError('Job route differs from current image selection')
    if _text(evidence): return
    bound = (not job.get('run_id') and job.get('input_digest')
             and data.get('image_job_bindings', {}).get(job.get('job_id')) == job['input_digest'])
    if job.get('run_id') != data['run_id'] and not bound:
        raise ValueError('Actual batch authorization required for a job outside this run')
    issues = image_authorization_issues(project, [job], route, data)
    if issues: raise ValueError('; '.join(issues))
