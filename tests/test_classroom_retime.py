"""Controlled old-teaching retiming on retained synthetic copies, never playback proof."""
import copy
import json
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/math-courseware-studio/scripts'))
from runtime import classroom_animation as animation, classroom_timing as timing, pptx_editor as editor
from test_classroom_animation import fixture, page, unit, step, action, patch_source
from test_classroom_timing import media_timing

NS, ET = editor.NS, editor.ET


def prepared(with_media=False):
    root, plan = fixture()
    units = [unit('u' + str(i), i, 'part-' + str(i)) for i in range(2, 10)]
    original_units = {u['unit_id']: u for u in units if u['targets'][0]['shape_id'] in (3, 5, 7)}
    old = timing.compile_timing(media_timing() if with_media else None,
                               [step('old-' + str(i), action('u' + str(i))) for i in (3, 5, 7)],
                               original_units)

    def change(parts, slides):
        slide = editor._parse(parts[slides[0]])
        tree = slide.find('p:cSld/p:spTree', NS)
        template = copy.deepcopy(tree[0])
        for item in list(tree):
            tree.remove(item)
        for i in list(range(2, 10)) + ([90, 91] if with_media else []):
            shape = copy.deepcopy(template)
            identity = editor._identity(shape)
            identity.set('id', str(i))
            identity.set('name', 'part-' + str(i))
            shape.find('.//a:t', NS).text = 'part-' + str(i)
            tree.append(shape)
        slide.append(copy.deepcopy(old))
        parts[slides[0]] = ET.tostring(slide)
    patch_source(root, plan, change)
    selected = [e.get('id') for e in old.findall(".//p:cTn[@nodeType='mainSeq']//*[@presetClass='entr']", NS)]
    plan['pages'][0] = page('P001', units,
        [step('new-' + str(i), action('u' + str(i))) for i in range(2, 10)],
        existing_policy='replace_managed', retime={
            'timing_sha256': editor._digest(editor._xml_value(old)),
            'effect_ids': selected, 'reason': 'Interleave each diagram with its original explanation'})
    return root, plan, old


def first_slide(root, result):
    parts = editor._parts(root / result['output'])
    return editor._parse(parts[editor._slides(parts)[0]])


