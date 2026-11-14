"""Validate teaching plans and create immutable native classroom-animation copies.

The caller supplies pedagogical decisions and actual instruction evidence. This
module binds those decisions to real objects; it does not infer teaching intent.
No Office process, course approval, or final-product registration is performed.
"""
from copy import deepcopy
import hashlib
import io
import json
import math
from pathlib import Path
import re
import zipfile

from . import pptx_editor as editor, state

VERSION = 'classroom_animation_v1'
NS = editor.NS
ET = editor.ET
ROLES = {'context', 'question', 'evidence', 'answer', 'explanation', 'conclusion', 'marker'}
KINDS = {'text', 'fraction', 'code', 'diagram', 'group'}
PURPOSES = {'answer', 'notation_instruction', 'observation', 'explanation'}
ENTRANCES = {'appear', 'fade', 'wipe'}
EXITS = {'disappear', 'fade_out'}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value, label):
    _need(isinstance(value, str) and bool(value.strip()), label + ' must be nonempty text')
    return value


def _id(value, label):
    _need(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]+', value),
          label + ' must be a stable ASCII ID')
    return value


def _fields(value, required, optional, label):
    editor._known_fields(value, set(required) | set(optional), label)
    missing = set(required) - set(value)
    _need(not missing, label + ' missing fields: ' + ', '.join(sorted(missing)))


def _path(project, relative):
    _text(relative, 'file path')
    _need('\\' not in relative and ':' not in relative and '..' not in Path(relative).parts,
          'Use a relative project path without traversal: ' + relative)
    return editor._inside(project, relative)


def _file(project, relative):
    path = _path(project, relative)
    _need(path.is_file(), 'Missing source file: ' + relative)
    return path


def _sources(project, plan):
    _text(plan['source_deck'], 'source_deck')
    versions = plan['source_versions']
    _need(isinstance(versions, dict) and bool(versions), 'Bound source_versions required')
    for relative, sha in versions.items():
        _need(isinstance(sha, str) and re.fullmatch(r'[a-f0-9]{64}', sha), 'Invalid source hash')
        _need(editor.sha256(_file(project, relative)) == sha, 'Source hash changed: ' + relative)
    _need(versions.get(plan['source_deck']) == plan['source_sha256'],
          'Source deck must be bound in source_versions')


def _instruction(project, plan):
    request = plan['request']
    _fields(request, {'user_instruction', 'evidence_ref'}, set(), 'request')
    instruction = _text(request['user_instruction'], 'Actual user instruction')
    evidence = request['evidence_ref']
    _fields(evidence, {'path', 'sha256'}, set(), 'instruction evidence')
    _text(evidence['path'], 'instruction evidence path')
    _need(evidence['path'] in plan['source_versions']
          and plan['source_versions'][evidence['path']] == evidence['sha256'],
          'Actual instruction evidence must be locked in source_versions')
    text = _file(project, evidence['path']).read_text(encoding='utf-8-sig')
    # JSON evidence may escape quotes/newlines; compare decoded strings too.
    try:
        decoded = json.loads(text)
    except ValueError:
        decoded = text

    def contains(value):
        if isinstance(value, str):
            return instruction in value
        if isinstance(value, dict):
            return any(contains(v) for v in value.values())
        return isinstance(value, list) and any(contains(v) for v in value)

    _need(contains(decoded), 'Actual instruction is absent from the locked evidence')


def _paragraphs(node):
    return [''.join('\n' if editor._local(n) == 'br' else (n.text or '')
                    for n in paragraph.iter() if editor._local(n) in {'t', 'br'})
            for paragraph in node.findall('p:txBody/a:p', NS)]


def _objects(root):
    nodes = editor._shape_nodes(root)
    objects = {}
    for node in nodes:
        identity = editor._identity(node)
        _need(identity is not None and (identity.get('id') or '').isdigit(), 'Invalid actual shape ID')
        sid = int(identity.get('id'))
        _need(sid not in objects, 'Duplicate actual shape ID')
        parents = [p for p in node.iterancestors() if editor._local(p) == 'grpSp']
        objects[sid] = {'node': node, 'shape_id': sid, 'name': identity.get('name'),
                        'type': editor._local(node), 'text': editor._text(node),
                        'paragraphs': _paragraphs(node),
                        'ancestors': [int(editor._identity(p).get('id')) for p in parents],
                        'hidden': any(editor._identity(p).get('hidden') in {'1', 'true'}
                                      for p in [node, *parents])}
    for sid, obj in objects.items():
        obj['descendants'] = sorted(k for k, value in objects.items() if sid in value['ancestors'])
    return objects


