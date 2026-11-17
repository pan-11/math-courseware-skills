"""Bind a full-page teaching inventory and expected clicks to a V1 candidate.

This checks the supplied, frozen teaching decisions. It does not infer whether a
lesson is pedagogically correct, inspect pixels, or certify native playback.
"""
from pathlib import Path

from . import classroom_animation as animation, state

VERSION = 'classroom_teaching_contract_v1'
PAGE_TYPES = {'teaching', 'activity_static', 'media', 'cover', 'preserve_scope'}
RETAINED = {'background', 'decoration', 'media', 'existing_animation', 'static_content', 'out_of_scope'}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _reference(project, value, versions, label):
    animation._fields(value, {'path', 'sha256'}, set(), label)
    _need(versions.get(value['path']) == value['sha256'], label + ' must be bound in source_versions')
    path = animation._file(project, value['path'])
    _need(state.sha256(path) == value['sha256'], label + ' hash changed')
    return path


def _targets(targets, objects, label):
    _need(isinstance(targets, list) and bool(targets), label + ': nonempty targets required')
    checked = []
    for target in targets:
        animation._fields(target, {'shape_id', 'expected_text'}, {'paragraph'}, label + ' target')
        sid = target['shape_id']
        _need(type(sid) is int and sid in objects, label + ': unknown actual shape ID')
        obj = objects[sid]
        if 'paragraph' in target:
            para = target['paragraph']
            _need(type(para) is int and 0 <= para < len(obj['paragraphs']), label + ': invalid paragraph')
            text = obj['paragraphs'][para]
        else:
            text = obj['text']
        _need(target['expected_text'] == text, label + ': actual target text changed')
        _need(not any(animation._overlap(target, old, objects) for old in checked),
              label + ': overlapping target inventory')
        checked.append(target)
    return checked


def _atoms(target, objects):
    obj = objects[target['shape_id']]
    if 'paragraph' in target:
        return {(obj['shape_id'], target['paragraph'])}
    ids = obj['descendants'] if obj['type'] == 'grpSp' else [obj['shape_id']]
    result = set()
    for sid in ids:
        item = objects[sid]
        if item['type'] == 'grpSp':
            continue
        paragraphs = [i for i, text in enumerate(item['paragraphs']) if text.strip()]
        result.update((sid, p) for p in paragraphs or [None])
    return result


def _target_key(target):
    return (target['shape_id'], target.get('paragraph', -1))


def _actions(steps, label):
    _need(isinstance(steps, list), label + ': expected_steps must be a list')
    result = []
    for step in steps:
        _need(isinstance(step, dict) and isinstance(step.get('actions'), list) and step['actions'],
              label + ': nonempty expected click actions required')
        actions = []
        for action in step['actions']:
            _need(isinstance(action, dict) and all(k in action for k in ('unit_id', 'effect', 'trigger')),
                  label + ': expected action requires unit/effect/trigger')
            effect = action['effect']
            normalized = {**action, 'duration_ms': action.get('duration_ms', 1 if effect in {'appear', 'disappear'} else 500),
                          'delay_ms': action.get('delay_ms', 0)}
            if effect == 'emphasize':
                normalized['scale'] = action.get('scale', 1.25)
            actions.append(normalized)
        result.append(actions)
    return result


