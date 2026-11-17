"""Remove explicitly selected teaching effects while preserving other native timing."""
from copy import deepcopy

from . import pptx_editor as editor

NS, ET = editor.NS, editor.ET
P = '{' + NS['p'] + '}'
EFFECT_TYPES = {'clickEffect', 'withEffect', 'afterEffect'}
BEHAVIORS = {'set', 'anim', 'animEffect', 'animClr', 'animMotion', 'animRot', 'animScale'}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _target(node):
    sid = node.get('spid', '')
    _need(sid.isdecimal(), 'Retiming requires a valid actual shape target')
    value = {'shape_id': int(sid)}
    if len(node):
        bounds = node.find('p:txEl/p:pRg', NS)
        _need(len(node) == 1 and bounds is not None and len(node[0]) == 1,
              'Retiming does not infer unknown sub-object targets')
        start, end = bounds.get('st', ''), bounds.get('end', '')
        _need(start.isdecimal() and end.isdecimal() and int(start) <= int(end),
              'Retiming requires a valid paragraph range')
        value.update(paragraph_start=int(start), paragraph_end=int(end))
    return value


def _atoms(target, objects):
    sid = target['shape_id']
    _need(sid in objects, 'Retiming target is missing from actual objects')
    obj = objects[sid]
    start = target.get('paragraph', target.get('paragraph_start'))
    if start is not None:
        end = target.get('paragraph', target.get('paragraph_end'))
        _need(type(start) is int and type(end) is int and 0 <= start <= end < len(obj['paragraphs']),
              'Retiming paragraph range is outside the actual shape')
        return {(sid, i) for i in range(start, end + 1)}
    leaves = [i for i in [sid, *obj['descendants']] if objects[i]['type'] != 'grpSp']
    _need(bool(leaves), 'Retiming an empty native group is unsupported')
    return {(i, p) for i in leaves for p in (range(len(objects[i]['paragraphs']))
                                            if objects[i]['paragraphs'] else [None])}


def _prune(parent):
    # Only prune ancestors emptied by a selected removal. Empty timing lists are
    # invalid OOXML; other media, interactive branches and extensions stay intact.
    while parent is not None and parent.tag == P + 'childTnLst' and not len(parent):
        node = parent.getparent()
        if node is None or node.tag != P + 'cTn':
            break
        node.remove(parent)
        kind = node.get('nodeType')
        if kind not in {None, 'mainSeq', 'tmRoot'}:
            break
        if any(editor._local(c) not in {'stCondLst', 'endCondLst'} for c in node):
            break
        wrapper = node.getparent()
        if wrapper is None or wrapper.tag != P + ('seq' if kind == 'mainSeq' else 'par'):
            break
        allowed = {'cTn', 'prevCondLst', 'nextCondLst'} if kind == 'mainSeq' else {'cTn'}
        if (len(wrapper.findall('p:cTn', NS)) != 1 or wrapper.find('.//p:extLst', NS) is not None
                or any(editor._local(c) not in allowed for c in wrapper)):
            break
        parent = wrapper.getparent()
        if parent is None:
            break
        parent.remove(wrapper)
        if parent.tag == P + 'tnLst' and not len(parent):
            parent.getparent().remove(parent)
            break


def _initial_visibility(timing, removed_atoms, objects):
    removed = []
    for setting in list(timing.findall('.//p:set', NS)):
        ancestors = list(setting.iterancestors())
        if any(n.get('nodeType') in EFFECT_TYPES | {'mainSeq', 'interactiveSeq'} for n in ancestors):
            continue
        targets = setting.findall('p:cBhvr/p:tgtEl/p:spTgt', NS)
        if len(targets) != 1:
            continue
        atoms = _atoms(_target(targets[0]), objects)
        if not atoms <= removed_atoms:
            continue
        names = setting.findall('p:cBhvr/p:attrNameLst/p:attrName', NS)
        value = setting.find('p:to/p:strVal', NS)
        if [n.text for n in names] != ['style.visibility'] or value is None or value.get('val') not in {'hidden', 'visible'}:
            continue
        nodes = [*setting.findall('.//p:cTn', NS), *(n for n in ancestors if n.tag == P + 'cTn')]
        conditions = [cond for n in nodes for cond in n.findall('p:stCondLst/p:cond', NS)]
        if any(set(c.attrib) - {'delay'} or c.get('delay') not in {None, '0'} or len(c) for c in conditions):
            continue
        if any(n.findall('p:endCondLst/*', NS) for n in nodes):
            continue
        removed.extend(n.get('id') for n in setting.findall('.//p:cTn', NS))
        parent = setting.getparent()
        parent.remove(setting)
        _prune(parent)
    return removed