def _existing_targets(timing):
    if timing is None:
        return []
    targets = []
    for target in timing.findall('.//p:spTgt', NS):
        sid = target.get('spid', '')
        _need(sid.isdigit(), 'Existing timing has an invalid target shape ID')
        bounds = target.find('p:txEl/p:pRg', NS)
        if bounds is not None:
            start, end = bounds.get('st', ''), bounds.get('end', '')
            _need(start.isdigit() and end.isdigit() and int(start) <= int(end),
                  'Existing timing has an invalid paragraph range')
            targets.append({'shape_id': int(sid), 'paragraph_start': int(start), 'paragraph_end': int(end)})
        else:
            # Unknown sub-object targeting is conservatively treated as whole.
            targets.append({'shape_id': int(sid)})
    for node in timing.findall('p:bldLst/*', NS):
        sid = node.get('spid', '')
        if sid.isdigit() and not any(t['shape_id'] == int(sid) for t in targets):
            targets.append({'shape_id': int(sid)})
    return targets


def inspect(source_path):
    """Read exact native object IDs, paragraph indices and existing targets."""
    source = Path(source_path)
    before = editor.sha256(source)
    parts = editor._parts(source)
    slides = []
    for index, part in enumerate(editor._slides(parts), 1):
        root = editor._parse(parts[part])
        timing = root.find('p:timing', NS)
        objects = [{k: v for k, v in obj.items() if k != 'node'} for obj in _objects(root).values()]
        slides.append({'slide_index': index, 'part': part, 'objects': objects,
                       'has_existing_timing': timing is not None,
                       'existing_targets': _existing_targets(timing),
                       'timing_sha256': editor._digest(editor._xml_value(timing)),
                       'existing_interactive_sequences': len(root.findall(".//p:cTn[@nodeType='interactiveSeq']", NS))})
    _need(editor.sha256(source) == before, 'Source changed during inspection')
    return {'source_sha256': before, 'slides': slides,
            'media': {n: hashlib.sha256(v).hexdigest() for n, v in parts.items() if n.startswith('ppt/media/')},
            'playback': 'unverified'}


def _overlap(left, right, objects):
    a, b = left['shape_id'], right['shape_id']
    if a != b:
        return a in objects.get(b, {}).get('ancestors', []) or b in objects.get(a, {}).get('ancestors', [])
    if not any(k in left for k in ('paragraph', 'paragraph_start')):
        return True
    if not any(k in right for k in ('paragraph', 'paragraph_start')):
        return True
    lstart, lend = left.get('paragraph', left.get('paragraph_start')), left.get('paragraph', left.get('paragraph_end'))
    rstart, rend = right.get('paragraph', right.get('paragraph_start')), right.get('paragraph', right.get('paragraph_end'))
    return lstart <= rend and rstart <= lend


