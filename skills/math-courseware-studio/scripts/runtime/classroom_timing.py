"""Compile checked classroom steps to a new native PresentationML timing tree.

The native appear/fade/exit/font-size behavior follows retained Office-authored
OOXML samples; paragraph builds and style.fontSize match Microsoft's Open XML
documentation. Start delays are parent-relative: afterEffect alone does not wait
for a previous sibling. The calling planner owns source/target/state validation.
This module never opens a deck and does not certify PowerPoint/WPS playback.
"""
from copy import deepcopy
import math

from . import pptx_editor as editor
from .click_answers import EMPTY_TIMING

NS, ET = editor.NS, editor.ET
P = '{' + NS['p'] + '}'
EFFECTS = {'appear', 'fade', 'wipe', 'disappear', 'fade_out', 'emphasize'}
TRIGGERS = {'on_click': 'clickEffect', 'with_previous': 'withEffect', 'after_previous': 'afterEffect'}
# Wipe subtypes describe the revealed edge, whereas the filter names its motion.
WIPE_SUBTYPES = {'left': '2', 'right': '8', 'up': '1', 'down': '4'}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _node(parent, name, **attributes):
    return ET.SubElement(parent, P + name, {key: str(value) for key, value in attributes.items()})


def _start(node, delay):
    _node(_node(node, 'stCondLst'), 'cond', delay=delay)


def _child_list(node):
    children = node.find('p:childTnLst', NS)
    if children is None:
        children = ET.Element(P + 'childTnLst')
        following = node.find('p:subTnLst', NS)
        node.insert(node.index(following) if following is not None else len(node), children)
    return children


def _target(behavior, target):
    shape = _node(_node(behavior, 'tgtEl'), 'spTgt', spid=target['shape_id'])
    if 'paragraph' in target:
        _node(_node(shape, 'txEl'), 'pRg', st=target['paragraph'], end=target['paragraph'])


def _checked(steps, units):
    _need(isinstance(steps, list) and isinstance(units, dict), 'Steps and units must be a list and mapping')
    normalized = []
    for step_index, step in enumerate(steps):
        _need(isinstance(step, dict), 'Step must be an object')
        editor._known_fields(step, {'step_id', 'pause_reason', 'actions'}, 'classroom step')
        label = str(step.get('step_id', step_index + 1))
        actions = step.get('actions')
        _need(isinstance(actions, list) and bool(actions), label + ': empty click is unsupported')
        checked_actions = []
        previous_start, previous_duration = 0, 0
        for index, action in enumerate(actions):
            _need(isinstance(action, dict), label + ': action must be an object')
            editor._known_fields(action, {'unit_id', 'effect', 'trigger', 'duration_ms', 'delay_ms',
                                          'direction', 'scale'}, label + ' action')
            uid = action.get('unit_id')
            _need(isinstance(uid, str) and uid in units, label + ': unknown unit')
            unit = units[uid]
            _need(isinstance(unit, dict) and type(unit.get('initial_visible')) is bool,
                  label + ': explicit unit initial_visible required')
            targets = unit.get('targets')
            _need(isinstance(targets, list) and bool(targets), label + ': nonempty targets required')
            seen = set()
            for target in targets:
                _need(isinstance(target, dict), label + ': target must be an object')
                editor._known_fields(target, {'shape_id', 'expected_text', 'paragraph'}, label + ' target')
                sid, paragraph = target.get('shape_id'), target.get('paragraph')
                _need(type(sid) is int and 0 < sid <= 4294967295, label + ': invalid shape ID')
                _need('paragraph' not in target or type(paragraph) is int and 0 <= paragraph < 4294967295,
                      label + ': invalid paragraph index')
                key = (sid, paragraph)
                _need(key not in seen, label + ': duplicate unit target')
                seen.add(key)
            effect = action.get('effect')
            trigger = action.get('trigger')
            _need(isinstance(effect, str) and effect in EFFECTS, label + ': unsupported effect')
            _need(isinstance(trigger, str) and trigger in TRIGGERS, label + ': unsupported trigger')
            _need((trigger == 'on_click') == (index == 0),
                  label + ': exactly the first action must use on_click')
            duration = action.get('duration_ms', 1 if effect in {'appear', 'disappear'} else 500)
            delay = action.get('delay_ms', 0)
            _need(type(duration) is int and 1 <= duration <= 5000, label + ': invalid duration_ms')
            _need(type(delay) is int and 0 <= delay <= 2000, label + ': invalid delay_ms')
            if effect == 'wipe':
                _need(isinstance(action.get('direction'), str) and action['direction'] in WIPE_SUBTYPES,
                      label + ': wipe direction must be left/right/up/down')
            else:
                _need('direction' not in action, label + ': direction is only supported for wipe')
            if effect == 'emphasize':
                scale = action.get('scale', 1.25)
                _need(type(scale) in {int, float} and math.isfinite(scale) and 1 < scale <= 2,
                      label + ': invalid font scale')
            else:
                _need('scale' not in action, label + ': scale is only supported for emphasize')
            start = delay if trigger == 'on_click' else previous_start + delay
            if trigger == 'after_previous':
                start += previous_duration
            checked_actions.append({**action, 'duration_ms': duration, 'start_ms': start})
            previous_start, previous_duration = start, duration
        normalized.append(checked_actions)
    return normalized


