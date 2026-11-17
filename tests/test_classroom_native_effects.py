"""Native behavior checks from target-copy examples, not slideshow verification."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/math-courseware-studio/scripts'))
from runtime import classroom_animation as animation, classroom_timing as timing
from test_classroom_timing import unit, action, step, effects, NS
from test_classroom_animation import fixture, action as plan_action, step as plan_step


class ClassroomNativeEffectTests(unittest.TestCase):
    def test_peek_moves_from_the_reveal_edge_and_clips_to_original_position(self):
        cases = {'down': ('1', 'ppt_y', '#ppt_y-#ppt_h*1.125000'),
                 'right': ('8', 'ppt_x', '#ppt_x-#ppt_w*1.125000'),
                 'up': ('4', 'ppt_y', '#ppt_y+#ppt_h*1.125000'),
                 'left': ('2', 'ppt_x', '#ppt_x+#ppt_w*1.125000')}
        for direction, (subtype, prop, start) in cases.items():
            with self.subTest(direction=direction):
                tree = timing.compile_timing(None, [step(action('u', 'peek', direction=direction, duration_ms=700))], {'u': unit(10)})
                effect = effects(tree)[0]
                self.assertEqual((effect.get('presetID'), effect.get('presetSubtype')), ('12', subtype))
                moving = effect.find('.//p:anim', NS)
                self.assertEqual(moving.find('.//p:attrName', NS).text, prop)
                self.assertEqual([n.get('val') for n in moving.findall('p:tavLst/p:tav/p:val/p:strVal', NS)], [start, '#' + prop])
                self.assertEqual(moving.find('p:cBhvr', NS).get('additive'), 'base')
                self.assertEqual(moving.find('p:cBhvr/p:cTn', NS).get('dur'), '700')
                self.assertEqual(effect.find('.//p:animEffect', NS).get('filter'), 'wipe(' + direction + ')')

    def test_horizontal_stretch_changes_width_but_keeps_height(self):
        tree = timing.compile_timing(None, [step(action('u', 'stretch', orientation='horizontal'))], {'u': unit(10)})
        effect = effects(tree)[0]
        self.assertEqual((effect.get('presetID'), effect.get('presetSubtype')), ('17', '10'))
        animations = {n.find('.//p:attrName', NS).text: n for n in effect.findall('.//p:anim', NS)}
        self.assertEqual(set(animations), {'ppt_w', 'ppt_h'})
        width = animations['ppt_w']
        self.assertEqual(width.find('p:tavLst/p:tav/p:val/p:fltVal', NS).get('val'), '0')
        self.assertEqual(width.findall('p:tavLst/p:tav', NS)[1].find('p:val/p:strVal', NS).get('val'), '#ppt_w')
        self.assertEqual([n.get('val') for n in animations['ppt_h'].findall('p:tavLst/p:tav/p:val/p:strVal', NS)], ['#ppt_h', '#ppt_h'])
        self.assertFalse(effect.findall('.//p:animEffect', NS))

    def test_random_bars_and_wheel_keep_their_actual_filters(self):
        for name, extra, preset, subtype, filter_ in [
                ('random_bars', {'orientation': 'horizontal'}, '14', '10', 'randombar(horizontal)'),
                ('wheel', {'spokes': 1}, '21', '1', 'wheel(1)')]:
            with self.subTest(effect=name):
                tree = timing.compile_timing(None, [step(action('u', name, duration_ms=800, **extra))], {'u': unit(10)})
                effect = effects(tree)[0]
                self.assertEqual((effect.get('presetID'), effect.get('presetSubtype')), (preset, subtype))
                self.assertEqual(effect.find('.//p:animEffect', NS).get('filter'), filter_)
                self.assertEqual(effect.find('.//p:animEffect/p:cBhvr/p:cTn', NS).get('dur'), '800')
                if name == 'wheel':
                    self.assertEqual(effect.find('.//p:set/p:cBhvr/p:cTn', NS).get('dur'), '800')

    def test_wheel_can_keep_short_visibility_set_and_long_motion_from_native_reference(self):
        root, plan = fixture()
        plan['pages'][0]['steps'][0]['actions'] = [plan_action('feature1', 'wheel', spokes=1,
            duration_ms=2000, visibility_duration_ms=1)]
        result = animation.build(root, plan)
        parts = animation.editor._parts(root / result['output'])
        slide = animation.editor.ET.fromstring(parts[animation.editor._slides(parts)[0]])
        effect = slide.find(".//p:cTn[@presetID='21']", NS)
        self.assertEqual(effect.find('.//p:set/p:cBhvr/p:cTn', NS).get('dur'), '1')
        self.assertEqual(effect.find('.//p:animEffect/p:cBhvr/p:cTn', NS).get('dur'), '2000')
        self.assertEqual(result['playback'], 'unverified')

    def test_extended_effects_are_checked_by_the_plan_and_source_remains_unchanged(self):
        for name, extra in [('peek', {'direction': 'down'}), ('stretch', {'orientation': 'horizontal'}),
                            ('random_bars', {'orientation': 'horizontal'}), ('wheel', {'spokes': 1})]:
            root, plan = fixture()
            original = (root / plan['source_deck']).read_bytes()
            plan['pages'][0]['steps'][0]['actions'] = [plan_action('feature1', name, **extra)]
            result = animation.build(root, plan)
            self.assertEqual(result['playback'], 'unverified')
            self.assertEqual((root / plan['source_deck']).read_bytes(), original)

    def test_unobserved_variants_and_cross_effect_fields_fail_closed(self):
        cases = [('stretch', {'orientation': 'diagonal'}), ('random_bars', {'orientation': 'vertical'}),
                 ('wheel', {'spokes': 3}), ('fade', {'spokes': 1}), ('peek', {'direction': 'center'}),
                 ('wipe', {'direction': 'up', 'orientation': 'horizontal'}),
                 ('fade', {'visibility_duration_ms': 1}),
                 ('wheel', {'spokes': 1, 'visibility_duration_ms': 0}),
                 ('wheel', {'spokes': 1, 'visibility_duration_ms': 501}),
                 ('wheel', {'spokes': 1, 'visibility_duration_ms': True})]
        for name, extra in cases:
            with self.subTest(effect=name, extra=extra), self.assertRaises(ValueError):
                timing.compile_timing(None, [step(action('u', name, **extra))], {'u': unit(10)})
            root, plan = fixture()
            plan['pages'][0]['steps'][0]['actions'] = [plan_action('feature1', name, **extra)]
            with self.subTest(plan_effect=name, extra=extra), self.assertRaises(ValueError):
                animation.check(root, plan)


class ClassroomReplayTests(unittest.TestCase):
    def test_repeated_entrance_still_requires_explicit_replay(self):
        root, plan = fixture()
        plan['pages'][0]['steps'].append(plan_step('repeat', plan_action('feature1', 'fade')))
        with self.assertRaisesRegex(ValueError, 'repeated entrance'):
            animation.check(root, plan)
        with self.assertRaisesRegex(ValueError, 'repeated entrance'):
            timing.compile_timing(None, [step(action('u')), step(action('u', 'fade'))], {'u': unit(10)})

    def test_explicit_replay_preserves_both_clicks_and_builds_without_synthetic_exit(self):
        root, plan = fixture()
        page = plan['pages'][0]
        page['units'] = page['units'][:1]
        page['steps'] = [plan_step('first', plan_action('feature1', 'fade')),
                         plan_step('again', plan_action('feature1', 'fade', replay=True))]
        original = (root / plan['source_deck']).read_bytes()
        result = animation.build(root, plan)
        self.assertEqual(result['playback'], 'unverified')
        self.assertEqual([s['visible_units'] for s in result['pages'][0]['states']],
                         [[], ['feature1'], ['feature1']])
        parts = animation.editor._parts(root / result['output'])
        slide = animation.editor.ET.fromstring(parts[animation.editor._slides(parts)[0]])
        tree = slide.find('p:timing', NS)
        nodes = effects(tree)
        self.assertEqual([(n.get('presetClass'), n.get('nodeType')) for n in nodes],
                         [('entr', 'clickEffect'), ('entr', 'clickEffect')])
        groups = [n.get('grpId') for n in nodes]
        self.assertEqual(len(set(groups)), 2)
        self.assertEqual([n.get('grpId') for n in tree.findall('p:bldLst/p:bldP', NS)], groups)
        self.assertEqual((root / plan['source_deck']).read_bytes(), original)
        self.assertTrue(animation.validate_final(root, {'path': result['manifest'],
                                                       'sha256': result['manifest_sha256']})['idempotent'])

    def test_replay_flag_cannot_bypass_initial_state_or_other_action_rules(self):
        cases = [
            (False, [], action('u', replay=True)),
            (True, [], action('u', replay=True)),
            (False, [action('u')], action('u', 'disappear', replay=True)),
            (False, [action('u')], action('u', 'emphasize', replay=True)),
            (False, [action('u')], action('u', replay=False)),
            (False, [action('u')], action('u', replay=1)),
            (False, [action('u')], action('u', replay='true')),
            (False, [action('u'), action('u', 'disappear')], action('u', replay=True)),
            (True, [action('u', 'disappear'), action('u')], action('u', replay=True)),
        ]
        for visible, before, last in cases:
            with self.subTest(visible=visible, before=before, last=last):
                actions = before + [last]
                with self.assertRaisesRegex(ValueError, 'replay'):
                    timing.compile_timing(None, [step(a) for a in actions], {'u': unit(10, visible)})
                root, plan = fixture()
                page = plan['pages'][0]
                page['units'] = page['units'][:1]
                page['units'][0]['initial_visible'] = visible
                page['steps'] = [plan_step('s' + str(i), {**a, 'unit_id': 'feature1'})
                                 for i, a in enumerate(actions)]
                with self.assertRaisesRegex(ValueError, 'replay'):
                    animation.check(root, plan)


class ClassroomPhaseTests(unittest.TestCase):
    def test_explicit_phase_is_bound_through_full_plan_and_rejects_invalid_anchors(self):
        for phase, trigger, valid in [(500, 'after_previous', True), (0, 'after_previous', True),
                                      (-1, 'after_previous', False), (True, 'after_previous', False),
                                      (921, 'after_previous', False), (0, 'with_previous', False)]:
            with self.subTest(phase=phase, trigger=trigger):
                root, plan = fixture()
                page = plan['pages'][0]
                page['units'] = page['units'][:2]
                page['steps'] = [plan_step('phase', plan_action('feature1', 'fade'),
                    plan_action('feature2', 'appear', trigger, delay_ms=420, phase_start_ms=phase))]
                if not valid:
                    with self.assertRaisesRegex(ValueError, 'phase_start_ms'):
                        animation.check(root, plan)
                    with self.assertRaisesRegex(ValueError, 'phase_start_ms'):
                        timing.compile_timing(None, page['steps'], {u['unit_id']: u for u in page['units']})
                    continue
                result = animation.build(root, plan)
                parts = animation.editor._parts(root / result['output'])
                slide = animation.editor.ET.fromstring(parts[animation.editor._slides(parts)[0]])
                tree = slide.find('p:timing', NS)
                nodes = effects(tree)
                self.assertEqual(nodes[-1].find('p:stCondLst/p:cond', NS).get('delay'), str(920-phase))
                phases = tree.find(".//p:cTn[@nodeType='mainSeq']/p:childTnLst", NS)[0].findall(
                    'p:cTn/p:childTnLst/p:par/p:cTn', NS)
                self.assertEqual(phases[1].find('p:stCondLst/p:cond', NS).get('delay'), str(phase))
                self.assertEqual(result['playback'], 'unverified')
        root, plan = fixture()
        plan['pages'][0]['steps'][0]['actions'][0]['phase_start_ms'] = 0
        with self.assertRaisesRegex(ValueError, 'phase_start_ms'):
            animation.check(root, plan)


if __name__ == '__main__':
    unittest.main()