def _units(page, objects, label):
    _need(isinstance(page['units'], list), label + ' units must be an explicit list')
    units, owned, logical = {}, [], {}
    for unit in page['units']:
        _fields(unit, {'unit_id', 'role', 'kind', 'purpose', 'initial_visible', 'targets'},
                {'logical_id', 'objective'}, label + ' unit')
        uid = _id(unit['unit_id'], label + ' unit_id')
        where = label + ' unit ' + uid
        _need(uid not in units, where + ': duplicate unit_id')
        _need(isinstance(unit['role'], str) and isinstance(unit['kind'], str) and isinstance(unit['purpose'], str)
              and unit['role'] in ROLES and unit['kind'] in KINDS and unit['purpose'] in PURPOSES,
              where + ': unsupported role/kind/purpose')
        _need(type(unit['initial_visible']) is bool, where + ': initial_visible must be boolean')
        if unit['kind'] in {'fraction', 'code'} or 'logical_id' in unit:
            logical_id = _id(unit.get('logical_id'), where + ' logical_id')
            logical.setdefault(logical_id, []).append(unit)
        if unit['purpose'] == 'notation_instruction':
            _text(unit.get('objective'), where + ' notation objective')
        elif 'objective' in unit:
            _need(False, where + ': objective is only for notation_instruction')
        _need(isinstance(unit['targets'], list) and bool(unit['targets']), where + ': nonempty targets required')
        for target in unit['targets']:
            _fields(target, {'shape_id', 'expected_text'}, {'paragraph'}, where + ' target')
            sid = target['shape_id']
            _need(type(sid) is int and sid in objects, where + ': unknown actual shape ID')
            obj = objects[sid]
            _need(not obj['hidden'] and all(not objects[i]['hidden'] for i in obj['descendants']),
                  where + ': hidden source shape or ancestor/descendant')
            _need(target['expected_text'] is None or isinstance(target['expected_text'], str),
                  where + ': expected_text must be string or null')
            if 'paragraph' in target:
                paragraph = target['paragraph']
                _need(type(paragraph) is int and 0 <= paragraph < len(obj['paragraphs']),
                      where + ': invalid actual paragraph index')
                actual_text = obj['paragraphs'][paragraph]
                _need(bool(actual_text.strip()), where + ': empty paragraph cannot form a teaching unit')
            else:
                actual_text = obj['text']
            _need(target['expected_text'] == actual_text, where + ': target text differs from source')
            _need(not any(_overlap(target, previous, objects) for previous in owned),
                  where + ': target ownership overlap (whole/group/paragraph)')
            owned.append(target)
        units[uid] = deepcopy(unit)
    for logical_id, items in logical.items():
        _need(len(items) == 1 or all(u['purpose'] == 'notation_instruction' and u.get('objective', '').strip() for u in items),
              label + ': logical fraction/code ' + logical_id + ' must remain one unit unless teaching notation explicitly')
    return units


def _steps(page, units, objects, label):
    _need(isinstance(page['steps'], list), label + ': steps must be an explicit list')
    if not page['steps']:
        _text(page.get('static_reason'), label + ' static_reason')
    elif 'static_reason' in page:
        _need(False, label + ': static_reason requires a zero-step page')
    visible = {uid for uid, unit in units.items() if unit['initial_visible']}
    states = [{'step_id': None, 'click_index': 0, 'visible_units': sorted(visible), 'emphasized_units': []}]
    normalized, step_ids, touched, emphasized = [], set(), set(), set()
    for position, step in enumerate(page['steps'], 1):
        _fields(step, {'step_id', 'pause_reason', 'actions'}, set(), label + ' step')
        sid = _id(step['step_id'], label + ' step_id')
        where = label + ' step ' + sid
        _need(sid not in step_ids, where + ': duplicate step_id')
        step_ids.add(sid)
        _text(step['pause_reason'], where + ' pause_reason')
        _need(isinstance(step['actions'], list) and bool(step['actions']), where + ': empty click actions')
        actions, last_end, previous_start, previous_end = [], {}, 0, 0
        for index, action in enumerate(step['actions']):
            _fields(action, {'unit_id', 'effect', 'trigger'}, {'duration_ms', 'delay_ms', 'direction', 'scale'}, where + ' action')
            uid, effect, trigger = action['unit_id'], action['effect'], action['trigger']
            _need(isinstance(uid, str) and uid in units, where + ': unknown unit_id')
            _need(isinstance(effect, str) and effect in ENTRANCES | EXITS | {'emphasize'}, where + ': unsupported effect')
            _need(isinstance(trigger, str) and trigger in ({'on_click'} if index == 0 else {'with_previous', 'after_previous'}),
                  where + ': exactly the first action must use on_click trigger')
            duration = action.get('duration_ms', 1 if effect in {'appear', 'disappear'} else 500)
            delay = action.get('delay_ms', 0)
            _need(type(duration) is int and 1 <= duration <= 5000, where + ': duration_ms must be 1..5000')
            _need(type(delay) is int and 0 <= delay <= 2000, where + ': delay_ms must be 0..2000')
            value = {**action, 'duration_ms': duration, 'delay_ms': delay}
            if effect == 'wipe':
                _need(isinstance(action.get('direction'), str) and action['direction'] in {'left', 'right', 'up', 'down'},
                      where + ': wipe requires direction')
            else:
                _need('direction' not in action, where + ': direction only applies to wipe')
            if effect == 'emphasize':
                scale = action.get('scale', 1.25)
                _need(type(scale) in (int, float) and math.isfinite(scale) and 1 < scale <= 2,
                      where + ': emphasize scale must be finite and 1 < scale <= 2')
                _need(all(bool((t['expected_text'] or '').strip()) and objects[t['shape_id']]['paragraphs']
                          for t in units[uid]['targets']), where + ': emphasize requires actual visible text targets')
                value['scale'] = scale
            else:
                _need('scale' not in action, where + ': scale only applies to emphasize')
            start = delay + (previous_end if trigger == 'after_previous' else previous_start if trigger == 'with_previous' else 0)
            _need(uid not in last_end or start >= last_end[uid], where + ': overlapping actions on the same unit')
            if effect in ENTRANCES:
                _need(uid not in visible, where + ': repeated entrance on an already visible unit')
                visible.add(uid)
            elif effect in EXITS:
                _need(uid in visible, where + ': exit requires a visible unit')
                visible.remove(uid)
            else:
                _need(uid in visible, where + ': emphasize requires a visible unit')
                emphasized.add(uid)
            previous_start, previous_end = start, start + duration
            last_end[uid] = previous_end
            touched.add(uid)
            actions.append(value)
        normalized.append({**step, 'actions': actions})
        states.append({'step_id': sid, 'click_index': position, 'visible_units': sorted(visible),
                       'emphasized_units': sorted(emphasized & visible)})
    _need(all(u['initial_visible'] or uid in touched for uid, u in units.items()),
          label + ': an initially hidden unit is never revealed')
    return normalized, states


