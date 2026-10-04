"""Explicit full-course creative groups; actual decisions remain in decisions.jsonl.

Snapshots describe existing reviewed files, never permission for future artifacts.
Default/manual workflow checks remain authoritative outside this narrow policy.
"""
from copy import deepcopy

from . import state, automation_store as store

POLICY = 'grouped_creative_v1'
GROUPS = {'video-creative': 'video-assets', 'video-direction': 'video-board'}
FINAL_CHECKS = ('editable_text', 'teaching_graphics', 'video_regions_layers',
                'fonts_wrapping_overlap', 'all_pages_animations', 'all_video_playback_audio',
                'interactive_worksheet_blackboard')


def validate_policy(project, plan):
    if 'review_policy' not in plan:
        if 'review_policy_evidence' in plan:
            raise ValueError('review_policy_evidence needs an explicit review_policy')
        return
    if plan['review_policy'] != POLICY:
        raise ValueError('Unknown review_policy')
    if not isinstance(plan.get('review_policy_evidence'), str) or not plan['review_policy_evidence'].strip():
        raise ValueError('review_policy needs actual selection evidence')
    scope = store.scope(project)
    if scope.get('project_mode') != 'full_course' or scope.get('current_task', {}).get('mode') != 'full_course':
        raise ValueError('grouped_creative_v1 requires full_course scope')


def active(project, run=None):
    run = store.load_run(project) if run is None else run
    if not run or run.get('review_policy') != POLICY or run.get('mode') != 'automatic':
        return False
    scope = store.scope(project)
    return (bool(run.get('review_policy_evidence', '').strip()) and run.get('scope') == scope
            and scope.get('project_mode') == 'full_course'
            and scope.get('current_task', {}).get('mode') == 'full_course')


def validate_tasks(tasks, policy):
    for task in tasks:
        group = task.get('review_group')
        if group is not None and (policy != POLICY or not isinstance(group, str) or group not in GROUPS
                or task.get('kind') != 'human' or task.get('step') != GROUPS[group]
                or task.get('video_id')):
            raise ValueError('review_group requires its automatic policy and a whole-group human task')
        if policy == POLICY and task.get('kind') == 'human':
            node = task.get('human_node')
            if node in ('H06', 'H07', 'H09') and group != 'video-creative':
                raise ValueError('H06/H07/H09 use one video-creative group')
            if node == 'H08' and group != 'video-direction':
                raise ValueError('H08 covers all shots in one video-direction group')
            if node == 'H19':
                raise ValueError('H19 is displayed at C6 and checked in H23, not a separate human task')


