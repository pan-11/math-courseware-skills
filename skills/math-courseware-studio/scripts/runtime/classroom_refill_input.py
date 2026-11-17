"""Import a provided refill as an immutable trial input, not a reviewed base."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

from . import classroom_animation as animation, state

ACTIVATION = '课堂动画试用V1'
ARTIFACT = 'editable-classroom-trial-input'
VERSION = 'classroom_refill_input_v1'


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _bound(project, reference):
    animation._fields(reference, {'path', 'sha256'}, set(), 'refill input reference')
    path = animation._file(project, reference['path'])
    _need(state.sha256(path) == reference['sha256'], 'Refill input bound file changed: ' + reference['path'])
    return path


def _paths(project, plan):
    animation._fields(plan, {'source_deck', 'source_sha256', 'source_versions', 'output',
                             'request', 'mapping'}, set(), 'refill input plan')
    animation._sources(project, plan)
    animation._instruction(project, plan)
    source = animation._file(project, plan['source_deck'])
    output = animation._path(project, plan['output'])
    plan_path = output.with_suffix('.refill-input.plan.json')
    manifest = output.with_suffix('.refill-input.json')
    protected = {output, plan_path, manifest}
    _need(source.suffix.lower() == '.pptx' and output.suffix.lower() == '.pptx',
          'Provided refill and its copied output must be PPTX files')
    _need(all(animation._file(project, path) not in protected for path in plan['source_versions']),
          'Refill input output and sidecars cannot overwrite a bound source')
    return source, output, plan_path, manifest


def _inventory(source, mapping):
    inventory = animation.inspect(source)
    slides = inventory['slides']
    animation.editor._mapping(mapping, len(slides))
    _need(set(mapping.values()) == set(range(1, len(slides) + 1)),
          'Refill input mapping must cover every actual slide exactly once')
    return {'inspection_sha256': animation.editor._digest(inventory),
            'slides': [{'slide_index': p['slide_index'], 'part': p['part'],
                        'shape_ids': [o['shape_id'] for o in p['objects']],
                        'object_count': len(p['objects']), 'timing_sha256': p['timing_sha256']}
                       for p in slides],
            'media': inventory['media']}


def _receipt(project, plan, output, plan_path, inventory):
    return {'schema_version': VERSION, 'role': 'provided_refill',
            'path': state.relative_path(project, output), 'sha256': plan['source_sha256'],
            'source_deck': plan['source_deck'], 'source_sha256': plan['source_sha256'],
            'source_versions': plan['source_versions'], 'mapping': plan['mapping'],
            'plan_ref': {'path': state.relative_path(project, plan_path), 'sha256': state.sha256(plan_path)},
            'inventory': inventory, 'content_review': 'unverified', 'playback': 'unverified'}


def _metadata(receipt):
    return {'refill_input_manifest': receipt['manifest_ref'], 'input_role': 'provided_refill', 'intermediate': True,
            'source_versions': receipt['source_versions'],
            'content_review': 'unverified', 'playback': 'unverified'}


def _write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def _validate(project, manifest_ref):
    manifest = _bound(project, manifest_ref)
    saved = state.read_json(manifest)
    _need(saved.get('schema_version') == VERSION, 'Unknown provided-refill receipt')
    plan_path = _bound(project, saved['plan_ref'])
    plan = state.read_json(plan_path)
    source, output, expected_plan, expected_manifest = _paths(project, plan)
    _need(plan_path == expected_plan and manifest == expected_manifest,
          'Refill input plan and manifest must stay beside their immutable copy')
    _need(output.is_file() and state.sha256(output) == plan['source_sha256'],
          'Refill input copy changed or missing')
    inventory = _inventory(source, plan['mapping'])
    expected = _receipt(project, plan, output, plan_path, inventory)
    _need(saved == expected, 'Refill input receipt differs from actual source, copy or inventory')
    animation._sources(project, plan)
    _bound(project, saved['plan_ref'])
    _bound(project, manifest_ref)
    _need(state.sha256(output) == expected['sha256'], 'Refill input copy changed during verification')
    return {**expected, 'manifest_ref': deepcopy(manifest_ref)}


def import_refill(project, plan, activation):
    """Copy and inventory a supplied refill; never mark content/playback approved."""
    _need(activation == ACTIVATION, 'Explicit activation must be exactly ' + ACTIVATION)
    project = Path(project).resolve()
    plan = deepcopy(plan)
    source, output, plan_path, manifest = _paths(project, plan)
    from . import classroom_trial
    classroom_trial._activate(activation, plan)
    classroom_trial._continuation(project, plan)
    state.load_project(project)
    if manifest.exists():
        _need(plan_path.is_file() and state.read_json(plan_path) == plan,
              'Existing refill input belongs to another plan; do not overwrite')
        result = _validate(project, {'path': state.relative_path(project, manifest),
                                     'sha256': state.sha256(manifest)})
    else:
        _need(not output.exists() and not plan_path.exists(),
              'Refill input output or plan already exists without complete provenance; do not overwrite')
        inventory = _inventory(source, plan['mapping'])
        animation._parent(output.parent)
        _write(plan_path, plan)
        with source.open('rb') as reader, output.open('xb') as writer:
            shutil.copyfileobj(reader, writer, 4 * 1024 * 1024)
        animation._sources(project, plan)
        _need(state.sha256(output) == plan['source_sha256'], 'Refill input copy differs from source')
        receipt = _receipt(project, plan, output, plan_path, inventory)
        _write(manifest, receipt)
        result = _validate(project, {'path': state.relative_path(project, manifest),
                                     'sha256': state.sha256(manifest)})
    state.register_artifact(project, ARTIFACT, result['path'], list(result['source_versions']), _metadata(result))
    return result


def current(project):
    """Recheck immutable input provenance and the current separate registration."""
    project = Path(project).resolve()
    record = state.load_project(project)
    registered = record.get('artifacts', {}).get(ARTIFACT)
    _need(registered is not None and ARTIFACT not in record.get('stale_targets', []),
          'No current, non-stale provided refill trial input')
    result = _validate(project, registered.get('refill_input_manifest'))
    _need(registered.get('path') == result['path'] and registered.get('sha256') == result['sha256']
          and all(registered.get(key) == value for key, value in _metadata(result).items()),
          'Provided refill registration differs from its verified input receipt')
    return result
