"""Current complete text adoption before new story-dependent images, including old runs.

This reads existing evidence only. It neither adopts text nor changes historical group identities.
"""
from copy import deepcopy
from pathlib import Path

from . import state


def inspect(project, video_id=None, approved=True):
    from . import workflow
    project = Path(project)
    data = workflow.load(project)
    audit = workflow.Inspection(project, data)
    full = data.get('current_task', {}).get('mode') == 'full_course'
    plan = audit.blueprint() if full else {}
    ids = plan.get('video_ids', []) if full else ([video_id] if video_id else list(data.get('videos', {})))
    if not ids and not full:
        path = project / 'manifest.json'
        if path.is_file(): ids = [state.read_json(path).get('video_id')]
    audit.need(bool(ids) and all(isinstance(vid, str) and vid for vid in ids),
               'video-story: actual complete video inventory required')
    targets, sources, records, routes, pointers, approvals = {}, {}, {}, {}, {}, []
    canonical_files = {state.resolve(project, '_state/' + name + '.json')
                       for name in ('story', 'math', 'pages', 'assets')}
    history = state.read_lines(state.resolve(project, '_state/decisions.jsonl'))
    for vid in ids:
        route, video = audit.video(vid)
        routes[vid] = route
        pointers[vid] = data.get('videos', {}).get(vid, {}).get('path', 'manifest.json')
        products = video.get('products', {})
        for name, field in (('script', 'complete'), ('voice', 'verbatim')):
            record = products.get(name, {})
            label = str(vid) + '/' + name
            files = audit.evidence(record, label, approved=approved)
            audit.need(record.get(field) is True, label + ': complete story text requires ' + field)
            if name == 'voice': audit.bind(record, label, products.get('script', {}))
            elif full: audit.bind(record, label, plan)
            records[label] = {key: deepcopy(value) for key, value in record.items() if key != 'approval'}
            for item in files.values():
                if isinstance(item, dict) and item.get('path') and item.get('sha256'):
                    try:
                        actual = state.resolve(project, item['path'])
                    except (OSError, TypeError, ValueError):
                        continue  # evidence() already reports invalid file references.
                    audit.need(actual not in canonical_files,
                               label + ': canonical core records cannot replace complete story text files')
                    targets[item['path']] = item['sha256']
                    sources[item['path']] = item['sha256']
                    latest = next((entry for entry in reversed(history) if item in entry.get('targets', [])), None)
                    if latest:
                        approvals.append({'decision_id': latest.get('decision_id'), 'target': item,
                                          'record_digest': state.digest(latest)})
            sources.update(record.get('source_versions', {}))
            if record.get('review', {}).get('path'):
                sources[record['review']['path']] = record['review']['sha256']
            if record.get('approval'):
                approvals.append({'approval': record['approval']})
    return dict(issues=list(dict.fromkeys(audit.issues)),
                targets=[{'path': path, 'sha256': sha} for path, sha in sorted(targets.items())],
                source_versions=sources, records=records, routes=routes, manifest_paths=pointers,
                video_ids=ids, blueprint={key: value for key, value in plan.items() if key != 'approval'},
                approval_sources=approvals)


def image_check(project, purpose):
    if purpose not in ('cover', 'asset'): return {'issues': [], 'basis': None}
    from . import workflow
    data = workflow.load(project)
    task = data.get('current_task', {})
    modules = {name.removeprefix('math-courseware-') for name in task.get('modules', [])}
    if task.get('mode') != 'full_course' and not any(name == 'video' or name.startswith('video-') for name in modules):
        return {'issues': [], 'basis': None}
    current = inspect(project)
    payload = {key: value for key, value in current.items() if key not in ('issues', 'approval_sources')}
    return {'issues': current['issues'], 'basis': state.digest(payload)}


def image_issues(project, purpose):
    return image_check(project, purpose)['issues']


def require_image(project, purpose):
    current = image_check(project, purpose)
    if current['issues']: raise ValueError('Complete video-story adoption required: ' + '; '.join(current['issues']))
    return current['basis']


def check_job(project, job):
    current = require_image(project, job['purpose'])
    if current != job.get('story_basis'):
        raise ValueError('Complete video-story basis changed or was not recorded for this pending job; '
                         'preserve it and prepare a new version')