def _prepare(project, plan):
    _fields(plan, {'schema_version', 'mode', 'source_deck', 'source_sha256', 'source_versions',
                   'output', 'request', 'mapping', 'pages'}, set(), 'classroom animation plan')
    _need(plan['schema_version'] == VERSION and plan['mode'] == 'classroom', 'Unknown classroom plan version or mode')
    _sources(project, plan)
    _instruction(project, plan)
    source, output = _file(project, plan['source_deck']), _path(project, plan['output'])
    protected = {output, output.with_suffix('.plan.json'), output.with_suffix('.manifest.json')}
    _need(output.suffix.lower() == '.pptx' and all(_file(project, p) not in protected for p in plan['source_versions']),
          'Output and sidecars must be new paths distinct from every source')
    parts = editor._parts(source)
    slide_parts = editor._slides(parts)
    editor._mapping(plan['mapping'], len(slide_parts))
    _need(isinstance(plan['pages'], list) and all(isinstance(p, dict) for p in plan['pages']), 'pages must be a list of objects')
    for page in plan['pages']:
        _id(page.get('page_id'), 'page_id')
    _need(len(plan['pages']) == len(plan['mapping']) and
          {p.get('page_id') for p in plan['pages']} == set(plan['mapping']), 'Every mapped page must appear exactly once')
    pages = []
    for page in plan['pages']:
        _fields(page, {'page_id', 'teaching_goal', 'student_action', 'basis', 'initial_reason', 'units', 'steps', 'existing_policy'},
                {'existing_reason', 'static_reason'}, 'classroom page')
        label = _id(page['page_id'], 'page_id')
        for name in ('teaching_goal', 'student_action', 'initial_reason'):
            _text(page[name], label + ' ' + name)
        _fields(page['basis'], {'path', 'locator'}, set(), label + ' basis')
        _text(page['basis']['path'], label + ' basis path')
        _need(page['basis']['path'] in plan['source_versions'], label + ': page basis must be a bound source')
        _text(page['basis']['locator'], label + ' basis locator')
        _need(isinstance(page['existing_policy'], str) and page['existing_policy'] in {'reject_conflicts', 'append_after_existing'},
              label + ': unknown existing_policy')
        if page['existing_policy'] == 'append_after_existing':
            _text(page.get('existing_reason'), label + ' existing_reason')
        elif 'existing_reason' in page:
            _need(False, label + ': existing_reason requires append_after_existing')
        index = plan['mapping'][label]
        part = slide_parts[index - 1]
        original = editor._parse(parts[part])
        objects = _objects(original)
        units = _units(page, objects, label)
        steps, states = _steps(page, units, objects, label)
        previous = original.find('p:timing', NS)
        existing_targets = _existing_targets(previous)
        for uid, unit in units.items():
            _need(not any(_overlap(t, existing, objects) for t in unit['targets'] for existing in existing_targets),
                  label + ' unit ' + uid + ': existing animation ownership conflict')
        if steps and previous is not None:
            _need(page['existing_policy'] == 'append_after_existing',
                  label + ': existing timing requires explicit append_after_existing and existing_reason')
        from .classroom_timing import compile_timing
        timing = compile_timing(previous, steps, units) if steps else deepcopy(previous)
        pages.append({'page_id': label, 'slide_index': index, 'part': part, 'original': original,
                      'objects': objects, 'units': units, 'steps': steps, 'states': states,
                      'existing_timing': previous, 'timing': timing})
    _sources(project, plan)
    return {'project': project, 'source': source, 'output': output, 'parts': parts,
            'pages': sorted(pages, key=lambda p: p['slide_index'])}


