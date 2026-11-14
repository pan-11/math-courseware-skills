"""Synthetic OOXML timing behavior; these checks do not certify native playback."""
from copy import deepcopy
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/math-courseware-studio/scripts'))
from runtime import pptx_editor as editor
from runtime.click_answers import EMPTY_TIMING

NS, ET = editor.NS, editor.ET


def compiler(test):
    test.assertIsNotNone(importlib.util.find_spec('runtime.classroom_timing'),
                         'Classroom effects require an actual native timing compiler')
    return importlib.import_module('runtime.classroom_timing').compile_timing


def unit(sid, visible=False, paragraph=None):
    target = {'shape_id': sid, 'expected_text': 'Synthetic text'}
    if paragraph is not None:
        target['paragraph'] = paragraph
    return {'unit_id': 'u' + str(sid), 'initial_visible': visible, 'kind': 'text', 'targets': [target]}


def action(uid, effect='appear', trigger='on_click', **kwargs):
    return {'unit_id': uid, 'effect': effect, 'trigger': trigger, **kwargs}


def step(*actions):
    return {'step_id': 'S1', 'pause_reason': 'Students explain before the next step', 'actions': list(actions)}


def main(timing):
    return timing.find(".//p:cTn[@nodeType='mainSeq']/p:childTnLst", NS)


def effects(timing):
    return main(timing).findall('.//p:cTn[@presetClass]', NS)


def start_offset(effect):
    """Resolve native parent-relative delays up to the manual click boundary."""
    total = 0
    for node in [effect, *effect.iterancestors()]:
        if node.tag != '{' + NS['p'] + '}cTn':
            continue
        cond = node.find('p:stCondLst/p:cond', NS)
        if cond is not None:
            if cond.get('delay') == 'indefinite':
                break
            total += int(cond.get('delay', '0'))
    return total


def media_timing():
    timing = deepcopy(EMPTY_TIMING)
    root_children = timing.find(".//p:cTn[@nodeType='tmRoot']/p:childTnLst", NS)
    # Reduced native media tree: preserve the interactive trigger, command and end conditions.
    root_children.append(ET.fromstring(('''<p:seq xmlns:p="''' + NS['p'] + '''" concurrent="1" nextAc="seek">
      <p:cTn id="80" nodeType="interactiveSeq" restart="whenNotActive" fill="hold">
       <p:stCondLst><p:cond evt="onClick" delay="0"><p:tgtEl><p:spTgt spid="90"/></p:tgtEl></p:cond></p:stCondLst>
       <p:childTnLst><p:cmd type="call" cmd="playFrom(0.0)"><p:cBhvr additive="base">
        <p:cTn id="81" dur="46348" fill="hold"/><p:tgtEl><p:spTgt spid="90"/></p:tgtEl>
       </p:cBhvr></p:cmd></p:childTnLst>
      </p:cTn>
     </p:seq>''').encode()))
    main(timing).append(ET.fromstring(('''<p:par xmlns:p="''' + NS['p'] + '''"><p:cTn id="82" fill="hold">
      <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst><p:childTnLst><p:par>
       <p:cTn id="83" presetClass="mediacall" presetID="2" grpId="75" nodeType="clickEffect" fill="hold">
        <p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst><p:cmd type="call" cmd="togglePause">
         <p:cBhvr><p:cTn id="84" dur="1"/><p:tgtEl><p:spTgt spid="91"/></p:tgtEl></p:cBhvr>
        </p:cmd></p:childTnLst>
       </p:cTn></p:par></p:childTnLst></p:cTn></p:par>''').encode()))
    builds = ET.SubElement(timing, '{' + NS['p'] + '}bldLst')
    ET.SubElement(builds, '{' + NS['p'] + '}bldP', spid='91', grpId='75', animBg='1')
    return timing


