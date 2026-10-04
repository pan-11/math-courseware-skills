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
LAYOUTS = ('legacy', 'four-folders')
FOLDERS = ('01_source', '02_work', '03_final', '04_notes')


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


def storage_layout(project):
    root = Path(project).resolve()
    legacy = (root / '_state/project.json').is_file()
    current = (root / '02_work/_state/project.json').is_file()
    if legacy and current:
        raise ValueError('Two initialized layouts in one course; select the intended root without moving files')
    return 'four-folders' if current else 'legacy'


def _four_folder_path(relative):
    path = Path(relative)
    if not path.parts or '..' in path.parts:
        raise ValueError('Use a path inside the four course folders')
    if path.parts[0] in FOLDERS or path.as_posix() in ('AGENTS.md', 'HANDOFF.md'):
        return path
    if path.parts[0] == 'inputs':
        return Path('01_source', *path.parts[1:])
    return Path('02_work') / path


def resolve(project, relative):
    root = Path(project).resolve()
    if storage_layout(root) == 'four-folders' and not Path(relative).is_absolute():
        relative = _four_folder_path(relative)
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Path must name a file or directory inside the project')
    return path


def relative_path(project, value):
    """Stable record path for a physical file or logical path, in either layout."""
    root = Path(project).resolve()
    actual = resolve(root, value)
    path = actual.relative_to(root)
    if storage_layout(root) == 'four-folders':
        if path.parts[0] == '01_source':
            path = Path('inputs', *path.parts[1:])
        elif path.parts[0] == '02_work' and len(path.parts) > 1:
            path = Path(*path.parts[1:])
        elif path.parts[0] not in FOLDERS and path.as_posix() not in ('AGENTS.md', 'HANDOFF.md'):
            raise ValueError('Import original files into 01_source before registering their paths')
        if resolve(root, path) != actual:
            # A work-area AGENTS.md is distinct from the root rules, for example.
            path = actual.relative_to(root)
    return path.as_posix()


def load_project(project):
    data = read_json(resolve(project, '_state/project.json'))
    if data.get('schema_version') != SCHEMA:
        raise ValueError('Unsupported project schema')
    return data


