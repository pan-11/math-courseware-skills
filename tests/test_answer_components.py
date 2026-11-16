"""Retained component-only PPTX checks; not native slideshow acceptance."""
import copy
import unittest

from pptx import Presentation

from test_click_answers import answer, fixture, non_answer, rewrite_slide, slide
from runtime import click_answers, pptx_editor as editor, state


def component_fixture():
    root, plan = fixture()
    plan['mode'] = 'components_only'
    plan['output'] = 'editable/output/components.pptx'
    return root, plan


def bind_source(root, plan):
    plan['source_sha256'] = plan['source_versions'][plan['source_deck']] = editor.sha256(root / plan['source_deck'])


def refresh_output_hash(root, report):
    path = root / report['manifest']
    data = state.read_json(path)
    data['output_sha256'] = editor.sha256(root / report['output'])
    state.write_json(path, data)


def existing_timing(rootxml):
    from runtime.classroom_timing import compile_timing
    title = next(n for n in editor._shape_nodes(rootxml) if editor._identity(n).get('name') == 'existing-title')
    sid = int(editor._identity(title).get('id'))
    timing = compile_timing(None, [{'step_id': 'old', 'actions': [
        {'unit_id': 'title', 'effect': 'appear', 'trigger': 'on_click', 'duration_ms': 1, 'delay_ms': 0}]}],
        {'title': {'initial_visible': False, 'targets': [{'shape_id': sid}]}})
    children = timing.find(".//p:cTn[@nodeType='tmRoot']/p:childTnLst", editor.NS)
    sequence = editor.ET.SubElement(children, '{' + editor.NS['p'] + '}seq', concurrent='1')
    clock = editor.ET.SubElement(sequence, '{' + editor.NS['p'] + '}cTn', id='900',
                                nodeType='interactiveSeq', dur='indefinite')
    condition_list = editor.ET.SubElement(clock, '{' + editor.NS['p'] + '}stCondLst')
    condition = editor.ET.SubElement(condition_list, '{' + editor.NS['p'] + '}cond', evt='onClick', delay='0')
    target = editor.ET.SubElement(condition, '{' + editor.NS['p'] + '}tgtEl')
    editor.ET.SubElement(target, '{' + editor.NS['p'] + '}spTgt', spid=str(sid))
    child_list = editor.ET.SubElement(clock, '{' + editor.NS['p'] + '}childTnLst')
    editor.ET.SubElement(child_list, '{' + editor.NS['p'] + '}par').append(
        editor.ET.Element('{' + editor.NS['p'] + '}cTn', id='901', dur='1'))
    rootxml.append(timing)