def _summary(context):
    return {'ready_for_review': True, 'playback': 'unverified',
            'state_scope': 'Managed units only; existing animation playback and unmanaged visibility are not inferred',
            'pages': [{'page_id': p['page_id'], 'slide_index': p['slide_index'], 'part': p['part'],
                       'click_count': len(p['steps']), 'states': p['states'],
                       'has_existing_timing': p['existing_timing'] is not None,
                       'existing_targets': _existing_targets(p['existing_timing']),
                       'managed_units': list(p['units'].values())} for p in context['pages']]}


def check(project, plan):
    """Read-only semantic and compiler check; no output or approval mutation."""
    return _summary(_prepare(Path(project).resolve(), plan))


def _patched(context):
    patched = {}
    for page in context['pages']:
        if not page['steps']:
            continue
        root = deepcopy(page['original'])
        old = root.find('p:timing', NS)
        if old is not None:
            root.replace(old, deepcopy(page['timing']))
        else:
            extension = root.find('p:extLst', NS)
            root.insert(root.index(extension) if extension is not None else len(root), deepcopy(page['timing']))
        patched[page['part']] = ET.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    return patched


def _package(context, patched):
    if not patched:
        return context['source'].read_bytes()
    output = io.BytesIO()
    with zipfile.ZipFile(context['source']) as source, zipfile.ZipFile(output, 'w') as archive:
        archive.comment = source.comment
        for info in source.infolist():
            archive.writestr(info, patched.get(info.filename, context['parts'][info.filename]))
    return output.getvalue()


def _verify(context, candidate):
    after = editor._parts(candidate)
    _need(set(after) == set(context['parts']), 'Output package parts changed')
    mapped = {p['part']: p for p in context['pages'] if p['steps']}
    for part, data in context['parts'].items():
        page = mapped.get(part)
        if page is None:
            _need(after[part] == data, 'Non-target ZIP part changed: ' + part)
            continue
        root = editor._parse(after[part])
        actual = root.find('p:timing', NS)
        _need(editor._xml_value(actual) == editor._xml_value(page['timing']),
              page['page_id'] + ': timing differs from deterministic plan compilation')
        _need(len(root.findall('p:timing', NS)) == 1, page['page_id'] + ': duplicate timing')
        old = page['original'].find('p:timing', NS)
        if old is None:
            root.remove(actual)
        else:
            root.replace(actual, deepcopy(old))
        _need(editor._xml_value(root) == editor._xml_value(page['original']),
              page['page_id'] + ': original shapes/layout/media/slide metadata changed')
    return {**_summary(context), 'checks': {'source_unchanged': True, 'slide_content_preserved': True,
             'non_target_parts_preserved': True, 'timing_matches_compilation': True}}


