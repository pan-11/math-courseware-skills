"""Opt-in persistent host-session queue. Dispatches instructions, never shell commands."""
from copy import deepcopy
from pathlib import Path
import re

from . import state, workflow, review, preferences, image_budget, calibration, automation_store as store

RUBRIC = {step: ('source' if step == 'analysis' else
                 'video' if step.startswith('video-') else
                 'visual' if step in ('cover', 'asset', 'page-image') else
                 'delivery' if step in ('image-export', 'editable-handoff', 'editable-import',
                                       'editable-build', 'collect', 'complete') else 'teaching')
          for step in workflow.STEPS}
MEDIA_STEPS = {'cover', 'asset', 'page-image', 'video-script', 'video-assets',
               'video-board', 'video-upload', 'editable-handoff'}


def _external(task):
    spec = image_budget.task_spec(task)
    return (spec['step'] in MEDIA_STEPS or spec.get('side_effects') == 'external'
            or 'image_count' in spec or 'image_requests' in spec)


def _load(project):
    return store.load_run(project)


def _save(project, data, event):
    store.save_run(project, data, event)


def _validate_tasks(project, tasks):
    if not isinstance(tasks, list) or not tasks or len(tasks) > 200:
        raise ValueError('Provide a nonempty concrete queue of at most 200 tasks')
    ids = [t.get('id') for t in tasks if isinstance(t, dict)]
    if len(ids) != len(tasks) or any(not isinstance(i, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', i) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Task IDs must be unique simple identifiers')
    for task in tasks:
        step = task.get('step')
        if step not in workflow.STEPS or task.get('kind', 'produce') not in ('produce', 'human'):
            raise ValueError('Task needs a supported workflow step and produce/human kind')
        if step == 'complete' and task.get('kind') != 'human':
            raise ValueError('Whole-course final acceptance remains a human task in P1/P2')
        if step in workflow.VIDEO_STEPS and not str(task.get('video_id', '')).strip():
            raise ValueError('Video tasks require an actual video_id')
        if not isinstance(task.get('instruction'), str) or not task['instruction'].strip():
            raise ValueError('Each task needs a concrete instruction/return requirement')
        deps = task.get('depends_on', [])
        if not isinstance(deps, list) or len(set(deps)) != len(deps) or set(deps) - set(ids):
            raise ValueError('Task dependencies must reference existing unique IDs')
        inputs, outputs = task.get('inputs'), task.get('outputs')
        if not isinstance(inputs, list) or not inputs or not isinstance(outputs, list) or not outputs:
            raise ValueError('Each task needs real input paths and required output role names')
        for path in inputs: store.relative(project, path)
        if any(not isinstance(role, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+', role) for role in outputs) or len(set(outputs)) != len(outputs):
            raise ValueError('Output roles must be unique names')
        if task.get('side_effects', 'local') not in ('local', 'external'):
            raise ValueError('side_effects must be local or external')
        if type(task.get('max_attempts', 2)) is not int or not 1 <= task.get('max_attempts', 2) <= 3:
            raise ValueError('Use a bounded max_attempts between one and three')
        if 'requires_preferences' in task:
            groups = task['requires_preferences']
            if (not isinstance(groups, list) or any(not isinstance(g, str) or g not in preferences.GROUPS for g in groups)
                    or len(set(groups)) != len(groups)):
                raise ValueError('requires_preferences must name unique image/video/editable groups')
        if 'image_requests' in task: preferences._requests(task['image_requests'], 'image_requests')
        image_budget.validate_declaration(task)
    remaining = {t['id']: set(t.get('depends_on', [])) for t in tasks}
    while remaining:
        ready = {name for name, deps in remaining.items() if not deps}
        if not ready: raise ValueError('Task dependency cycle')
        remaining = {name: deps - ready for name, deps in remaining.items() if name not in ready}


def _new_task(task):
    return {'spec': deepcopy(task), 'status': 'pending', 'attempt': 0, 'history': []}


def start(project, plan):
    evidence = plan.get('activation_evidence', '')
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError('Actual explicit automatic-mode activation evidence required')
    tasks = plan.get('tasks')
    _validate_tasks(project, tasks)
    with store.locked(project):
        existing = _load(project)
        if existing:
            if existing['plan_digest'] == state.digest(plan):
                calibration.recover(project, existing)
                return status(project)
            raise ValueError('A queue already exists; switch/resume or extend it without replacing progress')
        store.directory(project, store.AREA + '/runs')
        data = {'schema_version': '1.0', 'run_id': store.identifier('run'),
                'project': str(Path(project).resolve()), 'mode': 'automatic', 'paused': False,
                'activation_evidence': evidence, 'scope': store.scope(project),
                'plan_digest': state.digest(plan), 'revision': 0,
                'preferences': preferences.canonical(project),
                'preference_basis': preferences.canonical(project),
                'tasks': [_new_task(t) for t in tasks]}
        if 'preferences' in plan: preferences.update(project, data, plan['preferences'])
        image_budget.initialize(data, plan.get('limits'))
        choices = {**plan.get('preferences', {})}
        if 'limits' in plan: choices['limits'] = plan['limits']
        calibration.settings(project, data, choices)
        _save(project, data, 'start')
        state.write_json(state.resolve(project, store.AREA + '/active.json'), {'run_id': data['run_id']})
        return status(project)


def configure(project, settings):
    if not _load(project): raise ValueError('No queue to configure; absent queues remain manual')
    if (not isinstance(settings, dict) or not settings
            or set(settings) - (preferences.GROUPS | {'limits', 'image_declarations', 'human_reason'})
            or not set(settings) & (preferences.GROUPS | {'limits', 'image_declarations'})):
        raise ValueError('Provide known preference groups, limits or missing image declarations with actual evidence')
    with store.locked(project):
        data = _load(project)
        choices = {key: value for key, value in settings.items() if key in preferences.GROUPS}
        if choices: preferences.update(project, data, choices)
        if 'limits' in settings: image_budget.configure(data, settings['limits'])
        if 'image_declarations' in settings: image_budget.amend_declarations(data, settings['image_declarations'])
        calibration.validate_metadata(settings)
        calibration.settings(project, data, settings)
        _save(project, data, 'configure-settings')
        return status(project)


def extend(project, tasks, evidence):
    if not isinstance(evidence, str) or not evidence.strip(): raise ValueError('Scope evidence for the concrete extension required')
    with store.locked(project):
        data = _load(project)
        if not data: raise ValueError('Start a queue first')
        old = {t['spec']['id']: t['spec'] for t in data['tasks']}
        additions = []
        for task in tasks:
            if task.get('id') in old:
                if task != old[task['id']]: raise ValueError('Cannot rewrite an existing task; use a new versioned ID')
            else: additions.append(task)
        _validate_tasks(project, list(old.values()) + additions)
        if additions:
            data['tasks'].extend(_new_task(t) for t in additions)
            data['extension_evidence'] = evidence
            _save(project, data, 'extend')
        return status(project)


def _gate(project, task, data=None):
    spec = image_budget.task_spec(task)
    gate = workflow.check(project, spec['step'], video_id=spec.get('video_id'))
    if data is not None:
        gate['issues'] += preferences.task_issues(project, spec, data)
        gate['issues'] += image_budget.task_issues(project, spec, data)
        gate['allowed'] = not gate['issues']
    return gate


def _sources(project, data, task):
    expected = store.versions(project, task['spec']['inputs'])
    dependencies = set(task['spec'].get('depends_on', []))
    for item in data['tasks']:
        if item['spec']['id'] in dependencies:
            expected.update(item.get('output_versions', {}))
    problems = store.issues(project, expected)
    if problems: raise ValueError('; '.join(problems))
    return expected


def _refresh(project, data):
    for task in data['tasks']:
        if task.pop('blocked_by_upstream', False):
            task['issues'] = [issue for issue in task.get('issues', []) if issue != 'An upstream task is stale']
        if task['status'] in ('done', 'review_ready', 'reviewing', 'needs_revision', 'unverified'):
            problems = store.issues(project, task.get('input_versions', {}))
            problems += store.issues(project, task.get('output_versions', {}))
            problems += store.binding_issues(project, task.get('bindings', []))
            if problems:
                task.update(status='stale', issues=problems)
                continue
        if task['status'] in ('review_ready', 'reviewing', 'done') and task.get('packet'):
            result = review.status(project, task['packet'])
            if result['issues']: task.update(status='stale', issues=result['issues'])
            elif result['pending'] and task['status'] == 'done':
                task.update(status='stale', issues=['Completed task no longer has its independent review'])
            elif result['valid']:
                digest = state.sha256(state.resolve(project, task['packet']).with_name('result.json'))
                if task.get('review_result_sha256') and task['review_result_sha256'] != digest:
                    task.update(status='stale', issues=['Recorded independent review changed'])
                    continue
                task['review_result_sha256'] = digest
                task['findings'] = result['report']['checks']
                task['status'] = {'pass': 'done', 'changes_required': 'needs_revision',
                                  'unverified': 'unverified'}[result['verdict']]
    # Propagate downstream even when a producer's old physical files still exist.
    changed = True
    while changed:
        changed = False
        invalid = {t['spec']['id'] for t in data['tasks']
                   if t['status'] == 'stale' or t.get('blocked_by_upstream')}
        for task in data['tasks']:
            if task['spec']['id'] not in invalid and set(task['spec'].get('depends_on', [])) & invalid:
                if task['status'] == 'waiting_external' and task['spec'].get('kind') == 'human':
                    # Retain the original reply channel after the human rejects its producer.
                    task.update(blocked_by_upstream=True, issues=['An upstream task is stale'])
                else:
                    task.update(status='stale', issues=['An upstream task is stale'])
                changed = True


def status(project):
    data = _load(project)
    if not data: return {'mode': 'manual', 'run_id': None, 'tasks': [], 'whole_course_complete': False}
    _refresh(project, data)
    effective = preferences.effective(project, data, strict=False)
    return {**data, 'whole_course_complete': False,
            'calibration': calibration.summary(project, data),
            'image_budget_status': image_budget.summary(data),
            'preferences': effective, 'missing_preferences': preferences.missing(effective),
            'preference_issues': preferences.conflicts(project, data),
            'scope_matches': data['scope'] == store.scope(project),
            'queue_complete': all(t['status'] == 'done' for t in data['tasks'])}


def _claim(project, data, task, actor):
    task['input_versions'] = _sources(project, data, task)
    task['bindings'] = store.bindings(project, task['input_versions'])
    task['attempt'] += 1
    task['claim'] = store.identifier('claim')
    task['producer_id'] = actor
    task['preferences'] = preferences.effective(project, data, strict=False)
    task['review_attempt'] = 0
    task.pop('review_result_sha256', None)
    task['status'] = 'waiting_external' if task['spec'].get('kind', 'produce') == 'human' else 'running'
    task['history'].append({'claim': task['claim'], 'attempt': task['attempt'], 'at': state.now()})


def _action(task):
    result = {'task': image_budget.task_spec(task), 'claim': task.get('claim'), 'attempt': task['attempt'],
            'preferences': task.get('preferences', {}),
            'owner': 'math-courseware-' + workflow.OWNERS.get(task['spec']['step'], 'studio'),
            'input_versions': task.get('input_versions', {}), 'findings': task.get('findings', []),
            'issues': task.get('issues', []), 'blocked_by_upstream': task.get('blocked_by_upstream', False),
            'instruction': task['spec']['instruction'], 'external_submission_guard': _external(task)}
    if 'image_declaration' in task: result['image_declaration'] = task['image_declaration']
    return result


def next_task(project, actor):
    if not isinstance(actor, str) or not actor.strip(): raise ValueError('Host/producer identity required')
    data = _load(project)
    if not data: return {'action': 'manual', 'whole_course_complete': False}
    with store.locked(project):
        data = _load(project)
        calibration.recover(project, data)
        if data['mode'] == 'manual': return {'action': 'manual', 'whole_course_complete': False}
        if data['paused']: return {'action': 'paused', 'whole_course_complete': False}
        if data['scope'] != store.scope(project):
            return {'action': 'waiting', 'issues': ['Current task scope changed; explicitly reconcile the queue scope'],
                    'whole_course_complete': False}
        _refresh(project, data)
        done = {t['spec']['id'] for t in data['tasks'] if t['status'] == 'done'}
        for task in data['tasks']:
            if task['status'] == 'needs_revision' and not _external(task) and task['attempt'] < task['spec'].get('max_attempts', 2):
                task['status'] = 'pending'
            if task['status'] == 'pending' and set(task['spec'].get('depends_on', [])) <= done:
                gate = _gate(project, task, data)
                task['issues'] = gate['issues']
                if gate['allowed'] and task['spec'].get('kind', 'produce') == 'human':
                    try: _claim(project, data, task, 'human')
                    except (OSError, ValueError) as exc: task['issues'] = [str(exc)]
        humans = [_action(t) for t in data['tasks'] if t['status'] == 'waiting_external']
        effective = preferences.effective(project, data, strict=False)
        common = {'run_id': data['run_id'], 'human_tasks': humans, 'whole_course_complete': False,
                  'image_budget_status': image_budget.summary(data),
                  'preferences': effective, 'missing_preferences': preferences.missing(effective),
                  'preference_issues': preferences.conflicts(project, data)}
        for task in data['tasks']:
            if task['status'] in ('running', 'reviewing'):
                _save(project, data, 'recover-inflight')
                return {**common, **_action(task), 'action': 'recover',
                        'packet': task.get('packet'), 'issues': ['Inspect this claim; do not redispatch blindly']}
        for task in data['tasks']:
            if task['status'] == 'review_ready':
                task['status'] = 'reviewing'
                _save(project, data, 'dispatch-review')
                return {**common, **_action(task), 'action': 'review', 'packet': task['packet']}
        for task in data['tasks']:
            if task['status'] == 'pending' and task['spec'].get('kind', 'produce') == 'produce' and set(task['spec'].get('depends_on', [])) <= done:
                gate = _gate(project, task, data)
                task['issues'] = gate['issues']
                if not gate['allowed']: continue
                try: _claim(project, data, task, actor)
                except (OSError, ValueError) as exc:
                    task['issues'] = [str(exc)]; continue
                _save(project, data, 'dispatch-produce')
                return {**common, **_action(task), 'action': 'produce'}
        _save(project, data, 'inspect-waits')
        complete = all(t['status'] == 'done' for t in data['tasks'])
        return {**common, 'action': 'queue_complete' if complete else 'waiting',
                'blocked': [{'id': t['spec']['id'], 'status': t['status'], 'issues': t.get('issues', []),
                             'instruction': t['spec']['instruction'], 'findings': t.get('findings', [])}
                            for t in data['tasks'] if t['status'] != 'done']}


def record(project, result):
    calibration.validate_metadata(result)
    with store.locked(project):
        data = _load(project)
        if not data: raise ValueError('No active queue')
        _refresh(project, data)
        task = next((t for t in data['tasks'] if t['spec']['id'] == result.get('task_id')), None)
        if not task or result.get('claim') != task.get('claim'):
            raise ValueError('Current task and claim token required')
        digest = state.digest(result)
        replayed, replay_signature = calibration.receipt_replay(project, data, task, result)
        human_receipt = task['spec'].get('kind') == 'human' and result.get('status') in ('completed', 'returned')
        if (((not human_receipt or not task.get('last_human_receipt')) and task.get('last_result_digest') == digest) or
                (replayed and task.get('last_human_receipt') == {
                    'signature': replay_signature, 'event_id': replayed['event_id']})):
            calibration.recover(project, data)
            return _action(task) | {'status': task['status']}
        if data['scope'] != store.scope(project): raise ValueError('Current task scope changed')
        if task['status'] not in ('running', 'waiting_external', 'unknown'):
            raise ValueError('Task is not awaiting this result')
        requested = result.get('status')
        if task['status'] == 'unknown' and requested not in ('produced', 'completed'):
            raise ValueError('Unknown submissions need recovered actual outputs; no blind retry')
        if requested in ('failed', 'unknown'):
            if not str(result.get('message', '')).strip(): raise ValueError('Actual failure/unknown evidence required')
            task.update(status=requested, issues=[result['message']])
        elif requested in ('produced', 'completed', 'returned'):
            human = task['spec'].get('kind', 'produce') == 'human'
            returned = requested == 'returned'
            if returned and (not human or task['status'] != 'waiting_external'
                    or not isinstance(result.get('human_decision'), str) or not result['human_decision'].strip()):
                raise ValueError('Only a waiting human task may record an actual returned decision')
            if human and requested == 'completed' and (result.get('human_decision') in ('rejected', 'changes_required')
                    or str(result.get('human_decision', '')).startswith('partial')):
                raise ValueError('Rejected/partial human decisions must use returned and cannot complete a task')
            dependencies = set(task['spec'].get('depends_on', []))
            if not returned and any(t['spec']['id'] in dependencies and t['status'] != 'done' for t in data['tasks']):
                raise ValueError('Upstream work no longer passes current review')
            problems = store.issues(project, task['input_versions']) + store.binding_issues(project, task['bindings'])
            gate = _gate(project, task)
            if returned: problems = [p for p in problems if not p.startswith('Latest user decision rejects: ')]
            if problems or (not returned and not gate['allowed']): raise ValueError('; '.join(problems + gate['issues']))
            artifacts = result.get('artifacts', {})
            if not isinstance(artifacts, dict) or set(artifacts) != set(task['spec']['outputs']):
                raise ValueError('Actual output files must cover every declared output role exactly')
            expected = store.versions(project, list(artifacts.values()))
            problems = store.issues(project, expected)
            if returned: problems = [p for p in problems if not p.startswith('Latest user decision rejects: ')]
            if problems: raise ValueError('; '.join(problems))
            if human:
                if requested not in ('completed', 'returned') or not isinstance(result.get('user_evidence'), str) or not result['user_evidence'].strip():
                    raise ValueError('Human operation needs actual returned files and user completion evidence')
                event = replayed or calibration.receipt(project, data, task, result, expected)
                calibration.remember(data, event)
                task['last_human_receipt'] = {'signature': calibration.receipt_identity(project, result, expected),
                                            'event_id': event['event_id']}
                task['history'][-1]['human_event_id'] = event['event_id']
                task.update(status='waiting_external' if returned else 'done', user_evidence=result['user_evidence'])
            else:
                if requested != 'produced': raise ValueError('Production requires an independent review before completion')
                previous = {p for entry in task['history'] for p in entry.get('outputs', {})}
                if previous & set(expected):
                    raise ValueError('Revision must use new versioned output files; preserve prior attempts')
                packet = review._prepare(project, {
                    'rubric': RUBRIC[task['spec']['step']], 'producer_id': task['producer_id'],
                    'artifacts': list(expected), 'sources': list(task['input_versions']),
                    'instruction': task['spec']['instruction']})
                task.update(status='review_ready', packet=packet['packet'])
                task['review_attempt'] = task.get('review_attempt', 0) + 1
            task['output_versions'] = expected
            task['bindings'] = store.bindings(project, {**task['input_versions'], **expected})
            task['history'][-1]['outputs'] = expected
        else: raise ValueError('Use produced, completed, returned, failed or unknown')
        task['last_result_digest'] = digest
        _save(project, data, 'record-' + requested)
        return _action(task) | {'status': task['status'], 'packet': task.get('packet')}


def control(project, mode=None, paused=None, evidence=''):
    if not isinstance(evidence, str) or not evidence.strip(): raise ValueError('Actual mode/pause/resume evidence required')
    if mode not in (None, 'manual', 'automatic') or paused not in (None, True, False):
        raise ValueError('Unsupported control value')
    with store.locked(project):
        data = _load(project)
        if not data: raise ValueError('No queue to control; absent queues remain manual')
        if mode is not None: data['mode'] = mode
        if paused is not None: data['paused'] = paused
        data['control_evidence'] = evidence
        _save(project, data, 'control')
        return status(project)


def retry(project, task_id, evidence):
    if not isinstance(evidence, str) or not evidence.strip(): raise ValueError('Concrete recovery evidence required')
    with store.locked(project):
        data = _load(project)
        if not data: raise ValueError('No queue')
        _refresh(project, data)
        task = next((t for t in data['tasks'] if t['spec']['id'] == task_id), None)
        if not task or task['status'] not in ('failed', 'stale', 'needs_revision', 'unverified'):
            raise ValueError('Only a resolved failure, changed version or review issue may be retried')
        if task['attempt'] >= task['spec'].get('max_attempts', 2): raise ValueError('Attempt limit reached; revise the plan explicitly')
        if _external(task):
            raise ValueError('External work is not automatically retried; reconcile actual platform work first')
        task.update(status='pending', retry_evidence=evidence, issues=[])
        _save(project, data, 'retry')
        return status(project)


def reconcile(project, evidence):
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError('Actual instruction to reconcile the current scope required')
    with store.locked(project):
        data = _load(project)
        if not data: raise ValueError('No queue')
        data['scope'] = store.scope(project)
        data['scope_reconciliation_evidence'] = evidence
        _refresh(project, data)
        _save(project, data, 'reconcile-scope')
        return status(project)


def recheck(project, task_id, evidence):
    """Reinspect unchanged outputs when missing observation becomes available; no regeneration."""
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError('Actual reason/evidence for renewed independent inspection required')
    with store.locked(project):
        data = _load(project)
        if not data: raise ValueError('No queue')
        _refresh(project, data)
        task = next((t for t in data['tasks'] if t['spec']['id'] == task_id), None)
        if not task or task['status'] != 'unverified':
            raise ValueError('Recheck is only for unchanged outputs with an unverified report')
        if data['scope'] != store.scope(project): raise ValueError('Current task scope changed')
        if task.get('review_attempt', 1) >= 2:
            raise ValueError('Review attempt limit reached; inspect the remaining evidence gap')
        packet = review._prepare(project, {
            'rubric': RUBRIC[task['spec']['step']], 'producer_id': task['producer_id'],
            'artifacts': list(task['output_versions']), 'sources': list(task['input_versions']),
            'instruction': task['spec']['instruction']})
        task.update(status='review_ready', packet=packet['packet'], recheck_evidence=evidence,
                    review_attempt=task.get('review_attempt', 1) + 1)
        task.pop('review_result_sha256', None)
        _save(project, data, 'recheck-unchanged-output')
        return status(project)