def replace_managed(original, specification, units, objects):
    """Return a copy with only hash-bound, fully-owned teaching groups removed.

    A retained main group stays before subsequently compiled steps. Partial
    click-group removal is rejected because it could turn a withEffect into an
    unintended automatic action. Media, interactive and unknown behaviors are
    never selected as teaching effects.
    If no native timing remains, return None so callers omit p:timing entirely.
    """
    _need(original is not None, 'replace_managed requires existing timing')
    _need(isinstance(specification, dict) and set(specification) == {'timing_sha256', 'effect_ids', 'reason'},
          'Retiming requires timing_sha256, effect_ids and reason')
    _need(specification['timing_sha256'] == editor._digest(editor._xml_value(original)),
          'Retiming source timing hash differs')
    selected = specification['effect_ids']
    _need(isinstance(selected, list) and selected and all(isinstance(i, str) and i.isdecimal() for i in selected)
          and len(set(selected)) == len(selected), 'Retiming effect_ids must be unique nonempty native IDs')
    _need(isinstance(specification['reason'], str) and specification['reason'].strip(), 'Retiming reason is required')
    timing = deepcopy(original)
    mains = timing.findall(".//p:cTn[@nodeType='mainSeq']", NS)
    _need(len(mains) == 1, 'Retiming requires one native main sequence')
    main = mains[0]
    effects = [n for n in main.findall('.//p:cTn', NS) if n.get('nodeType') in EFFECT_TYPES]
    by_id = {n.get('id'): n for n in effects}
    _need(len(by_id) == len(effects), 'Retiming found duplicate native effect IDs')
    _need(set(selected) <= set(by_id), 'Retiming selects an unknown or non-main teaching effect')
    owned_atoms = set().union(*(_atoms(t, objects) for u in units.values() for t in u['targets'])) if units else set()
    old_atoms, build_keys = set(), set()
    for ident in selected:
        effect = by_id[ident]
        _need(effect.get('presetClass') in {'entr', 'exit', 'emph', 'path'},
              'Retiming may select teaching effects only, never media commands')
        _need(not any(editor._local(n) in {'audio', 'video', 'cmd', 'sndTgt', 'sndAc', 'extLst'} for n in effect.iter()),
              'Retiming cannot discard media or unknown extensions')
        behaviors = [n for n in effect.iter() if n.find('p:cBhvr', NS) is not None]
        _need(behaviors and all(editor._local(n) in BEHAVIORS for n in behaviors),
              'Retiming cannot discard an unknown teaching behavior')
        targets = effect.findall('.//p:spTgt', NS)
        _need(bool(targets), 'Retiming effect has no actual shape target')
        for target in targets:
            atoms = _atoms(_target(target), objects)
            _need(atoms <= owned_atoms, 'Retiming effect target is not fully owned by managed units')
            old_atoms.update(atoms)
            build_keys.add((target.get('spid'), effect.get('grpId')))
    main_children = main.find('p:childTnLst', NS)
    _need(main_children is not None, 'Retiming main sequence lacks a child list')
    groups = []
    for wrapper in main_children:
        contained = [n for n in wrapper.findall('.//p:cTn', NS) if n.get('nodeType') in EFFECT_TYPES]
        chosen = [n for n in contained if n.get('id') in selected]
        if chosen:
            _need(len(chosen) == len(contained), 'Retiming must select an entire original click group')
            # Only pure time containers around the selected effects may vanish.
            outside = [n for n in wrapper.iter() if not any(e is n or e in n.iterancestors() for e in chosen)]
            _need(all(editor._local(n) in {'par', 'cTn', 'childTnLst', 'stCondLst', 'endCondLst', 'cond'} for n in outside),
                  'Retiming click group includes unselected or unknown behavior')
            groups.append(wrapper)
    _need(sum(len([n for n in g.findall('.//p:cTn', NS) if n.get('id') in selected]) for g in groups) == len(selected),
          'Retiming effect nesting is unsupported')
    for group in groups:
        main_children.remove(group)
    initial_ids = _initial_visibility(timing, old_atoms, objects)
    builds = timing.find('p:bldLst', NS)
    if builds is not None:
        for build in list(builds):
            key = (build.get('spid'), build.get('grpId'))
            remaining = [n for n in timing.findall('.//p:cTn', NS)
                         if n.get('grpId') == key[1] and any(t.get('spid') == key[0] for t in n.findall('.//p:spTgt', NS))]
            if key in build_keys and not remaining:
                _need(editor._local(build) == 'bldP', 'Retiming cannot discard an unknown build kind')
                builds.remove(build)
        if not len(builds):
            timing.remove(builds)
    _prune(main_children)
    before_ids = {n.get('id') for n in original.findall('.//p:cTn', NS)}
    removed_ids = before_ids - {n.get('id') for n in timing.findall('.//p:cTn', NS)}
    _need(not any(n.get('val') in removed_ids for n in timing.findall('.//p:tn', NS)),
          'Retiming would leave an external timing reference dangling')
    record = {'source_timing_sha256': specification['timing_sha256'],
              'removed_effect_ids': selected, 'removed_initial_visibility_ids': initial_ids,
              'retained_main_effect_ids': [n.get('id') for n in timing.findall(".//p:cTn[@nodeType='mainSeq']//p:cTn", NS)
                                           if n.get('nodeType') in EFFECT_TYPES]}
    if not len(timing):
        _need(not timing.attrib, 'Retiming cannot discard unknown timing attributes')
        timing = None
    return timing, record
