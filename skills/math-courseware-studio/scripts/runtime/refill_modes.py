"""Text coverage for faithful restoration and explicitly selected teaching reveals."""
from copy import deepcopy

MODES = {'faithful_restore', 'teaching_reveal'}


def resolve_modes(plan):
    default = plan.get('refill_mode', 'faithful_restore')
    overrides = plan.get('page_modes', {})
    mapping = plan.get('mapping', {})
    if not isinstance(default, str) or default not in MODES:
        raise ValueError('Unknown refill mode')
    if (not isinstance(overrides, dict) or set(overrides) - set(mapping)
            or any(not isinstance(mode, str) or mode not in MODES for mode in overrides.values())):
        raise ValueError('Invalid page refill modes')
    return {page_id: overrides.get(page_id, default) for page_id in mapping}


def visibility(page):
    units = page.get('text_units', [])
    ids = {unit['unit_id'] for unit in units}
    if len(ids) != len(units):
        raise ValueError(page['page_id'] + ': duplicate authoritative text unit')
    steps, membership = set(), {}
    for step in page.get('reveal_steps', []):
        step_id = step.get('step_id')
        members = step.get('unit_ids', [])
        if (not isinstance(step_id, str) or not step_id.strip() or step_id == 'initial' or step_id in steps
                or not isinstance(members, list) or any(not isinstance(unit_id, str) for unit_id in members)):
            raise ValueError(page['page_id'] + ': invalid reveal step')
        steps.add(step_id)
        for unit_id in members:
            if unit_id not in ids or unit_id in membership:
                raise ValueError(page['page_id'] + ': unknown or repeated reveal membership')
            membership[unit_id] = step_id
    result = {}
    for unit in units:
        unit_id = unit['unit_id']
        at = unit.get('visible_at', membership.get(unit_id, 'initial'))
        if (not isinstance(at, str) or (at != 'initial' and at not in steps)
                or (unit_id in membership and at != membership[unit_id])):
            raise ValueError(page['page_id'] + ': conflicting or unknown visible_at for ' + unit_id)
        result[unit_id] = at
    return result


def native_required(page, mode):
    steps = {step['step_id'] for step in page.get('reveal_steps', [])}
    required = set()
    for obj in page.get('native_objects', []):
        at = obj.get('visible_at', 'initial')
        if not isinstance(at, str) or (at != 'initial' and at not in steps):
            raise ValueError(page['page_id'] + ': unknown native object visible_at')
        if obj.get('required', True) and (mode == 'teaching_reveal' or at == 'initial'):
            required.add(obj['object_id'])
    return required


def validate_content(pages, plan, legacy_replay=False):
    modes = resolve_modes(plan)
    units = plan.get('text_units', [])
    if any(unit['page_id'] not in modes for unit in units):
        raise ValueError('Text unit page is outside the reviewed page mapping')
    result = {'refill_mode': plan.get('refill_mode', 'faithful_restore'), 'page_modes': modes,
              'pages': {}, 'shared_text': [], 'historical_coverage_preserved': legacy_replay}
    owners = {}
    for unit in units:
        pieces = unit.get('segments', unit.get('instances', []))
        if pieces:
            for piece in pieces:
                if 'reuse_object_id' not in piece:
                    owners[(unit['page_id'], piece['object_id'])] = unit['unit_id']
        else:
            owners[(unit['page_id'], unit['unit_id'])] = unit['unit_id']
    for page_id, mode in modes.items():
        page = pages[page_id]
        at = visibility(page)
        included = [u for u in page.get('text_units', [])
                    if legacy_replay or mode == 'teaching_reveal' or at[u['unit_id']] == 'initial']
        expected = {u['unit_id']: u['text'] for u in included}
        selected = [u for u in units if u['page_id'] == page_id]
        actual = {u['unit_id']: u['text'] for u in selected}
        if len(actual) != len(selected) or actual != expected:
            raise ValueError(page_id + ': editable plan must cover every authoritative text unit for its refill mode exactly')
        deferred = [deepcopy(u) for u in page.get('text_units', []) if u['unit_id'] not in expected]
        for unit in deferred:
            unit['visible_at'] = at[unit['unit_id']]
        result['pages'][page_id] = {
            'initial_unit_ids': [unit_id for unit_id, when in at.items() if when == 'initial'],
            'included_unit_ids': list(expected), 'deferred_text_units': deferred,
            'unit_visibility': at}
        for unit in selected:
            for piece in unit.get('segments', []):
                if 'reuse_object_id' in piece:
                    owner = owners.get((page_id, piece['reuse_object_id']))
                    if at.get(owner) != 'initial':
                        raise ValueError(page_id + ': shared text must reference an initial object on the same page')
                    result['shared_text'].append({'page_id': page_id, 'unit_id': unit['unit_id'],
                        'object_id': piece['reuse_object_id'], 'text': piece['text']})
    return result
