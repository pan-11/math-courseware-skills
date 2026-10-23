"""Immutable, native inline answers added to a retained faithful-restoration PPTX.

OfficeCLI authors only a working copy. Original package bytes are retained except
for the slides receiving new shapes and a verified extension of their timing.
Workflow authorization and final artifact selection belong to the calling host.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid
import zipfile

from PIL import Image
from . import pptx_editor as editor, state

VERSION = 'inline_answers_v1'
COLOR = 'B3261E'
NS = editor.NS
ET = editor.ET
DISPOSITIONS = {'answer', 'open_blank', 'already_visible', 'ambiguous'}

# Empty projection of the native OfficeCLI 1.0.158 appear/onClick timing tree,
# inspected from an actual isolated fixture. Existing timing is compared to its
# own original tree instead; it is never replaced with this template.
EMPTY_TIMING = ET.fromstring(('''<p:timing xmlns:p="''' + NS['p'] + '''">
 <p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
 <p:childTnLst><p:seq concurrent="1" nextAc="seek">
 <p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst/></p:cTn>
 <p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>
 <p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>
 </p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>''').encode())


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value, label):
    _need(isinstance(value, str) and bool(value.strip()), label + ' must be nonempty text')
    return value


def _identifier(value, label):
    _need(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]+', value), label + ' must be a stable ASCII ID')
    return value


def _file(project, relative):
    path = editor._inside(project, _text(relative, 'file path'))
    _need(path.is_file(), 'Missing source file: ' + relative)
    return path


def _sources(project, plan):
    versions = plan.get('source_versions')
    _need(isinstance(versions, dict) and bool(versions), 'Bound source_versions required')
    for relative, sha in versions.items():
        _need(isinstance(sha, str) and re.fullmatch(r'[a-f0-9]{64}', sha), 'Invalid source hash')
        _need(editor.sha256(_file(project, relative)) == sha, 'Source hash changed: ' + relative)
    _need(versions.get(plan['source_deck']) == plan['source_sha256'], 'Source deck must be bound in source_versions')


def _main(timing):
    found = timing.findall(".//p:cTn[@nodeType='mainSeq']/p:childTnLst", NS)
    _need(len(found) == 1 and not timing.findall(".//p:cTn[@nodeType='interactiveSeq']", NS),
          'Unsupported existing timing: a single non-interactive main sequence is required')
    _need(all(node.tag == '{' + NS['p'] + '}par' for node in found[0]),
          'Unsupported existing timing children; preserve the source and resolve the sequence explicitly')
    return found[0]


def _name(page_id, object_id):
    return 'mcw-answer:' + page_id + ':' + object_id


def _prepare(project, plan):
    editor._known_fields(plan, {'schema_version', 'source_deck', 'source_sha256', 'output', 'mapping',
                               'source_versions', 'request', 'pages'}, 'inline answer plan')
    _need(plan.get('schema_version') == VERSION, 'Unknown inline answer plan version')
    _sources(project, plan)
    source = _file(project, plan['source_deck'])
    output = editor._inside(project, plan['output'])
    _need(source != output and output.suffix.lower() == '.pptx', 'Output must be a new PPTX path')
    _need(all(editor._inside(project, p) not in {output, output.with_suffix('.plan.json'),
                                               output.with_suffix('.manifest.json')}
              for p in plan['source_versions']), 'Output cannot be its own source')
    request = plan.get('request', {})
    editor._known_fields(request, {'user_instruction', 'evidence_ref'}, 'request')
    _text(request.get('user_instruction'), 'Actual fabrication instruction')
    evidence = request.get('evidence_ref', {})
    editor._known_fields(evidence, {'path', 'sha256'}, 'instruction evidence')
    _need(evidence.get('path') in plan['source_versions']
          and plan['source_versions'][evidence['path']] == evidence.get('sha256'),
          'Actual instruction evidence must be locked in source_versions')
    inventory = editor.inspect_deck(source)
    editor._mapping(plan.get('mapping'), len(inventory['slides']))
    pages = plan.get('pages')
    _need(isinstance(pages, list) and all(isinstance(p, dict) for p in pages), 'Per-page scan records required')
    _need(len(pages) == len(plan['mapping']) and {p.get('page_id') for p in pages} == set(plan['mapping']),
          'Scan every mapped page exactly once, including zero-blank pages')
    parts = editor._parts(source)
    prepared = []
    for page in pages:
        editor._known_fields(page, {'page_id', 'scan_complete', 'reference_image', 'items'}, 'page scan')
        page_id = _identifier(page['page_id'], 'page_id')
        _need(page.get('scan_complete') is True, page_id + ': complete blank scan required')
        reference = page.get('reference_image')
        _need(reference in plan['source_versions'], page_id + ': missing bound reference image')
        with Image.open(_file(project, reference)) as image:
            image.verify()
        index = plan['mapping'][page_id]
        slide = inventory['slides'][index - 1]
        original = editor._parse(parts[slide['part']])
        shapes = {s['shape_id']: s for s in slide['shapes']}
        _need(len(shapes) == len(slide['shapes']), page_id + ': duplicate source shape IDs')
        items = page.get('items')
        _need(isinstance(items, list), page_id + ': items must be an explicit list')
        blank_ids, object_ids, clicks, normalized = set(), set(), [], []
        for item in items:
            editor._known_fields(item, {'blank_id', 'disposition', 'source_basis', 'reason', 'answer_text',
                                       'derivation', 'box', 'click_order', 'components', 'existing_shapes'}, 'blank')
            blank_id = _identifier(item.get('blank_id'), 'blank_id')
            _need(blank_id not in blank_ids, page_id + ': duplicate blank ID')
            blank_ids.add(blank_id)
            disposition = item.get('disposition')
            _need(disposition in DISPOSITIONS, 'Unknown blank disposition')
            _text(item.get('reason'), 'Blank reason')
            basis = item.get('source_basis', {})
            editor._known_fields(basis, {'path', 'locator'}, 'answer source basis')
            _need(basis.get('path') in plan['source_versions'], 'Answer basis must reference a bound source')
            _text(basis.get('locator'), 'Answer source locator')
            value = deepcopy(item)
            if disposition != 'answer':
                _need(not set(item) & {'answer_text', 'derivation', 'box', 'click_order', 'components'},
                      'Non-answer items cannot create answer objects or clicks')
                if disposition == 'already_visible':
                    existing = item.get('existing_shapes')
                    _need(isinstance(existing, list) and bool(existing), 'Visible answers require actual existing shapes')
                    seen = set()
                    for ref in existing:
                        editor._known_fields(ref, {'shape_id', 'expected_text'}, 'visible shape')
                        sid = ref.get('shape_id')
                        _need(type(sid) is int and sid in shapes and sid not in seen, 'Unknown or duplicate visible shape')
                        seen.add(sid)
                        shape = shapes[sid]
                        if shape['text'] is not None:
                            _need(ref.get('expected_text') == shape['text'], 'Visible answer text differs from source')
                        node = next(n for n in editor._shape_nodes(original) if int(editor._identity(n).get('id')) == sid)
                        ancestors = [node, *[p for p in node.iterancestors() if editor._local(p) == 'grpSp']]
                        _need(all(editor._identity(p).get('hidden') not in {'1', 'true'} for p in ancestors),
                              'Already-visible answer or its parent group is hidden')
                        ancestor_ids = {editor._identity(p).get('id') for p in ancestors}
                        entrances = original.findall(".//p:cTn[@presetClass='entr']//p:spTgt", NS)
                        _need(all(n.get('spid') not in ancestor_ids for n in entrances),
                              'Already-visible answer or its parent has an existing entrance animation; resolve its initial state')
                else:
                    _need('existing_shapes' not in item, 'Only already_visible can bind source shapes')
                normalized.append(value)
                continue
            _need('existing_shapes' not in item, 'New answers cannot animate existing source shapes')
            answer_text = _text(item.get('answer_text'), 'Answer text')
            _text(item.get('derivation'), 'Answer derivation')
            order = item.get('click_order')
            _need(type(order) is int and order > 0, 'Positive integer click_order required')
            clicks.append(order)
            box = editor._box({'box': item.get('box')}, inventory['width_pt'], inventory['height_pt'])
            components = item.get('components')
            _need(isinstance(components, list) and bool(components), 'Answer components required')
            joined, actual = [], []
            for component in components:
                editor._known_fields(component, {'object_id', 'kind', 'text', 'box', 'font'}, 'answer component')
                oid = _identifier(component.get('object_id'), 'object_id')
                _need(oid not in object_ids, 'Duplicate answer component ID')
                object_ids.add(oid)
                name = _name(page_id, oid)
                _need(all(s['name'] != name for s in shapes.values()), 'Answer object name already exists')
                kind = component.get('kind')
                _need(kind in {'text', 'bar'}, 'Components must be editable text or fraction bar')
                rect = editor._box({'box': component.get('box')}, inventory['width_pt'], inventory['height_pt'])
                _need(rect['x'] >= box['x'] and rect['y'] >= box['y']
                      and rect['x'] + rect['width'] <= box['x'] + box['width'] + .001
                      and rect['y'] + rect['height'] <= box['y'] + box['height'] + .001,
                      'Answer component escapes its original blank')
                raw_font = component.get('font', {})
                _need(isinstance(raw_font, dict), 'Answer font must be an object')
                font, paragraph = editor._format({'font': {'color': COLOR, **raw_font},
                                                  'paragraph': {'align': 'center'}})
                if kind == 'text':
                    text = _text(component.get('text'), 'Component text')
                    joined.append(text)
                    for existing in shapes.values():
                        geometry = existing['geometry']
                        if (existing['parent_shape_id'] is not None or existing['text'] is None
                                or re.sub(r'\s', '', existing['text']) != re.sub(r'\s', '', text)
                                or 'off' not in geometry or 'ext' not in geometry):
                            continue
                        left = int(geometry['off']['x']) / editor.EMU
                        top = int(geometry['off']['y']) / editor.EMU
                        right = left + int(geometry['ext']['cx']) / editor.EMU
                        bottom = top + int(geometry['ext']['cy']) / editor.EMU
                        overlap = max(0, min(right, rect['x'] + rect['width']) - max(left, rect['x'])) * max(
                            0, min(bottom, rect['y'] + rect['height']) - max(top, rect['y']))
                        _need(overlap < rect['width'] * rect['height'] / 2,
                              'An existing answer already occupies this blank; classify it instead of adding a duplicate')
                else:
                    _need('text' not in component and rect['width'] > rect['height'],
                          'Fraction bar must be a horizontal native shape without slash text')
                    text = ''
                    joined.append('/')
                actual.append({'name': name, 'object_id': oid, 'kind': kind, 'text': text,
                               'box': rect, 'font': font, 'paragraph': paragraph, 'vertical_anchor': 'center'})
            _need(re.sub(r'\s', '', ''.join(joined)) == re.sub(r'\s', '', answer_text),
                  'Answer components must preserve the logical answer text')
            value['components'] = actual
            normalized.append(value)
        _need(sorted(clicks) == list(range(1, len(clicks) + 1)), 'Each logical answer needs one consecutive click_order')
        timing = original.find('p:timing', NS)
        if clicks and timing is not None:
            _main(timing)
        prepared.append({'page_id': page_id, 'index': index, 'part': slide['part'], 'original': original,
                         'items': normalized, 'answers': sorted((i for i in normalized if i['disposition'] == 'answer'),
                                                              key=lambda i: i['click_order'])})
    return {'source': source, 'output': output, 'inventory': inventory, 'parts': parts,
            'pages': sorted(prepared, key=lambda p: p['index'])}


def _validate_group(group, shape_ids):
    allowed = {'par', 'cTn', 'stCondLst', 'cond', 'childTnLst', 'set', 'cBhvr', 'tgtEl',
               'spTgt', 'attrNameLst', 'attrName', 'to', 'strVal'}
    _need(all(editor._local(n) in allowed for n in group.iter()), 'Unsupported answer animation behavior')
    start = group.find('p:cTn/p:stCondLst/p:cond', NS)
    _need(start is not None and dict(start.attrib) == {'delay': 'indefinite'},
          'Answer click must wait for ordinary slide advance')
    for condition in group.findall('.//p:cond', NS):
        if condition is not start:
            _need(dict(condition.attrib) == {'delay': '0'} and len(condition) == 0,
                  'Answer components must start together without extra triggers or delays')
    effects = group.findall('.//p:cTn[@presetClass]', NS)
    _need(len(effects) == len(shape_ids), 'One entrance effect required for each answer component')
    _need([n.get('spid') for n in group.findall('.//p:spTgt', NS)] == [str(s) for s in shape_ids],
          'Answer animation targets differ from its logical component group')
    for position, effect in enumerate(effects):
        _need(effect.get('presetClass') == 'entr' and effect.get('presetID') == '1'
              and effect.get('presetSubtype') == '0' and effect.get('grpId') is not None
              and effect.get('nodeType') == ('clickEffect' if position == 0 else 'withEffect'),
              'Native click animation must be appear/onClick with synchronous remaining components')
        behavior = effect.findall('.//p:set', NS)
        _need(len(behavior) == 1
              and [n.text for n in behavior[0].findall('.//p:attrName', NS)] == ['style.visibility']
              and behavior[0].find('p:to/p:strVal', NS) is not None
              and behavior[0].find('p:to/p:strVal', NS).get('val') == 'visible',
              'Answer entrance must reveal visibility and retain it')
        targets = behavior[0].findall('.//p:spTgt', NS)
        _need(len(targets) == 1 and dict(targets[0].attrib) == {'spid': str(shape_ids[position])}
              and len(targets[0]) == 0, 'Answer effect must target exactly its whole native component')
    for node in group.findall('.//p:cTn', NS):
        _need(node.get('fill') == 'hold' and node.get('dur') in (None, '1')
              and set(node.attrib) <= {'id', 'dur', 'fill', 'grpId', 'presetID', 'presetClass', 'presetSubtype', 'nodeType'},
              'Answer timing must hold visible without replay, reversal or delayed progression')
    return {str(sid): effect.get('grpId') for sid, effect in zip(shape_ids, effects)}


def _timing_check(original, actual, answers):
    previous = original.find('p:timing', NS)
    timing = actual.find('p:timing', NS)
    _need(timing is not None, 'Missing native answer timing')
    main = _main(timing)
    old_groups = list(_main(previous)) if previous is not None else []
    _need(len(main) == len(old_groups) + len(answers), 'Answer click group count differs from plan')
    ids = [n.get('id') for n in timing.findall('.//p:cTn', NS)]
    _need(None not in ids and len(set(ids)) == len(ids), 'Duplicate native timing IDs')
    new_ids, group_ids = [], {}
    for group, answer in zip(list(main)[len(old_groups):], answers):
        group_ids.update(_validate_group(group, answer['shape_ids']))
        new_ids.extend(str(i) for i in answer['shape_ids'])
    projection = deepcopy(timing)
    projected_main = _main(projection)
    for group in list(projected_main)[len(old_groups):]:
        projected_main.remove(group)
    builds = projection.find('p:bldLst', NS)
    _need(builds is not None, 'Missing native answer build list')
    actual_builds = [n for n in builds if n.get('spid') in new_ids]
    _need(sorted(n.get('spid') for n in actual_builds) == sorted(new_ids), 'Answer build targets differ from plan')
    for node in actual_builds:
        _need(editor._local(node) == 'bldP' and set(node.attrib) == {'spid', 'grpId'} and len(node) == 0,
              'Unsupported answer build behavior')
        _need(node.get('grpId') == group_ids[node.get('spid')], 'Answer build group differs from its entrance effect')
        builds.remove(node)
    if not len(builds) and (previous is None or previous.find('p:bldLst', NS) is None):
        projection.remove(builds)
    expected = previous if previous is not None else EMPTY_TIMING
    _need(editor._xml_value(projection) == editor._xml_value(expected),
          'Original timing changed or unsupported animation sequence; source retained')
    return sum(bool(g.findall(".//p:cTn[@nodeType='clickEffect']", NS)) for g in old_groups)


def _inspect(context, candidate):
    after = editor._parts(candidate)
    _need(set(after) == set(context['parts']), 'Output package parts changed')
    mapped = {p['part']: p for p in context['pages']}
    reports = []
    counts = {'answers': 0, 'open_blank': 0, 'already_visible': 0, 'ambiguous': 0}
    for part, data in context['parts'].items():
        page = mapped.get(part)
        if page is None or not page['answers']:
            _need(after[part] == data, 'Non-target ZIP part changed: ' + part)
        if page is None:
            continue
        root = editor._parse(after[part])
        original = page['original']
        nodes = editor._shape_nodes(root)
        shape_ids = [editor._identity(n).get('id') for n in nodes]
        _need(len(set(shape_ids)) == len(shape_ids), 'Duplicate output shape IDs')
        answers = []
        for item in page['answers']:
            ids = []
            for component in item['components']:
                matches = [n for n in nodes if editor._identity(n).get('name') == component['name']]
                _need(len(matches) == 1 and matches[0].getparent().tag == '{' + NS['p'] + '}spTree',
                      'Missing independent native answer component')
                node = matches[0]
                _need(editor._local(node) == 'sp' and editor._identity(node).get('hidden') not in {'1', 'true'},
                      'Answer must be an editable native shape, hidden by entrance timing only')
                transform = editor._transform(node)
                for child, fields in (('off', ('x', 'y')), ('ext', ('width', 'height'))):
                    actual_box = transform.find('a:' + child, NS) if transform is not None else None
                    _need(actual_box is not None, 'Missing answer geometry')
                    attrs = ('x', 'y') if child == 'off' else ('cx', 'cy')
                    _need(all(abs(int(actual_box.get(a, '-999')) - round(component['box'][f] * editor.EMU)) <= 1
                              for a, f in zip(attrs, fields)), 'Answer moved outside its planned original blank')
                if component['kind'] == 'text':
                    _need(editor._text(node) == component['text'], 'Answer text differs from plan')
                    editor._verify_format(node, component)
                else:
                    color = node.find('p:spPr/a:solidFill/a:srgbClr', NS)
                    geometry = node.find('p:spPr/a:prstGeom', NS)
                    _need(color is not None and color.get('val') == component['font']['color']
                          and geometry is not None and geometry.get('prst') == 'rect'
                          and not (editor._text(node) or '').strip(), 'Fraction bar must remain native and correctly colored')
                ids.append(int(editor._identity(node).get('id')))
            answers.append({'blank_id': item['blank_id'], 'answer_text': item['answer_text'],
                            'click_order': item['click_order'], 'shape_ids': ids,
                            'colors': [c['font']['color'] for c in item['components']]})
        old_clicks = (_timing_check(original, root, answers) if answers else
                      len(original.findall(".//p:cTn[@nodeType='clickEffect']", NS)))
        restored = deepcopy(root)
        for node in list(editor._shape_nodes(restored)):
            if editor._identity(node).get('name') in {c['name'] for a in page['answers'] for c in a['components']}:
                node.getparent().remove(node)
        if answers:
            changed_timing = restored.find('p:timing', NS)
            prior_timing = original.find('p:timing', NS)
            if prior_timing is None:
                restored.remove(changed_timing)
            else:
                restored.replace(changed_timing, deepcopy(prior_timing))
        _need(editor._xml_value(restored) == editor._xml_value(original),
              'Original shapes, layering or slide metadata changed')
        states = [{'click_order': 0, 'absolute_click_index': 0, 'visible_shape_ids': []}]
        visible = []
        for item in answers:
            visible.extend(item['shape_ids'])
            item['absolute_click_index'] = old_clicks + item['click_order']
            states.append({'click_order': item['click_order'], 'absolute_click_index': item['absolute_click_index'],
                           'visible_shape_ids': list(visible)})
        for item in page['items']:
            counts['answers' if item['disposition'] == 'answer' else item['disposition']] += 1
        reports.append({'page_id': page['page_id'], 'slide_index': page['index'], 'existing_click_count': old_clicks,
                        'answers': answers, 'answer_states': states,
                        'retained_blanks': [i for i in page['items'] if i['disposition'] != 'answer']})
    return {'ready_for_final': counts['ambiguous'] == 0, 'counts': counts, 'pages': reports,
            'checks': {'source_unchanged': True, 'original_shapes_preserved': True,
                       'original_timing_preserved': True, 'non_target_parts_preserved': True,
                       'native_click_structure': True}, 'playback': 'unverified'}


def _write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def _commands(context):
    commands = []
    for page in context['pages']:
        for answer in page['answers']:
            for index, component in enumerate(answer['components']):
                font = component['font']
                props = {'name': component['name'], 'geometry': 'rect', 'line': 'none',
                         **{k: str(v) + 'pt' for k, v in component['box'].items()}}
                if component['kind'] == 'bar':
                    props['fill'] = font['color']
                else:
                    props.update(text=component['text'], fill='none', font=font['family'],
                                 size=str(font['size_pt']), color=font['color'], bold=str(font['bold']).lower(),
                                 autoFit='none', align='center', valign='middle', lineSpacing='1.0x', margin='0pt,0pt,0pt,0pt')
                    props['font.ea'] = font['east_asian']
                commands.append({'command': 'add', 'parent': f"/slide[{page['index']}]", 'type': 'shape', 'props': props})
                commands.append({'command': 'add', 'parent': f"/slide[{page['index']}]/shape[@name={component['name']}]",
                                 'type': 'animation', 'props': {'effect': 'appear', 'class': 'entrance', 'duration': '1',
                                 'trigger': 'onClick' if index == 0 else 'withPrevious', 'delay': '0'}})
    return commands


def _candidate(project, context):
    work_dir = context['output'].parent / (context['output'].stem + '-work-' + uuid.uuid4().hex)
    work_dir.mkdir()
    (work_dir / 'AGENTS.md').write_text('# Retained inline answer attempt\nOfficeCLI working copy, commands, candidate and logs. '
                                      'Synthetic/test runs are not lesson approval. Preserve failed attempts; no automatic cleanup.\n',
                                      encoding='utf-8')
    work = work_dir / 'officecli-working.pptx'
    shutil.copy2(context['source'], work)
    commands = work_dir / 'commands.json'
    _write_new(commands, _commands(context))
    log = []
    try:
        log.append(editor._office(['batch', work, '--input', commands, '--json']))
    except Exception as exc:
        log.append(str(exc))
        raise
    finally:
        try:
            log.append(editor._office(['close', work]))
        finally:
            _write_new(work_dir / 'officecli-log.json', log)
    edited = editor._parts(work)
    patched = {}
    for page in context['pages']:
        if not page['answers']:
            continue
        root = deepcopy(page['original'])
        changed = editor._parse(edited[page['part']])
        for answer in page['answers']:
            for component in answer['components']:
                matches = [n for n in editor._shape_nodes(changed) if editor._identity(n).get('name') == component['name']]
                _need(len(matches) == 1, 'OfficeCLI did not create exactly one answer component')
                _need(not any(k.startswith('{' + NS['r'] + '}') for n in matches[0].iter() for k in n.attrib),
                      'Answer shape unexpectedly requires a new package relationship')
                root.find('p:cSld/p:spTree', NS).append(deepcopy(matches[0]))
        timing = changed.find('p:timing', NS)
        _need(timing is not None, 'OfficeCLI did not create native answer timing')
        previous = root.find('p:timing', NS)
        if previous is not None:
            root.replace(previous, deepcopy(timing))
        else:
            extension = root.find('p:extLst', NS)
            root.insert(root.index(extension) if extension is not None else len(root), deepcopy(timing))
        patched[page['part']] = ET.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    candidate = work_dir / 'candidate.pptx'
    with zipfile.ZipFile(context['source']) as source, zipfile.ZipFile(candidate, 'w') as target:
        for info in source.infolist():
            target.writestr(info, patched.get(info.filename, context['parts'][info.filename]))
    return candidate, state.relative_path(project, work_dir)


def _report(project, manifest, data, idempotent):
    return {**data, 'manifest': state.relative_path(project, manifest), 'manifest_sha256': editor.sha256(manifest),
            'idempotent': idempotent}


def build(project, plan):
    """Build or recover one immutable answer candidate; does not register a final artifact."""
    project = Path(project).resolve()
    context = _prepare(project, plan)
    output = context['output']
    plan_path, manifest_path = output.with_suffix('.plan.json'), output.with_suffix('.manifest.json')
    digest = editor._digest(plan)
    if plan_path.exists():
        _need(editor._digest(state.read_json(plan_path)) == digest, 'Existing plan differs; do not overwrite')
    else:
        _need(not output.exists() and not manifest_path.exists(), 'Existing output lacks its immutable plan; do not overwrite')
        output.parent.mkdir(parents=True, exist_ok=True)
        _write_new(plan_path, plan)
    if manifest_path.exists():
        return validate_final(project, state.relative_path(project, manifest_path))
    recovered = output.exists()
    work_directory = None
    if recovered:
        candidate = output
    elif any(p['answers'] for p in context['pages']):
        candidate, work_directory = _candidate(project, context)
    else:
        candidate = context['source']
    candidate_sha = editor.sha256(candidate)
    inspected = _inspect(context, candidate)
    validation = editor._office(['validate', candidate])
    _sources(project, plan)
    candidate_bytes = candidate.read_bytes()
    _need(hashlib.sha256(candidate_bytes).hexdigest() == candidate_sha, 'Candidate changed during validation')
    if not recovered:
        with output.open('xb') as handle:
            handle.write(candidate_bytes)
    data = {'schema_version': VERSION, 'plan_sha256': digest,
            'plan': {'path': state.relative_path(project, plan_path), 'sha256': editor.sha256(plan_path)},
            'source_deck': plan['source_deck'], 'source_sha256': plan['source_sha256'],
            'source_versions': plan['source_versions'], 'output': plan['output'], 'output_sha256': editor.sha256(output),
            'work_directory': work_directory, 'recovered_output': recovered,
            'officecli_validation': validation, **inspected}
    _write_new(manifest_path, data)
    return _report(project, manifest_path, data, False)


def validate_final(project, manifest):
    """Re-read plan, bound sources and actual PPTX XML; never trust a ready flag."""
    project = Path(project).resolve()
    if isinstance(manifest, dict):
        editor._known_fields(manifest, {'path', 'sha256'}, 'manifest reference')
        path = _file(project, manifest.get('path'))
        _need(editor.sha256(path) == manifest.get('sha256'), 'Manifest hash changed')
    else:
        path = _file(project, manifest)
    manifest_sha = editor.sha256(path)
    data = state.read_json(path)
    _need(data.get('schema_version') == VERSION, 'Unknown answer manifest version')
    ref = data.get('plan', {})
    plan_path = _file(project, ref.get('path'))
    _need(editor.sha256(plan_path) == ref.get('sha256'), 'Immutable plan hash changed')
    plan = state.read_json(plan_path)
    _need(editor._digest(plan) == data.get('plan_sha256'), 'Manifest plan digest differs')
    context = _prepare(project, plan)
    output = context['output']
    _need(plan_path == output.with_suffix('.plan.json') and path == output.with_suffix('.manifest.json'),
          'Manifest/plan must remain beside their immutable output')
    _need(output.is_file() and editor.sha256(output) == data.get('output_sha256'), 'Output hash changed or file missing')
    for key in ('output', 'source_deck', 'source_sha256', 'source_versions'):
        _need(data.get(key) == plan[key], 'Manifest source/output binding differs: ' + key)
    inspected = _inspect(context, output)
    for key, value in inspected.items():
        _need(data.get(key) == value, 'Manifest differs from actual verified ' + key)
    editor._office(['validate', output])
    _sources(project, plan)
    _need(editor.sha256(output) == data['output_sha256'], 'Output hash changed during final validation')
    _need(editor.sha256(plan_path) == ref['sha256'] and editor.sha256(path) == manifest_sha,
          'Immutable plan or manifest changed during final validation')
    return _report(project, path, data, True)
