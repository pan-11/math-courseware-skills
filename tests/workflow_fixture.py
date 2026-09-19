"""Real files for synthetic workflow tests; never user approval or lesson acceptance."""
from pathlib import Path
from runtime import state


def ref(root, path):
    return {'path': path, 'sha256': state.sha256(Path(root) / path)}


def versions(*records):
    return {item['path']: item['sha256'] for record in records
            for item in record.get('files', {}).values()}


def evidence(root, name, files=None, approved=False, sources=None, **extra):
    root = Path(root)
    base = '_state/qa/workflow-' + name
    if files is None:
        path = base + '.md'
        (root / path).write_text('Synthetic ' + name + ' content; not real courseware.\n', encoding='utf-8')
        files = {'report': ref(root, path)}
    sources = sources or {}
    versions = {**sources, **{item['path']: item['sha256'] for item in files.values()}}
    state.write_json(root / (base + '-review.json'), {'passed': True, 'source_versions': versions,
                                                    'notes': 'Synthetic inspection only'})
    record = {'files': files, 'source_versions': sources,
              'review': ref(root, base + '-review.json'), **extra}
    if approved:
        state.write_json(root / (base + '-approval.json'), {
            'decision': 'approved', 'user_evidence': 'Synthetic approval, not a real user decision',
            'targets': list(files.values())})
        record['approval'] = ref(root, base + '-approval.json')
    return record


def enable_modules(root, modules=None, deck=None, route='A'):
    """Declare the isolated fixture request, keeping its scope separate from course content."""
    root = Path(root)
    modules = modules or ['pages', 'plan', 'editable', 'documents']
    path = '_state/qa/synthetic-module-request.md'
    (root / path).write_text('Synthetic request for these modules: ' + ', '.join(modules), encoding='utf-8')
    files = {'source': ref(root, path)}
    inputs = {m: evidence(root, 'input-' + m, files=files) for m in modules}
    if 'editable' in modules:
        edit_files = dict(files)
        pages_path = root / '_state/pages.json'
        if pages_path.exists():
            edit_files['text'] = ref(root, '_state/pages.json')
        if deck:
            edit_files['deck'] = ref(root, str(deck).replace('\\', '/'))
        inputs['editable'] = evidence(root, 'input-editable', files=edit_files)
    record = {'schema_version': '1.0', 'project_mode': 'selected_modules',
              'scope_evidence': 'Synthetic isolated module test',
              'current_task': {'mode': 'selected_modules', 'modules': modules,
                               'evidence': 'Synthetic request, not production authorization'},
              'inputs': inputs, 'stages': {}, 'videos': {},
              'route_choice': {'route': route, 'user_evidence': 'Synthetic explicit route ' + route}}
    state.write_json(root / '_state/workflow.json', record)
    return record