class _Compiler:
    def __init__(self, timing):
        self.timing = timing
        ids = [n.get('id') for n in timing.findall('.//p:cTn', NS)]
        _need(all(v is not None and v.isdecimal() and 0 <= int(v) <= 4294967295 for v in ids),
              'Unsupported existing timing ID')
        _need(len({int(v) for v in ids}) == len(ids), 'Duplicate existing timing IDs')
        groups = [n.get('grpId') for n in timing.iter() if n.get('grpId') is not None]
        _need(all(v.isdecimal() and 0 <= int(v) <= 4294967295 for v in groups),
              'Unsupported existing build group ID')
        self.next_id = max([int(v) for v in ids], default=0) + 1
        self.next_group = max([int(v) for v in groups], default=-1) + 1
        self.build_ids = {}
        self.target_passes = {}
        roots = timing.findall(".//p:cTn[@nodeType='tmRoot']", NS)
        _need(len(roots) <= 1, 'Unsupported multiple timing roots')
        if not roots:
            _need(not ids, 'Existing timing lacks its native root; preserve it for explicit repair')
            time_list = timing.find('p:tnLst', NS)
            if time_list is None:
                time_list = ET.Element(P + 'tnLst')
                timing.insert(0, time_list)
            _need(len(time_list) == 0, 'Unsupported existing timing without root')
            root = self._ctn(_node(time_list, 'par'), dur='indefinite', restart='never', nodeType='tmRoot')
        else:
            root = roots[0]
        self.root_children = _child_list(root)
        main_nodes = timing.findall(".//p:cTn[@nodeType='mainSeq']", NS)
        _need(len(main_nodes) <= 1, 'Unsupported multiple main sequences')
        if main_nodes:
            main_node = main_nodes[0]
            _need(main_node.getparent().tag == P + 'seq'
                  and main_node.getparent().getparent() is self.root_children,
                  'Unsupported main sequence nesting')
        else:
            sequence = _node(self.root_children, 'seq', concurrent='1', nextAc='seek')
            main_node = self._ctn(sequence, dur='indefinite', nodeType='mainSeq')
            for name, event in [('prevCondLst', 'onPrev'), ('nextCondLst', 'onNext')]:
                condition = _node(_node(sequence, name), 'cond', evt=event, delay='0')
                _node(_node(condition, 'tgtEl'), 'sldTgt')
        self.main = _child_list(main_node)

    def _ctn(self, parent, **attributes):
        _need(self.next_id <= 4294967295, 'Native timing ID space exhausted')
        node = _node(parent, 'cTn', id=self.next_id, **attributes)
        self.next_id += 1
        return node

    def _behavior(self, parent, target, duration, delay=None, hold=False, **attributes):
        behavior = _node(parent, 'cBhvr', **attributes)
        time = self._ctn(behavior, dur=duration, **({'fill': 'hold'} if hold else {}))
        if delay is not None:
            _start(time, delay)
        _target(behavior, target)
        return behavior

    def _visibility(self, parent, target, visible, duration=1, delay=0):
        setting = _node(parent, 'set')
        behavior = self._behavior(setting, target, duration, delay, hold=True)
        _node(_node(behavior, 'attrNameLst'), 'attrName').text = 'style.visibility'
        _node(_node(setting, 'to'), 'strVal', val='visible' if visible else 'hidden')

    def initialize(self, units, used):
        # A later entrance must not override an explicitly visible initial state.
        # This auto-starting sibling has no preset/nodeType click and no build.
        initial = self._ctn(_node(self.root_children, 'par'), fill='hold')
        _start(initial, 0)
        children = _node(initial, 'childTnLst')
        for uid in used:
            for target in units[uid]['targets']:
                self._visibility(children, target, units[uid]['initial_visible'])

    def _build(self, target):
        sid = target['shape_id']
        target_key = (sid, target.get('paragraph'))
        ordinal = self.target_passes.get(target_key, 0)
        self.target_passes[target_key] = ordinal + 1
        # Paragraphs' first effects share a build; subsequent exit/re-entry passes
        # receive new groups rather than rewriting a previous paragraph build.
        build_key = (sid, ordinal)
        if build_key not in self.build_ids:
            _need(self.next_group <= 4294967295, 'Native build group ID space exhausted')
            group = self.next_group
            self.next_group += 1
            self.build_ids[build_key] = group
            builds = self.timing.find('p:bldLst', NS)
            if builds is None:
                builds = ET.Element(P + 'bldLst')
                extension = self.timing.find('p:extLst', NS)
                self.timing.insert(self.timing.index(extension) if extension is not None else len(self.timing), builds)
            attributes = {'build': 'p', 'animBg': '0'} if 'paragraph' in target else {}
            _node(builds, 'bldP', spid=sid, grpId=group, **attributes)
        return self.build_ids[build_key]

    def effect(self, parent, action, target, target_index):
        effect, duration = action['effect'], action['duration_ms']
        category = 'exit' if effect in {'disappear', 'fade_out'} else ('emph' if effect == 'emphasize' else 'entr')
        preset = {'appear': '1', 'disappear': '1', 'fade': '10', 'fade_out': '10', 'wipe': '22', 'emphasize': '4'}[effect]
        subtype = WIPE_SUBTYPES[action['direction']] if effect == 'wipe' else ('2' if effect == 'emphasize' else '0')
        node = self._ctn(_node(parent, 'par'), presetID=preset, presetClass=category,
                         presetSubtype=subtype, fill='hold', grpId=self._build(target),
                         nodeType=TRIGGERS[action['trigger']] if target_index == 0 else 'withEffect')
        _start(node, action['start_ms'])
        children = _node(node, 'childTnLst')
        if effect in {'appear', 'disappear'}:
            self._visibility(children, target, effect == 'appear', duration)
        elif effect == 'emphasize':
            animation = _node(children, 'anim', to=format(action.get('scale', 1.25), '.15g'),
                              calcmode='lin', valueType='num')
            behavior = self._behavior(animation, target, duration, hold=True, override='childStyle')
            _node(_node(behavior, 'attrNameLst'), 'attrName').text = 'style.fontSize'
        else:
            if category == 'entr':
                self._visibility(children, target, True)
            animation = _node(children, 'animEffect', transition='out' if category == 'exit' else 'in',
                              filter='wipe(' + action['direction'] + ')' if effect == 'wipe' else 'fade')
            self._behavior(animation, target, duration)
            if category == 'exit':
                # Native exit samples persist hidden at the final millisecond.
                self._visibility(children, target, False, delay=duration - 1)

    def add_step(self, actions, units):
        click = self._ctn(_node(self.main, 'par'), fill='hold')
        _start(click, 'indefinite')
        simultaneous = self._ctn(_node(_node(click, 'childTnLst'), 'par'), fill='hold')
        _start(simultaneous, 0)
        children = _node(simultaneous, 'childTnLst')
        for action in actions:
            for target_index, target in enumerate(units[action['unit_id']]['targets']):
                self.effect(children, action, target, target_index)


def compile_timing(original_timing, steps, units):
    """Return an independent timing tree, preserving all pre-existing sequences.

    Inputs are already semantically checked against their slide by the planner.
    on_click creates one manual boundary; with_previous is relative to the prior
    action's start, after_previous to its end. All targets of one unit are parallel.
    """
    actions = _checked(steps, units)
    _need(original_timing is None or isinstance(original_timing, ET._Element)
          and original_timing.tag == P + 'timing', 'Expected a native p:timing element')
    timing = deepcopy(original_timing if original_timing is not None else EMPTY_TIMING)
    if not actions:
        return timing
    compiler = _Compiler(timing)
    used = list(dict.fromkeys(action['unit_id'] for group in actions for action in group))
    compiler.initialize(units, used)
    for group in actions:
        compiler.add_step(group, units)
    return timing
