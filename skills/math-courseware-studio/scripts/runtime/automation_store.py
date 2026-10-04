"""Small shared store for opt-in queues/reviews; never writes course adoption."""
from contextlib import contextmanager
import os
from pathlib import Path
import uuid

from . import state, workflow

AREA = '_state/automation'


def directory(project, relative):
    if not (Path(project) / 'AGENTS.md').is_file():
        raise ValueError('Read/create the project AGENTS.md before automation')
    path = state.resolve(project, relative)
    path.mkdir(parents=True, exist_ok=True)
    rules = path / 'AGENTS.md'
    if not rules.exists():
        rules.write_text('# Queue and independent review records\n\n'
                         'runs/: versioned run directories, mutable run.json and retained revisions.\n'
                         'reviews/: immutable packet.json and result.json per review.\n'
                         'active.json selects the current queue. write.lock is retained.\n'
                         'Keep all evidence; never put secrets here or edit course adoption records.\n',
                         encoding='utf-8')
    return path


@contextmanager
def locked(project):
    path = directory(project, AREA) / 'write.lock'
    with path.open('a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('Another automation command is writing; retry after it finishes') from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def identifier(prefix):
    return prefix + '-' + uuid.uuid4().hex


def relative(project, value):
    if not isinstance(value, str) or not value.strip() or Path(value).is_absolute():
        raise ValueError('Use a nonempty project-relative path')
    path = state.resolve(project, value)
    result = state.relative_path(project, path)
    if result.startswith(AREA + '/') or result == AREA:
        raise ValueError('Course inputs/outputs cannot refer to automation management files')
    return result


def versions(project, paths):
    result = {}
    for name in paths:
        name = relative(project, name)
        path = state.resolve(project, name)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Missing or empty artifact: ' + name)
        result[name] = state.sha256(path)
    return result


def issues(project, expected):
    found = []
    history = state.read_lines(state.resolve(project, '_state/decisions.jsonl'))
    for name, sha in expected.items():
        try:
            if versions(project, [name]).get(name) != sha:
                found.append('Changed artifact: ' + name)
        except (OSError, ValueError):
            found.append('Missing artifact: ' + name)
        latest = next((item for item in reversed(history) if any(
            target.get('path') == name and target.get('sha256') == sha
            for target in item.get('targets', []))), None)
        if latest and latest.get('decision') != 'approved':
            found.append('Latest user decision rejects: ' + name)
    return found


def bindings(project, paths):
    """Remember only existing references to these files, not the whole mutable index."""
    data = workflow.load(project)
    documents = {'workflow': data}
    for vid, ref in data.get('videos', {}).items():
        try:
            documents['video:' + vid] = state.read_json(state.resolve(project, ref['path']))
        except (OSError, ValueError, KeyError):
            continue
    result = []
    def walk(value, document, keys):
        if isinstance(value, dict):
            if value.get('path') in paths and value.get('sha256'):
                result.append({'document': document, 'keys': keys,
                               'value': {'path': value['path'], 'sha256': value['sha256']}})
            for key, child in value.items(): walk(child, document, keys + [key])
        elif isinstance(value, list):
            for index, child in enumerate(value): walk(child, document, keys + [index])
    for name, value in documents.items(): walk(value, name, [])
    return result


def binding_issues(project, saved):
    current = {(item['document'], tuple(item['keys'])): item['value']
               for item in bindings(project, {item['value']['path'] for item in saved})}
    return ['Current source selection changed: ' + item['value']['path'] for item in saved
            if current.get((item['document'], tuple(item['keys']))) != item['value']]


def immutable(path, value):
    if path.exists():
        if state.read_json(path) != value:
            raise ValueError('Immutable evidence already exists: ' + str(path))
    else:
        state.write_json(path, value)


def scope(project):
    data = workflow.load(project)
    return {key: data.get(key) for key in ('project_mode', 'scope_evidence', 'current_task')}