def _write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def _parent(path):
    missing, current = [], path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir()
        (directory / 'AGENTS.md').write_text('# Classroom animation outputs\nImmutable generated plans, PPTX candidates and '
                                            'manifests. Preserve failed attempts and sources; no automatic cleanup. '
                                            'Candidate structure is not playback or lesson approval.\n', encoding='utf-8')


def _report(project, path, data, idempotent):
    return {**data, 'manifest': state.relative_path(project, path), 'manifest_sha256': editor.sha256(path),
            'idempotent': idempotent}


def build(project, plan):
    """Create/recover an immutable candidate. Never selects a final course artifact."""
    project = Path(project).resolve()
    plan = deepcopy(plan)
    context = _prepare(project, plan)
    output = context['output']
    plan_path, manifest_path = output.with_suffix('.plan.json'), output.with_suffix('.manifest.json')
    digest = editor._digest(plan)
    if plan_path.exists():
        _need(editor._digest(state.read_json(plan_path)) == digest, 'Existing plan differs; do not overwrite')
    else:
        _need(not output.exists() and not manifest_path.exists(), 'Existing output lacks immutable plan; do not overwrite')
        _parent(output.parent)
        _write_new(plan_path, plan)
    plan_sha = editor.sha256(plan_path)
    if manifest_path.exists():
        return validate_final(project, state.relative_path(project, manifest_path))
    recovered = output.exists()
    if not recovered:
        candidate = _package(context, _patched(context))
        _sources(project, plan)
        _need(editor.sha256(plan_path) == plan_sha, 'Immutable plan changed during build')
        with output.open('xb') as stream:
            stream.write(candidate)
    output_sha = editor.sha256(output)
    verified = _verify(context, output)
    _sources(project, plan)
    _need(editor.sha256(output) == output_sha and editor.sha256(plan_path) == plan_sha,
          'Output or immutable plan changed during validation')
    data = {'schema_version': VERSION, 'plan_sha256': digest,
            'plan': {'path': state.relative_path(project, plan_path), 'sha256': plan_sha},
            'source_deck': plan['source_deck'], 'source_sha256': plan['source_sha256'],
            'source_versions': plan['source_versions'], 'output': plan['output'], 'output_sha256': output_sha,
            'recovered_output': recovered, **verified}
    _write_new(manifest_path, data)
    return _report(project, manifest_path, data, False)


def validate_final(project, manifest_ref):
    """Recompute from locked sources and plan; a manifest ready flag is not proof."""
    project = Path(project).resolve()
    if isinstance(manifest_ref, dict):
        _fields(manifest_ref, {'path', 'sha256'}, set(), 'manifest reference')
        path = _file(project, manifest_ref['path'])
        _need(editor.sha256(path) == manifest_ref['sha256'], 'Manifest hash changed')
    else:
        path = _file(project, manifest_ref)
    manifest_sha = editor.sha256(path)
    data = state.read_json(path)
    expected_keys = {'schema_version', 'plan_sha256', 'plan', 'source_deck', 'source_sha256', 'source_versions',
                     'output', 'output_sha256', 'recovered_output', 'ready_for_review', 'playback', 'state_scope', 'pages', 'checks'}
    _fields(data, expected_keys, set(), 'classroom manifest')
    _need(data['schema_version'] == VERSION and type(data['recovered_output']) is bool, 'Unknown classroom manifest')
    _fields(data['plan'], {'path', 'sha256'}, set(), 'immutable plan reference')
    plan_path = _file(project, data['plan']['path'])
    _need(editor.sha256(plan_path) == data['plan']['sha256'], 'Immutable plan hash changed')
    plan = state.read_json(plan_path)
    _need(editor._digest(plan) == data['plan_sha256'], 'Manifest plan digest differs')
    context = _prepare(project, plan)
    output = context['output']
    _need(plan_path == output.with_suffix('.plan.json') and path == output.with_suffix('.manifest.json'),
          'Manifest and plan must remain beside their immutable output')
    _need(output.is_file() and editor.sha256(output) == data['output_sha256'], 'Output hash changed or file missing')
    for key in ('source_deck', 'source_sha256', 'source_versions', 'output'):
        _need(data[key] == plan[key], 'Manifest source/output binding differs: ' + key)
    verified = _verify(context, output)
    for key, value in verified.items():
        _need(data[key] == value, 'Manifest differs from actual verified ' + key)
    _sources(project, plan)
    _need(editor.sha256(output) == data['output_sha256'], 'Output hash changed during validation')
    _need(editor.sha256(plan_path) == data['plan']['sha256'] and editor.sha256(path) == manifest_sha,
          'Immutable plan or manifest changed during validation')
    return _report(project, path, data, True)


