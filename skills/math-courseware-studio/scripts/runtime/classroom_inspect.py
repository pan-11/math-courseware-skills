"""Read-only native timing evidence, without flattening it into a simulated show.

Paths locate nodes in the original slide XML. XML strings retain complete native
parameters; they are serialized evidence, not the original ZIP bytes. Numeric
condition delays remain local to their native nodes. No click count, effective
start time, initial visibility or playback success is inferred from this data.
"""
from . import pptx_editor as editor

NS, ET = editor.NS, editor.ET
P = '{' + NS['p'] + '}'
M = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'
ACTIONS = {'set', 'anim', 'animClr', 'animEffect', 'animMotion', 'animRot', 'animScale',
           'cmd', 'audio', 'video'}
CONDITIONS = {'stCondLst', 'endCondLst', 'prevCondLst', 'nextCondLst'}
EVENTS = {'onBegin', 'onEnd', 'begin', 'end', 'onClick', 'onDblClick', 'onMouseOver',
          'onMouseOut', 'onNext', 'onPrev', 'onStopAudio'}
NODE_TYPES = {'tmRoot', 'mainSeq', 'interactiveSeq', 'clickEffect', 'withEffect',
              'afterEffect', 'withGroup', 'afterGroup'}
# These elements are indexed or retained verbatim, not evaluated. Anything else
# is retained too, and additionally called out as unresolved.
ELEMENTS = ACTIONS | CONDITIONS | {
    'timing', 'tnLst', 'par', 'seq', 'excl', 'cTn', 'childTnLst', 'subTnLst', 'cond',
    'tn', 'rtn', 'endSync', 'iterate', 'tmAbs', 'tmPct', 'cBhvr', 'cMediaNode',
    'tgtEl', 'spTgt', 'sldTgt', 'sndTgt', 'inkTgt', 'subSp', 'bg', 'txEl', 'pRg',
    'charRg', 'graphicEl', 'dgm', 'chart', 'oleChartEl', 'attrNameLst', 'attrName',
    'tavLst', 'tav', 'val', 'strVal', 'fltVal', 'intVal', 'boolVal', 'clrVal',
    'from', 'to', 'by', 'rCtr', 'progress', 'rgb', 'hsl', 'bldLst', 'bldP',
    'bldDgm', 'bldOleChart', 'bldGraphic', 'bldSub', 'bldAsOne', 'tmplLst', 'tmpl'}


def _xml(node):
    return ET.tostring(node, encoding='unicode', with_tail=False)


def _path(node):
    return node.getroottree().getpath(node)


def _text_evidence(slide):
    result = []
    for node in editor._shape_nodes(slide):
        identity = editor._identity(node)
        if identity is None:
            continue
        sid = identity.get('id', '')
        paragraphs = []
        for index, paragraph in enumerate(node.findall('p:txBody/a:p', NS)):
            paragraphs.append({'index': index, 'path': _path(paragraph),
                               'text': ''.join('\n' if editor._local(n) == 'br' else (n.text or '')
                                               for n in paragraph.iter()
                                               if isinstance(n.tag, str) and editor._local(n) in {'t', 'br'}),
                               'xml': _xml(paragraph),
                               'math_xml': [_xml(n) for n in paragraph.iter(M + 'oMath')]})
        result.append({'shape_id': int(sid) if sid.isdecimal() else sid,
                       'path': _path(node), 'paragraphs': paragraphs})
    return result