def validate(project, plan, objects_by_slide):
    """Reject omitted objects, changed initial states or changed click grouping."""
    project = Path(project).resolve()
    reference = plan.get('teaching_contract')
    _need(isinstance(reference, dict), 'A bound teaching_contract is required for new V1 builds')
    versions = plan['source_versions']
    path = _reference(project, reference, versions, 'teaching_contract')
    contract = state.read_json(path)
    animation._fields(contract, {'schema_version', 'source', 'basis', 'mapping', 'pages'}, set(), 'teaching contract')
    _need(contract['schema_version'] == VERSION, 'Unknown teaching contract version')
    _reference(project, contract['source'], versions, 'teaching contract source')
    _reference(project, contract['basis'], versions, 'teaching contract basis')
    _need(contract['source'] == {'path': plan['source_deck'], 'sha256': plan['source_sha256']},
          'Teaching contract must use the exact classroom input')
    _need(contract['mapping'] == plan['mapping'], 'Teaching contract mapping differs')
    _need(isinstance(contract['pages'], list) and all(isinstance(p, dict) for p in contract['pages']),
          'Teaching contract pages must be an explicit list')
    expected = {p.get('page_id'): p for p in contract['pages']}
    _need(len(expected) == len(contract['pages']) and set(expected) == set(plan['mapping']),
          'Teaching contract must cover every mapped page exactly once')
    reports = []
    for page in plan['pages']:
        pid = page['page_id']
        target = expected[pid]
        animation._fields(target, {'page_id', 'page_type', 'managed_units', 'retained_objects', 'expected_steps'},
                          {'static_reason'}, pid + ' contract page')
        page_type = target['page_type']
        _need(page_type in PAGE_TYPES, pid + ': invalid contract page_type')
        _need(isinstance(target['managed_units'], list) and isinstance(target['retained_objects'], list),
              pid + ': explicit managed and retained inventories required')
        objects = objects_by_slide[plan['mapping'][pid]]
        managed = {u.get('unit_id'): u for u in target['managed_units']}
        actual = {u.get('unit_id'): u for u in page['units']}
        _need(len(managed) == len(target['managed_units']) and len(actual) == len(page['units'])
              and set(managed) == set(actual), pid + ': managed teaching units differ from contract')
        assigned, covered = [], set()
        for uid, intended in managed.items():
            animation._fields(intended, {'unit_id', 'initial_visible', 'targets'}, set(), pid + ' contract unit')
            _need(type(intended['initial_visible']) is bool and
                  actual[uid]['initial_visible'] == intended['initial_visible'],
                  pid + ': initial visibility differs from teaching contract for ' + str(uid))
            targets = _targets(intended['targets'], objects, pid + '/' + str(uid))
            _need(sorted(actual[uid]['targets'], key=_target_key) == sorted(targets, key=_target_key),
                  pid + ': teaching unit targets differ from contract')
            assigned.extend(targets)
        for retained in target['retained_objects']:
            animation._fields(retained, {'category', 'reason', 'targets'}, set(), pid + ' retained object')
            category = retained['category']
            _need(category in RETAINED, pid + ': invalid retained category')
            animation._text(retained['reason'], pid + ' retained reason')
            _need(category != 'static_content' or page_type in {'activity_static', 'cover', 'preserve_scope'},
                  pid + ': teaching content must be managed explicitly, including initially visible content')
            _need(category != 'out_of_scope' or page_type == 'preserve_scope',
                  pid + ': out_of_scope objects require a preserved page')
            targets = _targets(retained['targets'], objects, pid + ' retained')
            for item in targets:
                ids = {sid for sid, _ in _atoms(item, objects)}
                if category in {'background', 'decoration', 'media'}:
                    _need(all(not (objects[sid]['text'] or '').strip() for sid in ids),
                          pid + ': native teaching text cannot be retained as ' + category)
                if category == 'media':
                    _need(objects[item['shape_id']].get('is_media') is True,
                          pid + ': retained media must identify an actual media object')
                if category == 'existing_animation':
                    _need(objects[item['shape_id']].get('existing_animated') is True,
                          pid + ': retained existing_animation must identify an actual animated object')
            assigned.extend(targets)
        for index, item in enumerate(assigned):
            _need(not any(animation._overlap(item, other, objects) for other in assigned[:index]),
                  pid + ': overlapping managed/retained coverage')
            covered.update(_atoms(item, objects))
        required = set().union(*(_atoms({'shape_id': sid}, objects) for sid in objects)) if objects else set()
        _need(covered == required, pid + ': full-page teaching coverage missing actual objects/paragraphs: ' +
              ','.join(str(x) for x in sorted(required - covered, key=str)[:12]))
        _need(_actions(page['steps'], pid) == _actions(target['expected_steps'], pid),
              pid + ': click contents/order/grouping/effects differ from teaching contract')
        if not target['expected_steps']:
            _need(page_type != 'teaching', pid + ': zero-click teaching page needs a real static/activity/media classification')
            animation._text(target.get('static_reason'), pid + ' contract static_reason')
        else:
            _need(page_type not in {'activity_static', 'media'}, pid + ': static/media page cannot declare teaching clicks')
        reports.append({'page_id': pid, 'slide_index': plan['mapping'][pid], 'page_type': page_type,
                        'managed_unit_count': len(managed), 'covered_atom_count': len(covered),
                        'expected_clicks': len(target['expected_steps'])})
    return {'contract': reference, 'revision': 1, 'complete_inventory': True,
            'matches_declared_teaching_contract': True, 'native_playback': 'unverified',
            'reference_visual_match': 'unverified', 'pages': reports}