class ClassroomTimingTests(unittest.TestCase):
    def test_one_click_reveals_all_logical_fraction_components_together(self):
        compile_timing = compiler(self)
        fraction = unit(10)
        fraction['targets'] = [unit(n)['targets'][0] for n in (10, 11, 12)]
        original_units = deepcopy(fraction)
        timing = compile_timing(None, [step(action('fraction'))], {'fraction': fraction})
        self.assertEqual(fraction, original_units)
        self.assertEqual(len(main(timing)), 1)
        self.assertEqual([n.get('nodeType') for n in effects(timing)],
                         ['clickEffect', 'withEffect', 'withEffect'])
        self.assertEqual([start_offset(n) for n in effects(timing)], [0, 0, 0])
        self.assertEqual([n.get('spid') for n in main(timing).findall('.//p:spTgt', NS)], ['10', '11', '12'])
        self.assertEqual([n.get('val') for n in main(timing).findall('.//p:strVal', NS)], ['visible'] * 3)

    def test_after_previous_includes_duration_delay_and_with_previous_start(self):
        compile_timing = compiler(self)
        units = {str(n): unit(n) for n in range(10, 15)}
        timing = compile_timing(None, [step(
            action('10', 'fade', duration_ms=600, delay_ms=100),
            action('11', 'wipe', 'with_previous', direction='right', duration_ms=900, delay_ms=50),
            action('12', 'fade', 'after_previous', duration_ms=250, delay_ms=30),
            action('13', 'appear', 'with_previous', delay_ms=20)),
            step(action('14', 'fade'))], units)
        self.assertEqual(len(main(timing)), 2)
        self.assertEqual([start_offset(n) for n in effects(timing)], [100, 150, 1080, 1100, 0])
        self.assertEqual([n.get('nodeType') for n in effects(timing)],
                         ['clickEffect', 'withEffect', 'afterEffect', 'withEffect', 'clickEffect'])
        self.assertEqual([n.get('dur') for n in main(timing).findall('.//p:animEffect/p:cBhvr/p:cTn', NS)],
                         ['600', '900', '250', '500'])

    def test_fade_exit_hides_only_at_the_end_and_emphasis_changes_font_size(self):
        compile_timing = compiler(self)
        timing = compile_timing(None, [step(action('u', 'emphasize', scale=1.5, duration_ms=400)),
                                             step(action('u', 'fade_out', duration_ms=800))], {'u': unit(10, True)})
        emph, exit_effect = effects(timing)
        anim = emph.find('p:childTnLst/p:anim', NS)
        self.assertEqual(anim.get('to'), '1.5')
        self.assertEqual(anim.find('p:cBhvr', NS).get('override'), 'childStyle')
        self.assertEqual(anim.find('.//p:attrName', NS).text, 'style.fontSize')
        self.assertFalse(emph.findall('.//p:animScale', NS))
        self.assertEqual(exit_effect.get('presetClass'), 'exit')
        self.assertEqual(exit_effect.find('.//p:animEffect', NS).get('transition'), 'out')
        visibility = exit_effect.find('.//p:set', NS)
        self.assertEqual(visibility.find('p:to/p:strVal', NS).get('val'), 'hidden')
        self.assertEqual(visibility.find('.//p:stCondLst/p:cond', NS).get('delay'), '799')
        self.assertEqual(visibility.find('.//p:cTn', NS).get('dur'), '1')

    def test_wipe_directions_use_native_filters_without_moving_the_shape(self):
        compile_timing = compiler(self)
        for direction in ('left', 'right', 'up', 'down'):
            with self.subTest(direction=direction):
                timing = compile_timing(None, [step(action('u', 'wipe', direction=direction))], {'u': unit(10)})
                effect = effects(timing)[0]
                self.assertEqual(effect.get('presetID'), '22')
                self.assertEqual(effect.find('.//p:animEffect', NS).get('filter'), 'wipe(' + direction + ')')
                self.assertFalse(effect.findall('.//p:anim', NS))

    def test_paragraphs_have_exact_ranges_and_a_shared_build_for_first_pass(self):
        compile_timing = compiler(self)
        units = {'p0': unit(10, False, 0), 'p2': unit(10, False, 2)}
        timing = compile_timing(None, [step(action('p0', 'fade')), step(action('p2', 'fade'))], units)
        for effect, expected in zip(effects(timing), ('0', '2')):
            targets = effect.findall('.//p:spTgt', NS)
            self.assertEqual(len(targets), 2)
            for target in targets:
                self.assertEqual(target.get('spid'), '10')
                self.assertEqual(dict(target.find('p:txEl/p:pRg', NS).attrib), {'st': expected, 'end': expected})
        builds = timing.findall('p:bldLst/p:bldP', NS)
        self.assertEqual(len(builds), 1)
        self.assertEqual(builds[0].get('build'), 'p')
        self.assertEqual(builds[0].get('animBg'), '0')
        self.assertEqual({e.get('grpId') for e in effects(timing)}, {builds[0].get('grpId')})

    def test_initial_state_is_explicit_for_reentry_and_independent_paragraphs(self):
        compile_timing = compiler(self)
        units = {'visible': unit(10, True, 0), 'hidden': unit(10, False, 1)}
        timing = compile_timing(None, [step(action('visible', 'disappear'),
                                              action('hidden', 'appear', 'with_previous')),
                                             step(action('visible', 'appear'),
                                              action('hidden', 'disappear', 'with_previous'))], units)
        root_children = timing.find(".//p:cTn[@nodeType='tmRoot']/p:childTnLst", NS)
        initial_sets = []
        for child in root_children:
            if child.find("p:cTn[@nodeType='mainSeq']", NS) is None:
                initial_sets.extend(child.findall('.//p:set', NS))
        observed = {node.find('.//p:pRg', NS).get('st'): node.find('p:to/p:strVal', NS).get('val')
                    for node in initial_sets}
        self.assertEqual(observed, {'0': 'visible', '1': 'hidden'})
        self.assertEqual(len(main(timing)), 2)
        self.assertEqual(len(main(timing).findall(".//p:cTn[@nodeType='clickEffect']", NS)), 2)

    def test_whole_group_target_is_not_expanded_to_its_children(self):
        compile_timing = compiler(self)
        group = unit(10)
        group['kind'] = 'group'
        group['targets'][0]['expected_text'] = None
        timing = compile_timing(None, [step(action('group'))], {'group': group})
        target = effects(timing)[0].find('.//p:spTgt', NS)
        self.assertEqual(dict(target.attrib), {'spid': '10'})
        self.assertEqual(len(target), 0)

    def test_original_main_interactive_media_and_builds_are_preserved(self):
        compile_timing = compiler(self)
        original = media_timing()
        original_bytes = ET.tostring(original)
        timing = compile_timing(original, [step(action('u'))], {'u': unit(10)})
        self.assertEqual(ET.tostring(original), original_bytes)
        self.assertIsNot(timing, original)
        self.assertEqual(editor._xml_value(main(timing)[0]), editor._xml_value(main(original)[0]))
        query = ".//p:cTn[@nodeType='interactiveSeq']"
        self.assertEqual(editor._xml_value(timing.find(query, NS)), editor._xml_value(original.find(query, NS)))
        self.assertEqual(editor._xml_value(timing.find('p:bldLst', NS)[0]),
                         editor._xml_value(original.find('p:bldLst', NS)[0]))
        ids = [int(n.get('id')) for n in timing.findall('.//p:cTn', NS)]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreater(int(effects(timing)[-1].get('grpId')), 75)
        self.assertGreater(int(effects(timing)[-1].get('id')), 84)

    def test_interactive_only_timing_receives_new_main_sequence_without_replacement(self):
        compile_timing = compiler(self)
        original = media_timing()
        children = original.find(".//p:cTn[@nodeType='tmRoot']/p:childTnLst", NS)
        children.remove(children[0])
        timing = compile_timing(original, [step(action('u'))], {'u': unit(10)})
        self.assertEqual(len(main(timing)), 1)
        self.assertEqual(editor._xml_value(timing.find(".//p:cTn[@nodeType='interactiveSeq']", NS)),
                         editor._xml_value(original.find(".//p:cTn[@nodeType='interactiveSeq']", NS)))

    def test_no_steps_returns_an_independent_unchanged_tree(self):
        compile_timing = compiler(self)
        original = media_timing()
        timing = compile_timing(original, [], {'u': unit(10, True)})
        self.assertIsNot(timing, original)
        self.assertEqual(ET.tostring(timing), ET.tostring(original))

    def test_repeated_transitions_use_distinct_build_groups_and_deterministic_output(self):
        compile_timing = compiler(self)
        steps = [step(action('u')), step(action('u', 'disappear')), step(action('u', 'fade'))]
        units = {'u': unit(10)}
        timing = compile_timing(None, steps, units)
        self.assertEqual(ET.tostring(timing), ET.tostring(compile_timing(None, steps, units)))
        groups = [e.get('grpId') for e in effects(timing)]
        self.assertEqual(len(set(groups)), 3)
        self.assertEqual([b.get('grpId') for b in timing.findall('p:bldLst/p:bldP', NS)], groups)

    def test_unsupported_effect_trigger_duration_or_target_fails_before_mutation(self):
        compile_timing = compiler(self)
        cases = [action('u', 'spin'), action('u', trigger='after_previous'), action('missing'),
                 action('u', duration_ms=True), action('u', duration_ms=0), action('u', duration_ms=5001),
                 action('u', delay_ms=2001), action('u', delay_ms=-1), action('u', 'wipe'),
                 action('u', 'wipe', direction='diagonal'), action('u', 'emphasize', scale=float('nan')),
                 action('u', 'emphasize', scale=3), action('u', unexpected=True)]
        original = media_timing()
        before = ET.tostring(original)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                compile_timing(original, [step(value)], {'u': unit(10)})
            self.assertEqual(ET.tostring(original), before)
        for target in ({'shape_id': True}, {'shape_id': 0}, {'shape_id': 10, 'paragraph': -1},
                       {'shape_id': 10, 'paragraph': True}):
            invalid = unit(10)
            invalid['targets'] = [target]
            with self.subTest(target=target), self.assertRaises(ValueError):
                compile_timing(original, [step(action('u'))], {'u': invalid})
        for steps in ([step()], [step(action('u'), action('u'))]):
            with self.assertRaises(ValueError):
                compile_timing(original, steps, {'u': unit(10)})

    def test_duplicate_native_ids_and_ambiguous_existing_main_sequence_are_rejected(self):
        compile_timing = compiler(self)
        original = media_timing()
        original.find(".//p:cTn[@id='84']", NS).set('id', '83')
        with self.assertRaisesRegex(ValueError, 'ID|id'):
            compile_timing(original, [step(action('u'))], {'u': unit(10)})
        original = media_timing()
        children = original.find(".//p:cTn[@nodeType='tmRoot']/p:childTnLst", NS)
        children.append(deepcopy(children[0]))
        with self.assertRaises(ValueError):
            compile_timing(original, [step(action('u'))], {'u': unit(10)})


if __name__ == '__main__':
    unittest.main()