def inspect_timing(slide):
    """Supplement legacy object inspection with lossless, explicitly partial evidence."""
    timing = slide.find('p:timing', NS)
    result = {'schema_version': 'classroom_timing_evidence_v1', 'evidence': 'readonly_xml',
              'playback': 'unverified', 'resolution': 'not_simulated',
              'xml': _xml(timing) if timing is not None else None,
              'sections': [], 'actions': [], 'unresolved': [], 'text_evidence': _text_evidence(slide),
              'text_format': 'XML text order; math_xml and paragraph XML preserve mathematical structure'}
    if timing is None:
        return result
    seen_unresolved = set()
    condition_cache = {}
    texts = {o['shape_id']: o for o in result['text_evidence']}

    def unresolved(node, reason):
        key = (_path(node), reason)
        if key not in seen_unresolved:
            seen_unresolved.add(key)
            result['unresolved'].append({'path': key[0], 'reason': reason, 'xml': _xml(node)})

    def condition(node):
        path = _path(node)
        if path in condition_cache:
            return condition_cache[path]
        raw = node.get('delay')
        kind = ('unspecified' if raw is None else 'indefinite' if raw == 'indefinite'
                else 'milliseconds' if raw.isdecimal() else 'unresolved')
        value = {'path': path, 'attributes': dict(node.attrib), 'xml': _xml(node),
                 'delay_kind': kind, 'delay_ms': int(raw) if kind == 'milliseconds' else None}
        condition_cache[path] = value
        if kind in {'unspecified', 'unresolved'}:
            unresolved(node, 'unspecified_delay' if kind == 'unspecified' else 'unsupported_delay')
        if node.get('evt') is not None and node.get('evt') not in EVENTS:
            unresolved(node, 'unsupported_event')
        return value

    def node_info(node):
        lists = []
        for child in node:
            if child.tag in {P + k for k in CONDITIONS}:
                lists.append({'kind': editor._local(child), 'path': _path(child), 'xml': _xml(child),
                              'conditions': [condition(c) for c in child if c.tag == P + 'cond']})
        return {'path': _path(node), 'type': editor._local(node), 'tag': node.tag,
                'attributes': dict(node.attrib), 'condition_lists': lists,
                'timing_modifiers': [_xml(c) for c in node if c.tag in {P + 'iterate', P + 'endSync'}]}

    def chain(node):
        ancestors = []
        for ancestor in node.iterancestors():
            if ancestor is timing:
                break
            ancestors.append(ancestor)
        return [node_info(n) for n in reversed(ancestors)]

    def target_info(node):
        data = {'path': _path(node), 'type': editor._local(node), 'attributes': dict(node.attrib),
                'xml': _xml(node), 'resolution': 'unresolved'}
        if node.tag != P + 'spTgt' or not node.get('spid', '').isdecimal():
            unresolved(node, 'unsupported_target')
            return data
        sid = int(node.get('spid'))
        data['shape_id'] = sid
        if sid not in texts:
            unresolved(node, 'missing_target_shape')
            return data
        paragraphs = texts[sid]['paragraphs']
        bounds = node.find('p:txEl/p:pRg', NS)
        if bounds is not None:
            start, end = bounds.get('st', ''), bounds.get('end', '')
            data['paragraph_range'] = {'start': int(start) if start.isdecimal() else start,
                                       'end': int(end) if end.isdecimal() else end}
            if (not start.isdecimal() or not end.isdecimal()
                    or not 0 <= int(start) <= int(end) < min(len(paragraphs), 4294967295)):
                unresolved(bounds, 'special_or_out_of_range_paragraph')
                return data
            if len(node) != 1 or len(node[0]) != 1:
                unresolved(node, 'unsupported_subtarget')
                return data
            data.update(resolution='bound_paragraphs',
                        paragraph_text=[p['text'] for p in paragraphs[int(start):int(end) + 1]])
        elif len(node):
            unresolved(node, 'unsupported_subtarget')
        else:
            data.update(resolution='bound_shape', paragraph_text=[p['text'] for p in paragraphs])
        return data

    section_nodes = []
    for node in timing.iter():
        if not isinstance(node.tag, str):
            continue
        if node.tag == P + 'cTn' and node.get('nodeType') in {'mainSeq', 'interactiveSeq'}:
            section_nodes.append((node, node.get('nodeType')))
        elif (node.tag == P + 'par' and node.getparent().tag == P + 'childTnLst'
              and node.getparent().getparent().tag == P + 'cTn'
              and node.getparent().getparent().get('nodeType') == 'tmRoot'):
            # Direct parallel nodes include native initialization; their role is
            # not inferred merely from being a sibling of a main sequence.
            section_nodes.append((node, 'tmRoot_direct_par'))
        if node.tag not in {P + k for k in ELEMENTS}:
            unresolved(node, 'unsupported_element')
        if node.tag == P + 'cond':
            condition(node)
        if node.tag == P + 'cTn' and node.get('nodeType') is not None and node.get('nodeType') not in NODE_TYPES:
            unresolved(node, 'unsupported_node_type')

    for node, kind in section_nodes:
        result['sections'].append({'kind': kind, **node_info(node), 'ancestor_chain': chain(node), 'action_paths': []})
    for node in timing.iter():
        if node.tag not in {P + k for k in ACTIONS}:
            continue
        ancestors = set(node.iterancestors())
        matches = [(s, record) for (s, _), record in zip(section_nodes, result['sections']) if s in ancestors]
        section = matches[-1][1] if matches else None
        action = {'path': _path(node), 'type': editor._local(node), 'attributes': dict(node.attrib),
                  'xml': _xml(node), 'ancestor_chain': chain(node),
                  'section_path': section['path'] if section else None,
                  'time_nodes': [node_info(n) for n in node.iter(P + 'cTn')],
                  'attribute_names': [n.text for n in node.findall('p:cBhvr/p:attrNameLst/p:attrName', NS)],
                  'targets': [target_info(t) for container in node
                              if container.tag in {P + 'cBhvr', P + 'cMediaNode'}
                              for element in container.findall('p:tgtEl', NS) for t in element]}
        result['actions'].append(action)
        for _, record in matches:
            record['action_paths'].append(action['path'])
        if section is None:
            unresolved(node, 'outside_indexed_sequence_or_root_parallel')
    return result