def snapshot(project, name, run=None):
    """Read the current relevant graph without requiring this group's own adoption."""
    from . import workflow
    run = store.load_run(project) if run is None else run
    if not isinstance(name, str) or name not in GROUPS or not active(project, run):
        return {'issues': ['Creative groups require the explicit current automatic full_course policy'],
                'targets': [], 'identity': None}
    data = workflow.load(project)
    audit = workflow.Inspection(project, data)
    plan = audit.blueprint()
    records, targets, versions, routes, pointers = {}, {}, {}, {}, {}

    def add(label, record, roles=(), visual=False):
        files = audit.evidence(record, label, roles)
        if visual: audit.visual(record, label)
        records[label] = {k: deepcopy(v) for k, v in record.items() if k != 'approval'}
        for item in files.values():
            if isinstance(item, dict) and item.get('path') and item.get('sha256'):
                targets[item['path']] = item['sha256']
                versions[item['path']] = item['sha256']
        versions.update(record.get('source_versions', {}))
        if record.get('review', {}).get('path'):
            versions[record['review']['path']] = record['review']['sha256']

    videos = {}
    for vid in plan.get('video_ids', []):
        route, video = audit.video(vid)
        routes[vid], videos[vid] = route, video
        # A new manifest for the same files is a real pointer change; later products in
        # the same manifest must not invalidate already adopted earlier products.
        pointers[vid] = data.get('videos', {}).get(vid, {}).get('path')
    shots = [vid for vid in videos if routes[vid] == 'shots']
    if name == 'video-direction':
        audit.need(bool(shots), 'video-direction: no shots videos; talking needs no director/board')
        previous = adopted(project, 'video-creative', run)
        audit.need(previous['approved'], 'video-direction: actual current video-creative group adoption required')
    else:
        previous = None

    shared = data.get('stages', {}).get('shared-assets', {})
    if name == 'video-creative':
        audit.stage('shared-assets')
        add('shared-assets', shared, visual=True)
        canonical = {'path': '_state/assets.json', 'sha256': ''}
        try: canonical['sha256'] = state.sha256(state.resolve(project, canonical['path']))
        except OSError: audit.need(False, 'shared-assets: missing canonical _state/assets.json')
        audit.need(canonical in shared.get('files', {}).values(),
                   'shared-assets: include current canonical _state/assets.json in this actual group')
        assets = audit.json_file(canonical, 'shared-assets/canonical').get('assets', [])
        indexed = {a.get('asset_id'): a for a in assets if isinstance(a, dict)}
        required = set()
        for video in videos.values():
            refs = video.get('products', {}).get('script', {}).get('asset_ids', [])
            audit.need(isinstance(refs, list) and bool(refs) and all(isinstance(r, str) for r in refs),
                       'script: declare all actual shared character/scene/prop asset_ids')
            if isinstance(refs, list): required.update(r for r in refs if isinstance(r, str))
        for aid in sorted(required):
            asset = indexed.get(aid, {})
            audit.need(bool(asset), 'shared-assets: missing required asset ' + aid)
            files = asset.get('files', [])
            files = list(files.values()) if isinstance(files, dict) else files
            audit.need(isinstance(files, list) and bool(files), 'shared-assets: actual asset files required for ' + aid)
            for item in files if isinstance(files, list) else []:
                audit.need(isinstance(item, dict) and item in shared.get('files', {}).values(),
                           'shared-assets: required actual asset not displayed: ' + aid)
                if isinstance(item, dict): audit.visual({'files': {'asset': item}}, 'shared-assets/' + aid)
        choice = shared.get('style_choice', {})
        if choice.get('kind') == 'existing':
            selected = choice.get('selected', {})
            audit.evidence({**shared, 'files': {'selected': selected}}, 'shared-assets/existing-master', approved=True)
        for candidate in choice.get('candidates', []):
            if isinstance(candidate, dict):
                versions[candidate.get('path', '')] = candidate.get('sha256')
                audit.need(candidate == choice.get('selected') or candidate not in shared.get('files', {}).values(),
                           'shared-assets: only the selected candidate belongs to adoption targets')

    chains = {'voice': ('script',), 'preview': ('script',), 'first-frame': ('script',),
              'director': ('script', 'voice', 'assets'), 'storyboard': ('director', 'assets'),
              'style': ('assets', 'storyboard')}
    for vid, video in videos.items():
        route = routes[vid]
        products = video.get('products', {})
        if name == 'video-creative':
            names = ['script', 'voice'] + (['preview', 'assets'] if route == 'shots' else ['first-frame', 'prompts'])
        else:
            if route != 'shots': continue
            names = ['director', 'storyboard', 'style', 'prompts']
        for product in names:
            record = products.get(product, {})
            add(vid + '/' + product, record,
                visual=product in ('preview', 'assets', 'first-frame', 'storyboard', 'style'))
            deps = chains.get(product, ())
            if product == 'prompts':
                deps = ('script', 'first-frame') if route == 'talking' else ('script', 'voice', 'director', 'storyboard', 'style')
            audit.bind(record, vid + '/' + product, *(products.get(d, {}) for d in deps))
            if product == 'script':
                audit.bind(record, vid + '/script', plan)
                audit.need(record.get('complete') is True, vid + '/script: complete actual script required')
            elif product == 'voice':
                audit.need(record.get('verbatim') is True, vid + '/voice: complete verbatim sound/dialogue required')
            elif product == 'preview':
                audit.need(record.get('panel_count') == 25, vid + '/preview: actual 25-panel story preview required')
            elif product == 'assets':
                audit.bind(record, vid + '/assets', shared)
            elif product == 'first-frame':
                audit.need(record.get('color') is True, vid + '/first-frame: actual color first frame required')
            elif product == 'storyboard':
                audit.need(record.get('formal') is True and record.get('black_white') is True,
                           vid + '/storyboard: formal black-and-white board required')
            elif product == 'prompts':
                audit.need(record.get('complete') is True, vid + '/prompts: complete actual prompt packet required')
        if route == 'talking' or name == 'video-direction':
            prep = video.get('preparation', {})
            roles = ['script', 'voice', 'frame_plan', 'prompts', 'production', 'classroom']
            if route == 'shots': roles += ['director', 'board_plan']
            add(vid + '/preparation', prep, roles)
            audit.bind(prep, vid + '/preparation', plan, *products.values())
    if name == 'video-direction' or not shots:
        ready = data.get('stages', {}).get('video-preparation', {})
        add('video-preparation', ready)
        audit.need(set(ready.get('video_ids', [])) == set(videos), 'video-preparation: cover all planned videos')
        audit.bind(ready, 'video-preparation', plan, *(v.get('preparation', {}) for v in videos.values()))
    payload = dict(policy=POLICY, run_id=run['run_id'], name=name, scope=run['scope'],
        blueprint={k: v for k, v in plan.items() if k != 'approval'}, routes=routes,
        manifest_paths=pointers, records=records, source_versions=versions)
    if previous: payload['creative_identity'] = previous.get('identity')
    identity = dict(name=name, run_id=run['run_id'], fingerprint=state.digest(payload))
    return dict(identity=identity, targets=[{'path': p, 'sha256': h} for p, h in sorted(targets.items())],
                source_versions=versions, video_ids=list(videos) if name == 'video-creative' else shots,
                issues=list(dict.fromkeys(audit.issues)))