def snapshot(project, manifest_ref, output, stage='final'):
    """Project known managed visibility into a separate immutable static PPTX.

    Unmanaged objects retain source visibility. Existing timelines are not
    simulated. Final font emphasis cannot be inferred from inherited fonts.
    """
    project = Path(project).resolve()
    _need(isinstance(stage, str) and stage in {'initial', 'final'}, 'Snapshot stage must be initial or final')
    verified = validate_final(project, manifest_ref)
    plan = state.read_json(_file(project, verified['plan']['path']))
    context = _prepare(project, plan)
    destination = _path(project, output)
    manifest_path = destination.with_suffix('.snapshot.json')
    protected = {_file(project, p) for p in plan['source_versions']}
    protected.update({_path(project, verified[k]) for k in ('output', 'manifest')})
    protected.add(_file(project, verified['plan']['path']))
    _need(destination.suffix.lower() == '.pptx' and destination not in protected and manifest_path not in protected,
          'Snapshot must use a new PPTX path separate from all inputs and classroom output')
    projected, patched = [], {}
    for page in context['pages']:
        if not page['units']:
            continue
        _need(page['existing_timing'] is None,
              page['page_id'] + ': static snapshot cannot infer pre-existing animation states')
        selected = page['states'][0 if stage == 'initial' else -1]
        _need(stage != 'final' or not selected['emphasized_units'],
              page['page_id'] + ': final static emphasis font sizes require a native export, not inferred fonts')
        root = deepcopy(page['original'])
        objects = _objects(root)
        visible = set(selected['visible_units'])
        for uid, unit in page['units'].items():
            if uid in visible:
                continue
            for target in unit['targets']:
                node = objects[target['shape_id']]['node']
                if 'paragraph' in target:
                    paragraph = node.findall('p:txBody/a:p', NS)[target['paragraph']]
                    for child in list(paragraph):
                        if editor._local(child) not in {'pPr', 'endParaRPr'}:
                            paragraph.remove(child)
                else:
                    node.getparent().remove(node)
        projected.append(page['page_id'])
        patched[page['part']] = ET.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    _need(bool(projected), 'Snapshot requires at least one mapped page with managed units')
    candidate = _package(context, patched)
    candidate_sha = hashlib.sha256(candidate).hexdigest()
    data = {'schema_version': 'classroom_static_snapshot_v1',
            'classroom_manifest': {'path': verified['manifest'], 'sha256': verified['manifest_sha256']},
            'output': output, 'output_sha256': candidate_sha, 'stage': stage,
            'projected_pages': projected,
            'scope': 'Managed unit visibility on listed pages only; other pages and unmanaged objects retain source content',
            'playback': 'unverified', 'static_rendering': 'unverified'}
    existed = destination.exists()
    if existed:
        _need(editor.sha256(destination) == candidate_sha, 'Static snapshot output differs; do not overwrite')
    if manifest_path.exists():
        _need(existed and state.read_json(manifest_path) == data, 'Static snapshot manifest differs; do not overwrite')
    # Recheck all bindings before either new write, including the classroom PPTX.
    validate_final(project, data['classroom_manifest'])
    if not existed:
        _parent(destination.parent)
        with destination.open('xb') as stream:
            stream.write(candidate)
    _need(editor.sha256(destination) == candidate_sha, 'Static snapshot changed during creation')
    if not manifest_path.exists():
        _write_new(manifest_path, data)
    return _report(project, manifest_path, data, existed)
