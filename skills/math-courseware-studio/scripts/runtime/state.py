"""Project records, approvals and narrowly scoped change propagation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid

SCHEMA = '1.0'
RECORDS = {'materials': 'materials', 'story': 'events', 'math': 'problems',
           'assets': 'assets', 'pages': 'pages'}
ROUTES = ('builtin', 'openai_image_api')


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace one record atomically; version preservation is handled by record_change.
    pending = path.with_name(path.name + '.pending-' + uuid.uuid4().hex)
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    pending.replace(path)


def read_lines(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip()] if path.exists() else []


def append_line(path, value):
    with Path(path).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')


def resolve(project, relative):
    root = Path(project).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Path must name a file or directory inside the project')
    return path


def load_project(project):
    data = read_json(resolve(project, '_state/project.json'))
    if data.get('schema_version') != SCHEMA:
        raise ValueError('Unsupported project schema')
    return data


def init_project(project, title, route=None):
    root = Path(project).resolve()
    if route is not None and route not in ROUTES:
        raise ValueError('Unknown image route')
    existing = root / '_state/project.json'
    if existing.exists():
        return load_project(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError('Nonempty directory is not an initialized courseware project')
    if not title.strip():
        raise ValueError('Project title required')
    root.mkdir(parents=True, exist_ok=True)
    (root / 'AGENTS.md').write_text(
        '# Courseware Project Rules\n\n'
        'inputs/: original source copies; never rewrite. planning/: human-readable plans.\n'
        'assets/: characters/scenes/props and approved versions. slides/: prompts and page images.\n'
        'editable/: handoff, returned originals, output copies. documents/: three teaching texts.\n'
        '_state/: canonical records, approvals, versions, jobs and QA. deliveries/: versioned copies.\n'
        'Stable IDs persist across reordering. Record authorized changes and preserve prior versions.\n'
        'Do not delete outputs or put secrets into project files. User scope and approvals take precedence.\n'
        'Read HANDOFF.md before resuming; validate records before downstream execution.\n', encoding='utf-8')
    (root / 'HANDOFF.md').write_text('# Courseware Handoff\n\nInitialized; awaiting source analysis.\n', encoding='utf-8')
    for name in ['inputs', 'planning', 'assets/characters', 'assets/scenes', 'assets/props',
                 'slides/prompts', 'editable/handoff', 'editable/returned', 'editable/output',
                 'documents/classroom-script', 'documents/lesson-presentation', 'documents/lesson-plan',
                 '_state/versions', '_state/jobs', '_state/editable', '_state/documents',
                 '_state/qa', 'deliveries']:
        (root / name).mkdir(parents=True, exist_ok=True)
    data = {'schema_version': SCHEMA, 'project_id': root.name, 'title': title,
            'revision': 'v001', 'created_at': now(), 'image_route': route,
            'font': 'KaiTi', 'artifacts': {}, 'stale_targets': [],
            'branches': {name: 'draft' for name in ['analysis', 'story', 'pages', 'editable', 'documents']}}
    write_json(existing, data)
    for name, array in RECORDS.items():
        write_json(root / '_state' / (name + '.json'),
                   {'schema_version': SCHEMA, 'project_id': root.name, 'revision': 'v001', array: []})
    for name in ['decisions', 'changes']:
        (root / '_state' / (name + '.jsonl')).touch()
    return data


def is_approved(project, relative):
    path = resolve(project, relative)
    if not path.is_file():
        return False
    current = sha256(path)
    for record in reversed(read_lines(resolve(project, '_state/decisions.jsonl'))):
        for target in record.get('targets', []):
            if target['path'] == relative and target['sha256'] == current:
                return record['decision'] == 'approved'
    return False


def require_approved(project, *paths):
    missing = [path for path in paths if not is_approved(project, path)]
    if missing:
        raise ValueError('Current version requires recorded user confirmation: ' + ', '.join(missing))


def record_approval(project, record):
    load_project(project)
    if not str(record.get('user_evidence', '')).strip() or not record.get('targets'):
        raise ValueError('Approval needs nonempty targets and actual user evidence')
    decision = record.get('decision', 'approved')
    if decision not in ('approved', 'rejected'):
        raise ValueError('Invalid decision')
    for item in record['targets']:
        if sha256(resolve(project, item['path'])) != item['sha256']:
            raise ValueError('Approval target has changed: ' + item['path'])
    entry = {**record, 'decision': decision}
    entry['decision_id'] = digest(entry)
    log = resolve(project, '_state/decisions.jsonl')
    history = read_lines(log)
    previous = history[-1] if history else None
    if previous and previous.get('decision_id') == entry['decision_id']:
        return previous
    entry['recorded_at'] = now()
    append_line(log, entry)
    if decision == 'approved':
        data = load_project(project)
        refreshed = {x['path'] for x in entry['targets']}
        for target in entry['targets']:
            if target['path'] in {f'_state/{name}.json' for name in RECORDS}:
                refreshed.update(entry_ids(read_json(resolve(project, target['path']))))
        data['stale_targets'] = [x for x in data.get('stale_targets', []) if x not in refreshed]
        write_json(resolve(project, '_state/project.json'), data)
    return entry


def entry_ids(value):
    # Only entities, not nested reference fields such as a text unit's math_id.
    return {item[key]: item for array, key in
            [('problems', 'math_id'), ('assets', 'asset_id'), ('pages', 'page_id'),
             ('events', 'event_id'), ('video_nodes', 'video_id')]
            for item in value.get(array, []) if isinstance(item.get(key), str)}


def impact(project, change):
    relative = change['path']
    before = read_json(resolve(project, relative))
    replacement = change['replacement']
    old, new = entry_ids(before), entry_ids(replacement)
    def content(item):
        if isinstance(item, dict) and 'page_id' in item:
            return {key: value for key, value in item.items() if key != 'order'}
        return item
    changed = {key for key in old.keys() | new.keys() if content(old.get(key)) != content(new.get(key))}
    # File-level dependency applies even for metadata-only changes (e.g. visual style).
    affected = changed | {relative}
    pages = read_json(resolve(project, '_state/pages.json')).get('pages', [])
    if relative == '_state/story.json' and before.get('visual_style') != replacement.get('visual_style'):
        affected.update(p['page_id'] for p in pages)
    record = load_project(project)
    while True:
        previous = set(affected)
        for page in pages:
            refs = set(page.get('math_ids', [])) | {x['asset_id'] for x in page.get('asset_refs', [])}
            refs |= set(page.get('video_ids', [])) | set(page.get('story_ids', []))
            if refs & affected:
                affected.add(page['page_id'])
        for key, artifact in record.get('artifacts', {}).items():
            if set(artifact.get('dependencies', [])) & affected:
                affected.add(key)
        if previous == affected:
            break
    return {'changed_ids': sorted(changed), 'affected_ids': sorted(affected),
            'order_changed': relative == '_state/pages.json' and
            [(p.get('page_id'), p.get('order')) for p in before.get('pages', [])] !=
            [(p.get('page_id'), p.get('order')) for p in replacement.get('pages', [])]}


def record_change(project, change):
    relative = change['path']
    if not re.fullmatch(r'_state/(project|materials|story|math|assets|pages)\.json', relative):
        raise ValueError('record-change only updates canonical records')
    path = resolve(project, relative)
    if sha256(path) != change.get('expected_sha256'):
        raise ValueError('Change is based on an outdated source')
    if not change.get('reason', '').strip() or not change.get('user_evidence', '').strip():
        raise ValueError('Change reason and authorization evidence required')
    replacement = change.get('replacement')
    if not isinstance(replacement, dict):
        raise ValueError('Replacement must be a JSON object')
    report = impact(project, change)
    old = read_json(path)
    version = int(str(old.get('revision', 'v000')).lstrip('v')) + 1
    replacement = {**replacement, 'schema_version': SCHEMA,
                   'project_id': old['project_id'] if 'project_id' in old else Path(project).name,
                   'revision': f'v{version:03d}'}
    if relative == '_state/project.json' and replacement.get('image_route') not in (*ROUTES, None):
        raise ValueError('Unknown image route')
    archive = f'_state/versions/{path.stem}-{old.get("revision", "v000")}-{sha256(path)[:16]}.json'
    saved = resolve(project, archive)
    if not saved.exists():
        shutil.copy2(path, saved)
    write_json(path, replacement)
    project_data = load_project(project)
    project_data['stale_targets'] = sorted(set(project_data.get('stale_targets', [])) |
                                          set(report['affected_ids']))
    write_json(resolve(project, '_state/project.json'), project_data)
    result = {**report, 'path': relative, 'previous_version': archive,
              'new_sha256': sha256(path), 'reason': change['reason'],
              'user_evidence': change['user_evidence'], 'recorded_at': now()}
    append_line(resolve(project, '_state/changes.jsonl'), result)
    return result


def register_artifact(project, artifact_id, path, dependencies=(), metadata=None):
    resolved = resolve(project, path)
    data = load_project(project)
    data['artifacts'][artifact_id] = {'path': path, 'sha256': sha256(resolved),
                                    'dependencies': list(dependencies), **(metadata or {})}
    data['stale_targets'] = [x for x in data.get('stale_targets', []) if x != artifact_id]
    write_json(resolve(project, '_state/project.json'), data)
    return data['artifacts'][artifact_id]


def status(project):
    data = load_project(project)
    data['approvals'] = {name: is_approved(project, '_state/' + name + '.json') for name in RECORDS}
    data['jobs'] = [{'path': str(path.relative_to(Path(project))),
                     'status': read_json(path).get('status')} for path in
                    sorted(resolve(project, '_state/jobs').glob('*/job.json'))]
    return data