def init_project(project, title, route=None, mode=None, scope_evidence='', layout='legacy'):
    root = Path(project).resolve()
    if route is not None and route not in ROUTES:
        raise ValueError('Unknown image route')
    if mode not in (None, 'full_course', 'selected_modules'):
        raise ValueError('Unknown workflow mode')
    if mode is not None and not str(scope_evidence).strip():
        raise ValueError('Explicit workflow mode requires scope evidence')
    if layout not in LAYOUTS:
        raise ValueError('Unknown storage layout')
    current_layout = storage_layout(root)
    existing = root / ('02_work/_state/project.json' if current_layout == 'four-folders' else '_state/project.json')
    if existing.exists():
        return load_project(root)
    if root.is_file():
        raise ValueError('Project must be the course folder, not an input file')
    if layout == 'legacy' and root.exists() and any(root.iterdir()):
        raise ValueError('Nonempty directory is not an initialized courseware project')
    if layout == 'four-folders':
        for name in ('inputs', 'planning', 'assets', 'slides', 'editable', 'documents', '_state', 'deliveries', 'videos'):
            if (root / name).is_dir():
                raise ValueError('Existing production directory requires inspection; no automatic migration: ' + name)
        for name in FOLDERS:
            if (root / name).exists() and not (root / name).is_dir():
                raise ValueError('Course folder name is already a file: ' + name)
        work = root / '02_work'
        if work.exists() and any(work.iterdir()):
            raise ValueError('Existing 02_work is not an initialized course; inspect it before resuming')
        existing = root / '02_work/_state/project.json'
    if not title.strip():
        raise ValueError('Project title required')
    root.mkdir(parents=True, exist_ok=True)
    rules = (
        '# Courseware Project Rules\n\n'
        'inputs/: original source copies; never rewrite. planning/: human-readable plans.\n'
        'assets/: characters/scenes/props and approved versions. slides/: prompts and page images.\n'
        'editable/: handoff, returned originals, output copies. documents/: three teaching texts.\n'
        '_state/: canonical records, approvals, versions, jobs and QA. deliveries/: versioned copies.\n'
        'Stable IDs persist across reordering. Record authorized changes and preserve prior versions.\n'
        'Do not delete outputs or put secrets into project files. User scope and approvals take precedence.\n'
        'Read HANDOFF.md before resuming; validate records before downstream execution.\n')
    if layout == 'four-folders':
        rules = ('# Four-folder Courseware Rules\n\n'
                 'This user-supplied folder is the course root; keep AGENTS.md and HANDOFF.md here.\n'
                 '01_source/: byte-identical original copies. Never rewrite or relocate originals.\n'
                 '02_work/: planning, assets, videos, slides, editable returns, documents, interactive, notes, readable and _state.\n'
                 '02_work/_state/: canonical records, versions, jobs, approvals, queues and QA. Retain all evidence.\n'
                 '02_work/deliveries/: collect staging including prompts/reference media; not a final product.\n'
                 '03_final/vNNN/: explicitly checked teaching products and their playback dependencies.\n'
                 '04_notes/vNNN/note-NN/: per-post image/copy/editing kits or actually completed media.\n'
                 '03_final/README.md and 04_notes/README.md identify current versions and real verification status.\n'
                 'Runtime record paths remain logical: inputs -> 01_source; other work paths -> 02_work.\n'
                 'Use state.resolve for disk paths and state.relative_path for record paths; explicit 03_final/04_notes stay unchanged.\n'
                 'Declare new subdirectory uses before creation. Keep old versions; never auto-delete or auto-adopt.\n'
                 'Read HANDOFF.md before resuming; preserve actual scope and approvals.\n')
    rules_path = root / 'AGENTS.md'
    if rules_path.exists():
        with rules_path.open('a', encoding='utf-8') as stream:
            stream.write('\n' + rules)
    else:
        rules_path.write_text(rules, encoding='utf-8')
    if not (root / 'HANDOFF.md').exists():
        (root / 'HANDOFF.md').write_text('# Courseware Handoff\n\nInitialized; awaiting source analysis.\n', encoding='utf-8')
    if layout == 'four-folders':
        for name in FOLDERS:
            (root / name).mkdir(exist_ok=True)
    for name in ['inputs', 'planning', 'assets/characters', 'assets/scenes', 'assets/props',
                 'slides/prompts', 'editable/handoff', 'editable/returned', 'editable/output',
                 'documents/classroom-script', 'documents/lesson-presentation', 'documents/lesson-plan',
                 '_state/versions', '_state/jobs', '_state/editable', '_state/documents',
                 '_state/qa', 'deliveries']:
        (root / (_four_folder_path(name) if layout == 'four-folders' else name)).mkdir(parents=True, exist_ok=True)
    data = {'schema_version': SCHEMA, 'project_id': root.name, 'title': title,
            'revision': 'v001', 'created_at': now(), 'image_route': route,
            'font': 'KaiTi', 'artifacts': {}, 'stale_targets': [],
            'branches': {name: 'draft' for name in ['analysis', 'story', 'pages', 'editable', 'documents']}}
    if layout == 'four-folders':
        data['storage_layout'] = layout
    write_json(existing, data)
    for name, array in RECORDS.items():
        write_json(resolve(root, '_state/' + name + '.json'),
                   {'schema_version': SCHEMA, 'project_id': root.name, 'revision': 'v001', array: []})
    for name in ['decisions', 'changes']:
        resolve(root, '_state/' + name + '.jsonl').touch()
    from . import workflow
    workflow.initialize(root, mode=mode, evidence=scope_evidence)
    return data


def is_approved(project, relative):
    if storage_layout(project) == 'four-folders':
        relative = relative_path(project, relative)
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
    from . import automation_store as store, calibration
    if not store.load_run(project):
        return _record_approval(project, record)
    with store.locked(project):
        data = store.load_run(project)
        calibration.validate_metadata(record)
        return _record_approval(project, record, data)