def adopted(project, name, run=None):
    from . import calibration
    run = store.load_run(project) if run is None else run
    current = snapshot(project, name, run)
    found = None
    if not current['issues']:
        for entry in reversed(state.read_lines(state.resolve(project, '_state/decisions.jsonl'))):
            if entry.get('review_group') == current['identity']:
                found = entry
                break
    event = found.get('calibration_event') if found else None
    approved = bool(event and event.get('run_id') == run['run_id'] and found.get('decision') == 'approved'
                    and all(state.is_approved(project, r['path']) for r in current['targets'])
                    and not calibration._changed_since(project, run, event))
    return {**current, 'approved': approved, 'decision_id': found.get('decision_id') if found else None,
            'event_id': found.get('calibration_event', {}).get('event_id') if found else None}


def validate_approval(project, record, run):
    identity = record.get('review_group')
    if identity is None: return
    if not isinstance(identity, dict): raise ValueError('review_group must identify the displayed actual group')
    current = snapshot(project, identity.get('name'), run)
    # Actual new human opinions may supersede a rejection of these same members.
    # This exception writes only that opinion; it never relaxes production/review
    # checks, missing files, changed sources, or a rejected upstream blueprint.
    member_rejections = tuple(': current version was rejected: ' + r['path'] for r in current['targets'])
    issues = [issue for issue in current['issues'] if not issue.endswith(member_rejections)]
    if issues: raise ValueError('; '.join(issues))
    if identity != current['identity']: raise ValueError('review_group no longer identifies the current files and scope')
    targets = sorted(record['targets'], key=lambda r: r['path'])
    if targets != current['targets']:
        raise ValueError('A complete review_group needs the exact displayed actual targets')


def require_adopted(audit, name):
    result = adopted(audit.project, name)
    audit.need(result['approved'], name + ': one actual complete current group adoption required')
    audit.issues.extend(result['issues'])


def human_gate(project, task, run, include_review=True):
    """Display real candidates before adoption; reviewer pass itself never adopts."""
    name = task['spec']['review_group']
    current = snapshot(project, name, run)
    problems = list(current['issues'])
    if include_review and not problems:
        from . import review
        refs = list(task['spec'].get('review_packets', []))
        refs += [t['packet'] for t in run['tasks'] if t['spec']['id'] in task['spec'].get('depends_on', []) and t.get('packet')]
        covered, reviewed_sources = {}, {}
        for ref in dict.fromkeys(refs):
            try:
                saved = review.snapshot(project, ref)
                if saved['reviewer_verdict'] != 'pass':
                    problems.append('Group dispatch requires passed independent review: ' + ref)
                covered.update({r['path']: r['sha256'] for r in saved['artifacts']})
                reviewed_sources.update(saved['source_versions'])
            except (OSError, ValueError) as exc: problems.append(str(exc))
        if not all(covered.get(r['path']) == r['sha256'] for r in current['targets']):
            problems.append('Group dispatch needs independent review covering every displayed current target')
        if not all(reviewed_sources.get(p) == sha for p, sha in current['source_versions'].items()):
            problems.append('Group dispatch needs independent review of every current source, including unselected candidates')
    return {'allowed': not problems, 'issues': problems, 'review_group': current}


def image_candidate(project, purpose):
    """Only new cover/asset visual candidates may precede visual adoption.

    Mathematical/story teaching definitions keep their original adoption gates.
    The job carries this exact basis so later submission cannot borrow new scope.
    """
    from . import workflow
    run = store.load_run(project)
    if purpose not in ('cover', 'asset') or not active(project, run): return None
    audit = workflow.Inspection(project, workflow.load(project))
    plan = audit.blueprint()
    canonical = '_state/assets.json'
    versions = store.versions(project, [canonical])
    audit.issues.extend(store.issues(project, versions))
    if audit.issues: raise ValueError('; '.join(audit.issues))
    return dict(policy=POLICY, run_id=run['run_id'], scope_digest=state.digest(run['scope']),
                purpose=purpose, assets_sha256=versions[canonical],
                blueprint=state.digest({k: v for k, v in plan.items() if k != 'approval'}))