class ClassroomRetimeTests(unittest.TestCase):
    def test_all_teaching_removed_is_schema_valid_and_supports_new_compilation(self):
        from test_click_answers import fixture as full_deck_fixture
        from runtime.classroom_retime import replace_managed
        root, source_plan = full_deck_fixture()
        source = root / source_plan['source_deck']
        parts = editor._parts(source)
        part = editor._slides(parts)[0]
        slide = editor._parse(parts[part])
        obj = next(o for o in animation._objects(slide).values() if o['name'] == 'existing-title')
        teaching_unit = unit('title', obj['shape_id'], obj['text'])
        old = timing.compile_timing(None, [step('old', action('title'))], {'title': teaching_unit})
        slide.append(old)
        parts[part] = ET.tostring(slide)
        with zipfile.ZipFile(source, 'w') as archive:
            for name, value in parts.items():
                archive.writestr(name, value)
        source_plan['source_sha256'] = source_plan['source_versions'][source_plan['source_deck']] = editor.sha256(source)
        editor._office(['validate', source])
        instruction = {k: copy.deepcopy(source_plan[k]) for k in (
            'source_deck', 'source_sha256', 'source_versions', 'output', 'request', 'mapping')}
        selected = [n.get('id') for n in old.findall('.//p:cTn[@presetClass]', NS)]
        specification = {'timing_sha256': editor._digest(editor._xml_value(old)), 'effect_ids': selected,
                         'reason': 'The copied reference declares a static teaching page'}
        entry = page('P001', [{**teaching_unit, 'initial_visible': True}], [], existing_policy='replace_managed',
                     retime=specification, static_reason='Keep this observation material visible')
        entry['basis'] = {'path': 'inputs/answer-basis.json', 'locator': 'Q4'}
        plan = {**instruction, 'schema_version': animation.VERSION, 'mode': 'classroom', 'pages': [entry]}
        result = animation.build(root, plan)
        editor._office(['validate', root / result['output']])
        self.assertIsNone(first_slide(root, result).find('p:timing', NS))
        self.assertTrue(animation.validate_final(root, result['manifest'])['idempotent'])
        remaining, _ = replace_managed(old, specification, {'title': teaching_unit}, animation._objects(slide))
        self.assertIsNone(remaining)
        fresh = timing.compile_timing(remaining, [step('new', action('title', 'fade'))], {'title': teaching_unit})
        self.assertEqual(len(fresh.findall(".//p:cTn[@nodeType='clickEffect']", NS)), 1)
        slide.replace(old, fresh)
        parts[part] = ET.tostring(slide)
        rebuilt = root / 'editable/recompiled.pptx'
        with zipfile.ZipFile(rebuilt, 'w') as archive:
            for name, value in parts.items():
                archive.writestr(name, value)
        editor._office(['validate', rebuilt])

    def test_empty_main_is_removed_without_removing_remaining_interactive_media(self):
        from runtime.classroom_retime import replace_managed
        root, plan, old = prepared(with_media=True)
        main = old.find(".//p:cTn[@nodeType='mainSeq']/p:childTnLst", NS)
        main.remove(main[0])
        builds = old.find('p:bldLst', NS)
        builds.remove(builds.find("p:bldP[@spid='91']", NS))
        page_plan = plan['pages'][0]
        page_plan['retime']['timing_sha256'] = editor._digest(editor._xml_value(old))
        parts = editor._parts(root / plan['source_deck'])
        slide = editor._parse(parts[editor._slides(parts)[0]])
        remaining, _ = replace_managed(old, page_plan['retime'],
            {u['unit_id']: u for u in page_plan['units']}, animation._objects(slide))
        self.assertIsNotNone(remaining)
        query = ".//p:cTn[@nodeType='interactiveSeq']"
        self.assertEqual(editor._xml_value(old.find(query, NS)), editor._xml_value(remaining.find(query, NS)))
        self.assertIsNone(remaining.find(".//p:cTn[@nodeType='mainSeq']", NS))
        self.assertIsNone(remaining.find('p:bldLst', NS))
        self.assertFalse([n for n in remaining.findall('.//p:childTnLst', NS) if not len(n)])

    def test_continuation_activation_reference_is_hash_bound_without_inventing_user_text(self):
        root, plan = fixture()
        path = root / 'inputs/activation.json'
        path.write_text(json.dumps({'user_instruction': plan['request']['user_instruction']}), encoding='utf-8')
        relative = 'inputs/activation.json'
        digest = editor.sha256(path)
        plan['source_versions'][relative] = digest
        plan['request']['activation_ref'] = {'path': relative, 'sha256': digest}
        self.assertTrue(animation.check(root, plan)['ready_for_review'])
        plan['request']['activation_ref']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Activation reference'):
            animation.check(root, plan)

    def test_old_three_explanations_move_into_eight_steps(self):
        root, plan, old = prepared()
        source_bytes = (root / plan['source_deck']).read_bytes()
        result = animation.build(root, plan)
        slide = first_slide(root, result)
        main = slide.find(".//p:cTn[@nodeType='mainSeq']", NS)
        effects = main.findall('.//p:cTn[@presetClass]', NS)
        self.assertEqual([e.get('nodeType') for e in effects], ['clickEffect'] * 8)
        self.assertEqual([e.find('.//p:spTgt', NS).get('spid') for e in effects],
                         [str(i) for i in range(2, 10)])
        self.assertEqual((root / plan['source_deck']).read_bytes(), source_bytes)
        self.assertTrue(animation.validate_final(root, result['manifest'])['idempotent'])
        self.assertNotEqual(editor._xml_value(old), editor._xml_value(slide.find('p:timing', NS)))

    def test_retime_to_static_removes_old_hidden_initializers(self):
        root, plan, _ = prepared()
        p = plan['pages'][0]
        p['steps'] = []
        p['static_reason'] = 'Target reference keeps this material visible for observation'
        for u in p['units']:
            u['initial_visible'] = True
        result = animation.build(root, plan)
        slide = first_slide(root, result)
        self.assertFalse(slide.findall(".//p:cTn[@nodeType='clickEffect']", NS))
        self.assertFalse(slide.findall(".//p:strVal[@val='hidden']", NS))
        self.assertTrue(animation.validate_final(root, result['manifest'])['idempotent'])

    def test_non_target_main_media_interactive_and_builds_are_preserved(self):
        root, plan, old = prepared(with_media=True)
        result = animation.build(root, plan)
        after = first_slide(root, result).find('p:timing', NS)
        for query in [".//p:cTn[@nodeType='interactiveSeq']",
                      ".//p:cTn[@presetClass='mediacall']",
                      "p:bldLst/p:bldP[@spid='91']"]:
            self.assertEqual(editor._xml_value(after.find(query, NS)), editor._xml_value(old.find(query, NS)))
        self.assertEqual(len(after.findall(".//p:cTn[@nodeType='mainSeq']//*[@nodeType='clickEffect']", NS)), 9)

    def test_wrong_hash_unknown_duplicate_and_unowned_effects_are_rejected(self):
        changes = [
            lambda p: p['retime'].update(timing_sha256='0' * 64),
            lambda p: p['retime']['effect_ids'].append('999999'),
            lambda p: p['retime']['effect_ids'].append(p['retime']['effect_ids'][0]),
            lambda p: p['units'].pop(1),
        ]
        for change in changes:
            root, plan, _ = prepared()
            change(plan['pages'][0])
            with self.subTest(change=change), self.assertRaises(ValueError):
                animation.build(root, plan)
            self.assertFalse((root / plan['output']).exists())

    def test_media_and_interactive_selection_cannot_be_reclassified_as_teaching(self):
        for forbidden_id in ('80', '83'):
            root, plan, _ = prepared(with_media=True)
            plan['pages'][0]['retime']['effect_ids'].append(forbidden_id)
            with self.subTest(effect=forbidden_id), self.assertRaisesRegex(ValueError, 'teaching|main|media'):
                animation.build(root, plan)

    def test_existing_policies_remain_conflict_rejecting(self):
        for policy in ('reject_conflicts', 'append_after_existing'):
            root, plan, _ = prepared()
            p = plan['pages'][0]
            p['existing_policy'] = policy
            p.pop('retime')
            if policy == 'append_after_existing':
                p['existing_reason'] = 'Synthetic negative overlap case'
            with self.subTest(policy=policy), self.assertRaisesRegex(ValueError, 'ownership conflict'):
                animation.check(root, plan)

    def test_partial_original_click_group_cannot_leave_an_automatic_orphan(self):
        root, plan, old = prepared()
        main = old.find(".//p:cTn[@nodeType='mainSeq']/p:childTnLst", NS)
        first = main[0].find('.//p:cTn[@presetClass]', NS)
        second = main[1].find('.//p:cTn[@presetClass]', NS)
        second.set('nodeType', 'withEffect')
        container = first.getparent().getparent()
        container.append(copy.deepcopy(second.getparent()))
        main.remove(main[1])
        def change(parts, slides):
            slide = editor._parse(parts[slides[0]])
            slide.replace(slide.find('p:timing', NS), old)
            parts[slides[0]] = ET.tostring(slide)
        patch_source(root, plan, change)
        plan['pages'][0]['retime'].update(timing_sha256=editor._digest(editor._xml_value(old)), effect_ids=[first.get('id')])
        with self.assertRaisesRegex(ValueError, 'entire original click group'):
            animation.check(root, plan)

    def test_retained_timing_reference_to_a_removed_effect_is_rejected(self):
        root, plan, old = prepared(with_media=True)
        interactive = old.find(".//p:cTn[@nodeType='interactiveSeq']/p:stCondLst/p:cond", NS)
        ET.SubElement(interactive, '{' + NS['p'] + '}tn', val=plan['pages'][0]['retime']['effect_ids'][0])
        def change(parts, slides):
            slide = editor._parse(parts[slides[0]])
            slide.replace(slide.find('p:timing', NS), old)
            parts[slides[0]] = ET.tostring(slide)
        patch_source(root, plan, change)
        plan['pages'][0]['retime']['timing_sha256'] = editor._digest(editor._xml_value(old))
        with self.assertRaisesRegex(ValueError, 'reference dangling'):
            animation.check(root, plan)


if __name__ == '__main__':
    unittest.main()