def _record_approval(project, record, calibration_run=None):
    load_project(project)
    if not str(record.get('user_evidence', '')).strip() or not record.get('targets'):
        raise ValueError('Approval needs nonempty targets and actual user evidence')
    decision = record.get('decision', 'approved')
    if decision not in ('approved', 'rejected'):
        raise ValueError('Invalid decision')
    if storage_layout(project) == 'four-folders':
        record = {**record, 'targets': [{**item, 'path': relative_path(project, item['path'])}
                                       for item in record['targets']]}
    for item in record['targets']:
        if sha256(resolve(project, item['path'])) != item['sha256']:
            raise ValueError('Approval target has changed: ' + item['path'])
    entry = {**record, 'decision': decision}
    entry['decision_id'] = digest(entry)
    log = resolve(project, '_state/decisions.jsonl')
    history = read_lines(log)
    previous = history[-1] if history else None
    linked = None
    if calibration_run:
        from . import calibration
        if record.get('human_event_id'):
            linked = calibration.approval_link(project, calibration_run, record,
                {t['path']: t['sha256'] for t in entry['targets']}, decision)
        previous = calibration.approval_replay(project, calibration_run, entry, history)
        if linked and previous and previous.get('calibration_event', {}).get('event_id') != linked['event_id']:
            previous = None
    if previous and (calibration_run or previous.get('decision_id') == entry['decision_id']):
        if calibration_run:
            from . import calibration
            calibration.recover(project, calibration_run)
        return previous
    entry['recorded_at'] = now()
    if calibration_run:
        from . import calibration
        task = next((t for t in calibration_run['tasks'] if t['spec']['id'] == record.get('task_id')), None)
        versions = {t['path']: t['sha256'] for t in entry['targets']}
        entry['calibration_event'] = (linked if linked else calibration.freeze(project, calibration_run, 'approval',
                [len(history), entry['decision_id']], versions, decision, entry['user_evidence'], record,
                task, entry['decision_id']))
        if not record.get('human_event_id'):
            entry['recorded_at'] = entry['calibration_event']['recorded_at']
    append_line(log, entry)
    if decision == 'approved':
        data = load_project(project)
        refreshed = {x['path'] for x in entry['targets']}
        for target in entry['targets']:
            if target['path'] in {f'_state/{name}.json' for name in RECORDS}:
                refreshed.update(entry_ids(read_json(resolve(project, target['path']))))
        data['stale_targets'] = [x for x in data.get('stale_targets', []) if x not in refreshed]
        write_json(resolve(project, '_state/project.json'), data)
    if calibration_run:
        calibration.recover(project, calibration_run)
    return entry


def entry_ids(value):
    # Only entities, not nested reference fields such as a text unit's math_id.
    return {item[key]: item for array, key in
            [('problems', 'math_id'), ('assets', 'asset_id'), ('pages', 'page_id'),
             ('events', 'event_id'), ('video_nodes', 'video_id')]
            for item in value.get(array, []) if isinstance(item.get(key), str)}


def impact(project, change):
    relative = relative_path(project, change['path']) if storage_layout(project) == 'four-folders' else change['path']
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
    relative = relative_path(project, change['path']) if storage_layout(project) == 'four-folders' else change['path']
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
    if storage_layout(project) == 'four-folders':
        path = relative_path(project, path)
        dependencies = [relative_path(project, value) for value in dependencies]
    resolved = resolve(project, path)
    data = load_project(project)
    data['artifacts'][artifact_id] = {'path': path, 'sha256': sha256(resolved),
                                    'dependencies': list(dependencies), **(metadata or {})}
    data['stale_targets'] = [x for x in data.get('stale_targets', []) if x != artifact_id]
    write_json(resolve(project, '_state/project.json'), data)
    return data['artifacts'][artifact_id]


def status(project):
    data = load_project(project)
    from . import workflow
    data['workflow'] = workflow.summary(project)
    data['approvals'] = {name: is_approved(project, '_state/' + name + '.json') for name in RECORDS}
    data['jobs'] = [{'path': relative_path(project, path) if storage_layout(project) == 'four-folders' else str(path.relative_to(Path(project))),
                     'status': read_json(path).get('status')} for path in
                    sorted(resolve(project, '_state/jobs').glob('*/job.json'))]
    return data