def check_image_candidate(project, job):
    saved = job.get('creative_candidate')
    if saved is None: return False
    current = image_candidate(project, job.get('purpose'))
    if current is None or current != saved or job.get('run_id') != current['run_id']:
        raise ValueError('Creative candidate run, scope or source version changed; prepare a new actual version')
    problems = store.issues(project, {r['path']: r['sha256'] for r in job.get('references', [])})
    if problems: raise ValueError('; '.join(problems))
    return True


def validate_receipt(project, run, task, result, versions):
    if not task['spec'].get('review_group'):
        if 'review_group' in result:
            raise ValueError('review_group is an actual group source link, not a result annotation')
        return
    identity = task.get('review_group', {}).get('identity')
    if result.get('review_group') != identity:
        raise ValueError('Human receipt must identify the exact displayed review_group')
    current = snapshot(project, task['spec']['review_group'], run)
    if current['identity'] != identity:
        raise ValueError('Displayed review_group has changed')
    if versions != {r['path']: r['sha256'] for r in current['targets']}:
        raise ValueError('Group receipt must cover the exact displayed actual files')
    if not result.get('decision_id') or not result.get('decision_event_id'):
        raise ValueError('Group receipt requires the actual decision_id and decision_event_id')
    matches = [entry for entry in state.read_lines(state.resolve(project, '_state/decisions.jsonl'))
               if entry.get('decision_id') == result['decision_id']
               and entry.get('calibration_event', {}).get('event_id') == result['decision_event_id']]
    if len(matches) != 1 or matches[0].get('review_group') != identity:
        raise ValueError('Group receipt decision is not the actual same-group occurrence')
    if result['status'] == 'completed' and not adopted(project, task['spec']['review_group'], run)['approved']:
        raise ValueError('Only actual complete current group adoption completes this human task')


def final_versions(audit):
    """Files a real H23 inspection must cover; no future report is an input."""
    versions = {}
    for name in ('pages', 'editable', 'documents'):
        for item in audit.data.get('stages', {}).get(name, {}).get('files', {}).values():
            if item.get('path'): versions[item['path']] = item.get('sha256')
    delivery = audit.data.get('stages', {}).get('delivery', {}).get('files', {})
    metadata = {delivery[role]['path'] for role in ('wps', 'manifest') if delivery.get(role, {}).get('path')}
    for role, item in delivery.items():
        if role not in ('wps', 'manifest') and item.get('path') not in metadata:
            if audit.file(item, 'H23/delivery/' + role):
                versions[item['path']] = item['sha256']
    for vid in audit.data.get('stages', {}).get('blueprint', {}).get('video_ids', []):
        _, video = audit.video(vid)
        item = video.get('final', {}).get('files', {}).get('media', {})
        if item.get('path'): versions[item['path']] = item.get('sha256')
    return versions


def final_dispatch(project):
    """Prepare H23's actual inspection task, without claiming the inspection passed."""
    from . import workflow
    audit = workflow.Inspection(project, workflow.load(project))
    audit.issues.extend(workflow.check(project, 'documents')['issues'])
    editable = audit.stage('editable')
    audit.file(editable.get('files', {}).get('limitations'), 'editable/limitations')
    audit.stage('documents')
    for vid in audit.data.get('stages', {}).get('blueprint', {}).get('video_ids', []):
        _, video = audit.video(vid)
        final = video.get('final', {})
        audit.evidence(final, vid + '/actual-video', roles=('media',), approved=True)
        audit.video_container(final.get('files', {}).get('media'), vid + '/actual-video')
    versions = final_versions(audit)
    return dict(allowed=not audit.issues, issues=list(dict.fromkeys(audit.issues)),
                final_checklist=list(FINAL_CHECKS), inspection_versions=versions)


def final_inspection(audit, reference):
    report = audit.json_file(reference, 'H23/final-inspection')
    checks = report.get('checks', {})
    for key in FINAL_CHECKS:
        audit.need(isinstance(checks, dict) and checks.get(key) is True,
                   'H23: actual same-version inspection missing ' + key)
    versions = report.get('source_versions', {})
    audit.need(all(versions.get(path) == sha for path, sha in final_versions(audit).items()),
               'H23: actual inspection must cover every current page/deck/video/supporting document/delivery artifact')