class AnswerComponentTests(unittest.TestCase):
    def build_components(self, root, plan):
        try:
            return click_answers.build(root, plan)
        except ValueError as exc:
            self.fail('A valid components-only plan must build without answer timing: ' + str(exc))

    def test_components_without_click_orders_preserve_source_and_return_bound_objects(self):
        root, plan = component_fixture()
        plan['pages'][0]['items'] = [answer(), answer('Q2', 2, True)]
        for item in plan['pages'][0]['items']:
            item.pop('click_order')
        source = root / plan['source_deck']
        before = source.read_bytes()
        report = self.build_components(root, plan)
        self.assertFalse(report['ready_for_final'])
        self.assertTrue(report['ready_for_animation'])
        self.assertEqual(report['mode'], 'components_only')
        self.assertEqual(report['mapping'], plan['mapping'])
        self.assertNotIn('native_click_structure', report['checks'])
        self.assertNotIn('answer_states', report['pages'][0])
        self.assertEqual(source.read_bytes(), before)
        self.assertIsNone(slide(root / report['output']).find('p:timing', editor.NS))
        checked = click_answers.validate_components(root, {'path': report['manifest'], 'sha256': report['manifest_sha256']})
        self.assertEqual(checked['pages'], report['pages'])
        answers = checked['pages'][0]['answers']
        self.assertEqual([a['blank_id'] for a in answers], ['Q1', 'Q2'])
        self.assertEqual([c['kind'] for c in answers[1]['components']], ['text', 'bar', 'text'])
        self.assertEqual([c['text'] for c in answers[1]['components']], ['1', '', '2'])
        actual = {s['shape_id']: s for s in editor.inspect_deck(root / report['output'])['slides'][0]['shapes']}
        for item in answers:
            for component in item['components']:
                self.assertEqual(actual[component['shape_id']]['text'] or '', component['text'])
        old = editor.inspect_deck(source)
        self.assertEqual(list(actual.values())[:len(old['slides'][0]['shapes'])], old['slides'][0]['shapes'])
        for part, data in editor._parts(source).items():
            if part != 'ppt/slides/slide1.xml':
                self.assertEqual(editor._parts(root / report['output'])[part], data, part)

    def test_existing_main_interactive_and_build_trees_are_preserved(self):
        root, plan = component_fixture()
        source = root / plan['source_deck']
        rewrite_slide(source, existing_timing)
        bind_source(root, plan)
        plan['pages'][0]['items'] = [answer()]
        expected = editor._xml_value(slide(source).find('p:timing', editor.NS))
        report = self.build_components(root, plan)
        self.assertEqual(editor._xml_value(slide(root / report['output']).find('p:timing', editor.NS)), expected)
        checked = click_answers.validate_components(root, report['manifest'])
        self.assertTrue(checked['checks']['original_timing_preserved'])

    def test_zero_answers_are_immutable_components_not_final_answers(self):
        for items in ([], [non_answer('open_blank')], [non_answer('ambiguous')]):
            with self.subTest(items=items):
                root, plan = component_fixture()
                plan['pages'][0]['items'] = items
                report = self.build_components(root, plan)
                self.assertEqual((root / report['output']).read_bytes(), (root / plan['source_deck']).read_bytes())
                self.assertEqual(report['pages'][0]['answers'], [])
                self.assertFalse(report['ready_for_final'])
                self.assertEqual(report['ready_for_animation'], not any(i['disposition'] == 'ambiguous' for i in items))
                with self.assertRaisesRegex(ValueError, 'mode|component'):
                    click_answers.validate_final(root, report['manifest'])

    def test_cross_page_blank_ids_remain_separate_and_page_order_is_real(self):
        root, plan = component_fixture()
        source = root / plan['source_deck']
        deck = Presentation(source)
        deck.slides.add_slide(deck.slide_layouts[6])
        deck.save(source)
        bind_source(root, plan)
        plan['mapping']['P002'] = 2
        second = copy.deepcopy(plan['pages'][0])
        second.update(page_id='P002', items=[answer()])
        plan['pages'][0]['items'] = [answer()]
        plan['pages'].insert(0, second)
        report = self.build_components(root, plan)
        self.assertEqual([(p['page_id'], p['slide_index']) for p in report['pages']], [('P001', 1), ('P002', 2)])
        self.assertEqual([p['answers'][0]['blank_id'] for p in report['pages']], ['Q1', 'Q1'])
        self.assertEqual(click_answers.validate_components(root, report['manifest'])['mapping'], plan['mapping'])

    def test_replay_and_mode_switch_cannot_reuse_another_modes_manifest(self):
        for initial_mode in ('components_only', None):
            with self.subTest(initial_mode=initial_mode):
                root, plan = component_fixture()
                if initial_mode is None:
                    plan.pop('mode')
                report = self.build_components(root, plan)
                paths = [root / report['output'], root / report['manifest'], root / report['plan']['path']]
                before = [p.read_bytes() for p in paths]
                self.assertTrue(click_answers.build(root, plan)['idempotent'])
                changed = copy.deepcopy(plan)
                if initial_mode is None:
                    changed['mode'] = 'components_only'
                else:
                    changed.pop('mode')
                with self.assertRaisesRegex(ValueError, 'plan|overwrite'):
                    click_answers.build(root, changed)
                self.assertEqual([p.read_bytes() for p in paths], before)
                if initial_mode is None:
                    self.assertTrue(callable(getattr(click_answers, 'validate_components', None)),
                                    'Component manifests need a separate validator')
                    with self.assertRaisesRegex(ValueError, 'mode|component'):
                        click_answers.validate_components(root, report['manifest'])

    def test_forged_component_ids_and_ready_flag_are_rejected(self):
        root, plan = component_fixture()
        plan['pages'][0]['items'] = [answer()]
        report = self.build_components(root, plan)
        manifest = root / report['manifest']
        original = state.read_json(manifest)
        for change in (lambda d: d.update(ready_for_final=True),
                       lambda d: d['pages'][0]['answers'][0]['components'][0].update(shape_id=9999)):
            data = copy.deepcopy(original)
            change(data)
            state.write_json(manifest, data)
            with self.assertRaisesRegex(ValueError, 'Manifest|manifest'):
                click_answers.validate_components(root, report['manifest'])
        with self.assertRaisesRegex(ValueError, 'mode|component'):
            click_answers.validate_final(root, report['manifest'])

    def test_timing_or_existing_object_tamper_fails_even_with_refreshed_output_hash(self):
        for target in ('build', 'shape', 'added_timing'):
            with self.subTest(target=target):
                root, plan = component_fixture()
                if target == 'build':
                    rewrite_slide(root / plan['source_deck'], existing_timing)
                    bind_source(root, plan)
                plan['pages'][0]['items'] = [answer()]
                report = self.build_components(root, plan)
                def tamper(rootxml):
                    if target == 'build':
                        rootxml.find('p:timing/p:bldLst/p:bldP', editor.NS).set('grpId', '9999')
                    elif target == 'shape':
                        rootxml.find('.//a:t', editor.NS).text = 'tampered source text'
                    else:
                        rootxml.append(copy.deepcopy(click_answers.EMPTY_TIMING))
                rewrite_slide(root / report['output'], tamper)
                refresh_output_hash(root, report)
                with self.assertRaisesRegex(ValueError, 'Original|timing|metadata'):
                    click_answers.validate_components(root, report['manifest'])

    def test_bound_source_changes_invalidate_component_validation(self):
        root, plan = component_fixture()
        report = self.build_components(root, plan)
        (root / 'inputs/answer-basis.json').write_text('changed source', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Source|source'):
            click_answers.validate_components(root, report['manifest'])


if __name__ == '__main__':
    unittest.main()
