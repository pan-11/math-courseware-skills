"""Retained synthetic native-click checks; never real lesson/playback acceptance."""
import copy
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/math-courseware-studio/scripts'))
from runtime import pptx_editor as editor, state
from fixture_factory import retained_project, layered_deck


def module(test):
    test.assertIsNotNone(importlib.util.find_spec('runtime.click_answers'),
                         'Native inline answers need a real recoverable build/validate stage')
    return importlib.import_module('runtime.click_answers')


def fixture():
    root = retained_project('click-answers')
    source = layered_deck(root)
    basis = root / 'inputs/answer-basis.json'
    state.write_json(basis, {'Q1': '3 + 2 = 5', 'Q2': 'one of two equal pieces: 1/2',
                             'Q3': 'Give a personal example', 'Q4': 'Original title already visible'})
    authority = root / 'inputs/instruction.json'
    state.write_json(authority, {'user_instruction': 'Synthetic whole-deck faithful refill instruction only'})
    paths = [source, basis, authority, root / 'inputs/fixture-image.png']
    plan = {'schema_version': 'inline_answers_v1', 'source_deck': 'inputs/layered-source.pptx',
            'source_sha256': editor.sha256(source), 'output': 'editable/output/click.pptx',
            'mapping': {'P001': 1},
            'source_versions': {p.relative_to(root).as_posix(): editor.sha256(p) for p in paths},
            'request': {'user_instruction': 'Synthetic whole-deck faithful refill instruction only',
                        'evidence_ref': {'path': 'inputs/instruction.json', 'sha256': editor.sha256(authority)}},
            'pages': [{'page_id': 'P001', 'scan_complete': True,
                       'reference_image': 'inputs/fixture-image.png', 'items': []}]}
    return root, plan


def answer(blank='Q1', order=1, fraction=False):
    components = ([{'object_id': blank + '-numerator', 'kind': 'text', 'text': '1',
                    'box': {'x': 300, 'y': 120, 'width': 80, 'height': 35}},
                   {'object_id': blank + '-bar', 'kind': 'bar',
                    'box': {'x': 300, 'y': 158, 'width': 80, 'height': 1.5}},
                   {'object_id': blank + '-denominator', 'kind': 'text', 'text': '2',
                    'box': {'x': 300, 'y': 165, 'width': 80, 'height': 35}}] if fraction else
                  [{'object_id': blank + '-number', 'kind': 'text', 'text': '5',
                    'box': {'x': 100, 'y': 120, 'width': 80, 'height': 50}}])
    return {'blank_id': blank, 'disposition': 'answer', 'reason': 'Existing determinate blank',
            'source_basis': {'path': 'inputs/answer-basis.json', 'locator': blank},
            'answer_text': '1/2' if fraction else '5', 'derivation': '1 of 2 equal pieces' if fraction else '3 + 2 = 5',
            'click_order': order, 'components': components,
            'box': {'x': 300 if fraction else 100, 'y': 120, 'width': 80, 'height': 80}}


def non_answer(disposition, blank='Q3'):
    return {'blank_id': blank, 'disposition': disposition,
            'source_basis': {'path': 'inputs/answer-basis.json', 'locator': blank},
            'reason': 'Personal examples are non-unique' if disposition == 'open_blank' else 'Conflicting source wording'}


def slide(path):
    parts = editor._parts(path)
    return editor._parse(parts[editor._slides(parts)[0]])


def click_groups(root):
    return root.findall(".//p:cTn[@nodeType='mainSeq']/p:childTnLst/p:par", editor.NS)


def rewrite_slide(path, change):
    original = path.with_name(path.stem + '-before-tamper.pptx')
    original.write_bytes(path.read_bytes())
    parts = editor._parts(path)
    part = editor._slides(parts)[0]
    root = editor._parse(parts[part])
    change(root)
    parts[part] = editor.ET.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    with zipfile.ZipFile(path, 'w') as archive:
        for name, value in parts.items():
            archive.writestr(name, value)


class ClickAnswerTests(unittest.TestCase):
    def test_two_answers_are_two_clicks_and_fraction_components_share_one_click(self):
        api = module(self)
        root, plan = fixture()
        plan['pages'][0]['items'] = [answer(), answer('Q2', 2, True)]
        source_bytes = (root / plan['source_deck']).read_bytes()
        report = api.build(root, plan)
        self.assertTrue(report['ready_for_final'])
        self.assertEqual(report['counts']['answers'], 2)
        self.assertEqual(report['playback'], 'unverified')
        groups = click_groups(slide(root / report['output']))
        self.assertEqual(len(groups), 2)
        self.assertEqual([len(g.findall('.//p:spTgt', editor.NS)) for g in groups], [1, 3])
        effects = groups[1].findall('.//p:cTn[@presetClass]', editor.NS)
        self.assertEqual([n.get('nodeType') for n in effects], ['clickEffect', 'withEffect', 'withEffect'])
        self.assertTrue(all(n.get('presetClass') == 'entr' and n.get('presetID') == '1' for n in effects))
        inventory = editor.inspect_deck(root / report['output'])
        added = [s for s in inventory['slides'][0]['shapes'] if s['name'].startswith('mcw-answer:')]
        self.assertEqual(len(added), 4)
        self.assertTrue(all(f['color'] == 'B3261E' for s in added if s['text'] for f in s['fonts']))
        states = report['pages'][0]['answer_states']
        self.assertEqual([len(s['visible_shape_ids']) for s in states], [0, 1, 4])
        self.assertEqual((root / plan['source_deck']).read_bytes(), source_bytes)
        checked = api.validate_final(root, {'path': report['manifest'], 'sha256': report['manifest_sha256']})
        self.assertTrue(checked['ready_for_final'])

    def test_original_animation_layers_media_and_unknown_parts_survive(self):
        api = module(self)
        root, plan = fixture()
        source = root / plan['source_deck']
        editor._office(['add', source, '/slide[1]/shape[@name=existing-title]', '--type', 'animation',
                        '--prop', 'effect=fade', '--prop', 'class=entrance', '--prop', 'trigger=onClick'])
        editor._office(['close', source])
        plan['source_sha256'] = plan['source_versions'][plan['source_deck']] = editor.sha256(source)
        original_group = editor._xml_value(click_groups(slide(source))[0])
        before = editor.inspect_deck(source)
        plan['pages'][0]['items'] = [answer()]
        report = api.build(root, plan)
        self.assertEqual(editor._xml_value(click_groups(slide(root / report['output']))[0]), original_group)
        self.assertEqual(report['pages'][0]['existing_click_count'], 1)
        after = editor.inspect_deck(root / report['output'])
        self.assertEqual(after['slides'][0]['shapes'][:len(before['slides'][0]['shapes'])], before['slides'][0]['shapes'])
        self.assertEqual(before['media'], after['media'])
        for part, data in editor._parts(source).items():
            if part != 'ppt/slides/slide1.xml':
                self.assertEqual(editor._parts(root / report['output'])[part], data, part)

    def test_zero_answers_and_open_blanks_are_complete_without_new_shapes(self):
        api = module(self)
        for items in ([], [non_answer('open_blank')]):
            with self.subTest(items=items):
                root, plan = fixture()
                plan['pages'][0]['items'] = items
                report = api.build(root, plan)
                self.assertEqual((root / report['output']).read_bytes(), (root / plan['source_deck']).read_bytes())
                self.assertTrue(report['ready_for_final'])
                self.assertEqual(report['counts']['answers'], 0)

    def test_original_visible_answer_is_not_recreated_or_hidden(self):
        api = module(self)
        root, plan = fixture()
        shape = next(s for s in editor.inspect_deck(root / plan['source_deck'])['slides'][0]['shapes']
                     if s['name'] == 'existing-title')
        item = non_answer('already_visible', 'Q4')
        item['existing_shapes'] = [{'shape_id': shape['shape_id'], 'expected_text': shape['text']}]
        plan['pages'][0]['items'] = [item]
        report = api.build(root, plan)
        self.assertEqual(report['counts']['already_visible'], 1)
        self.assertEqual((root / report['output']).read_bytes(), (root / plan['source_deck']).read_bytes())
        self.assertIsNone(slide(root / report['output']).find('p:timing', editor.NS))

    def test_ambiguous_item_cannot_be_certified_by_forging_ready_flag(self):
        api = module(self)
        root, plan = fixture()
        plan['pages'][0]['items'] = [answer(), non_answer('ambiguous')]
        report = api.build(root, plan)
        self.assertFalse(report['ready_for_final'])
        manifest = root / report['manifest']
        data = state.read_json(manifest)
        data['ready_for_final'] = True
        state.write_json(manifest, data)
        with self.assertRaisesRegex(ValueError, 'manifest|Manifest|ready'):
            api.validate_final(root, report['manifest'])

    def test_missing_scan_reference_or_answer_basis_fails_before_output(self):
        api = module(self)
        changes = [lambda p: p['pages'].clear(),
                   lambda p: p['pages'][0].update(scan_complete=False),
                   lambda p: p['pages'][0].update(reference_image='inputs/missing.png'),
                   lambda p: p['pages'][0]['items'][0].update(derivation=''),
                   lambda p: p['pages'][0]['items'][0]['source_basis'].update(path='inputs/unknown.json')]
        for change in changes:
            root, plan = fixture()
            plan['pages'][0]['items'] = [answer()]
            change(plan)
            with self.assertRaises(ValueError):
                api.build(root, plan)
            self.assertFalse((root / plan['output']).exists())

    def test_components_cannot_escape_blank_change_answer_or_duplicate_click(self):
        api = module(self)
        for change in (lambda a: a['components'][0]['box'].update(x=800),
                       lambda a: a.update(answer_text='6'),
                       lambda a: a.update(click_order=2)):
            root, plan = fixture()
            item = answer()
            change(item)
            plan['pages'][0]['items'] = [item]
            with self.assertRaises(ValueError):
                api.build(root, plan)
            self.assertFalse((root / plan['output']).exists())

    def test_replay_is_byte_immutable_and_changed_plan_is_rejected(self):
        api = module(self)
        root, plan = fixture()
        report = api.build(root, plan)
        paths = [root / report['output'], root / report['manifest'], root / report['plan']['path']]
        before = [p.read_bytes() for p in paths]
        repeat = api.build(root, plan)
        self.assertTrue(repeat['idempotent'])
        self.assertEqual([p.read_bytes() for p in paths], before)
        changed = copy.deepcopy(plan)
        changed['pages'][0]['items'] = [answer()]
        with self.assertRaisesRegex(ValueError, 'plan|Plan|overwrite'):
            api.build(root, changed)
        self.assertEqual([p.read_bytes() for p in paths], before)

    def test_changed_bound_source_and_manual_output_are_rejected(self):
        api = module(self)
        root, plan = fixture()
        report = api.build(root, plan)
        (root / 'inputs/answer-basis.json').write_text('changed source', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'source|Source|hash'):
            api.build(root, plan)
        root, plan = fixture()
        report = api.build(root, plan)
        with (root / report['output']).open('ab') as handle:
            handle.write(b'synthetic manual change')
        with self.assertRaisesRegex(ValueError, 'hash|changed|modified'):
            api.build(root, plan)

    def test_native_xml_is_checked_even_if_manifest_output_hash_is_refreshed(self):
        api = module(self)
        root, plan = fixture()
        plan['pages'][0]['items'] = [answer()]
        report = api.build(root, plan)
        output = root / report['output']
        rewrite_slide(output, lambda x: x.find(".//p:cTn[@nodeType='clickEffect']", editor.NS).set('nodeType', 'withEffect'))
        manifest = state.read_json(root / report['manifest'])
        manifest['output_sha256'] = editor.sha256(output)
        state.write_json(root / report['manifest'], manifest)
        with self.assertRaisesRegex(ValueError, 'click|animation|Animation|timing'):
            api.validate_final(root, report['manifest'])

    def test_unsupported_existing_timing_is_retained_and_rejected(self):
        api = module(self)
        root, plan = fixture()
        source = root / plan['source_deck']
        def add_unknown(rootxml):
            timing = editor.ET.SubElement(rootxml, '{' + editor.NS['p'] + '}timing')
            editor.ET.SubElement(timing, '{' + editor.NS['p'] + '}tnLst')
        rewrite_slide(source, add_unknown)
        before = source.read_bytes()
        plan['source_sha256'] = plan['source_versions'][plan['source_deck']] = editor.sha256(source)
        plan['pages'][0]['items'] = [answer()]
        with self.assertRaisesRegex(ValueError, 'timing|sequence'):
            api.build(root, plan)
        self.assertEqual(source.read_bytes(), before)
        self.assertFalse((root / plan['output']).exists())

    def test_existing_answer_at_the_same_blank_cannot_be_added_again(self):
        api = module(self)
        root, plan = fixture()
        source = root / plan['source_deck']
        editor._office(['add', source, '/slide[1]', '--type', 'shape', '--prop', 'name=existing-visible-answer',
                        '--prop', 'text=5', '--prop', 'x=100pt', '--prop', 'y=120pt',
                        '--prop', 'width=80pt', '--prop', 'height=50pt'])
        editor._office(['close', source])
        plan['source_sha256'] = plan['source_versions'][plan['source_deck']] = editor.sha256(source)
        plan['pages'][0]['items'] = [answer()]
        with self.assertRaisesRegex(ValueError, 'already|existing|Existing'):
            api.build(root, plan)
        self.assertFalse((root / plan['output']).exists())

    def test_answer_build_group_must_match_its_entrance_effect(self):
        api = module(self)
        root, plan = fixture()
        plan['pages'][0]['items'] = [answer()]
        report = api.build(root, plan)
        output = root / report['output']
        rewrite_slide(output, lambda x: x.find('.//p:bldP', editor.NS).set('grpId', '99'))
        manifest = state.read_json(root / report['manifest'])
        manifest['output_sha256'] = editor.sha256(output)
        state.write_json(root / report['manifest'], manifest)
        with self.assertRaisesRegex(ValueError, 'build|group|animation'):
            api.validate_final(root, report['manifest'])

    def test_interrupted_manifest_write_recovers_existing_bytes(self):
        api = module(self)
        root, plan = fixture()
        output = root / plan['output']
        output.parent.mkdir(parents=True)
        output.write_bytes((root / plan['source_deck']).read_bytes())
        state.write_json(output.with_suffix('.plan.json'), plan)
        before = output.read_bytes()
        report = api.build(root, plan)
        self.assertTrue(report['recovered_output'])
        self.assertEqual(output.read_bytes(), before)
        self.assertTrue(api.validate_final(root, report['manifest'])['ready_for_final'])

    def test_all_mapped_pages_must_be_scanned_and_report_uses_slide_order(self):
        api = module(self)
        root, plan = fixture()
        source = root / plan['source_deck']
        editor._office(['add', source, '/', '--type', 'slide'])
        editor._office(['close', source])
        plan['source_sha256'] = plan['source_versions'][plan['source_deck']] = editor.sha256(source)
        plan['mapping']['P002'] = 2
        with self.assertRaisesRegex(ValueError, 'every mapped page'):
            api.build(root, plan)
        plan['pages'].insert(0, {'page_id': 'P002', 'scan_complete': True,
                                'reference_image': 'inputs/fixture-image.png', 'items': []})
        report = api.build(root, plan)
        self.assertEqual([p['page_id'] for p in report['pages']], ['P001', 'P002'])

    def test_already_visible_requires_actual_initial_visibility(self):
        api = module(self)
        root, plan = fixture()
        source = root / plan['source_deck']
        editor._office(['add', source, '/slide[1]/shape[@name=existing-title]', '--type', 'animation',
                        '--prop', 'effect=appear', '--prop', 'class=entrance', '--prop', 'trigger=onClick'])
        editor._office(['close', source])
        plan['source_sha256'] = plan['source_versions'][plan['source_deck']] = editor.sha256(source)
        shape = next(s for s in editor.inspect_deck(source)['slides'][0]['shapes'] if s['name'] == 'existing-title')
        item = non_answer('already_visible', 'Q4')
        item['existing_shapes'] = [{'shape_id': shape['shape_id'], 'expected_text': shape['text']}]
        plan['pages'][0]['items'] = [item]
        with self.assertRaisesRegex(ValueError, 'entrance animation'):
            api.build(root, plan)

    def test_output_changed_during_final_validation_is_not_certified(self):
        api = module(self)
        root, plan = fixture()
        report = api.build(root, plan)
        output = root / report['output']
        original_office = editor._office
        def concurrent_edit(args):
            result = original_office(args)
            if args[0] == 'validate' and Path(args[1]) == output:
                with output.open('ab') as stream:
                    stream.write(b'synthetic concurrent manual edit')
            return result
        with patch.object(editor, '_office', concurrent_edit):
            with self.assertRaisesRegex(ValueError, 'changed|hash'):
                api.validate_final(root, report['manifest'])

    def test_legitimate_duplicate_source_names_do_not_require_layer_renaming(self):
        api = module(self)
        root, plan = fixture()
        source = root / plan['source_deck']
        def duplicate_names(rootxml):
            for node in rootxml.findall('p:cSld/p:spTree/p:pic', editor.NS):
                editor._identity(node).set('name', 'Picture 1')
        rewrite_slide(source, duplicate_names)
        plan['source_sha256'] = plan['source_versions'][plan['source_deck']] = editor.sha256(source)
        plan['pages'][0]['items'] = [answer()]
        try:
            report = api.build(root, plan)
        except ValueError as exc:
            self.fail('Legitimate repeated source names must retain their layers: ' + str(exc))
        shapes = editor.inspect_deck(root / report['output'])['slides'][0]['shapes']
        self.assertEqual(sum(s['name'] == 'Picture 1' for s in shapes), 2)
        self.assertTrue(report['checks']['original_shapes_preserved'])

    def test_initial_visibility_includes_all_parent_groups(self):
        api = module(self)
        for mode in ('hidden', 'entrance'):
            with self.subTest(mode=mode):
                root, plan = fixture()
                source = root / plan['source_deck']
                if mode == 'entrance':
                    editor._office(['add', source, '/slide[1]/shape[@name=existing-title]', '--type', 'animation',
                                    '--prop', 'effect=appear', '--prop', 'class=entrance', '--prop', 'trigger=onClick'])
                    editor._office(['close', source])
                def hide_group(rootxml):
                    group = rootxml.find('p:cSld/p:spTree/p:grpSp', editor.NS)
                    if mode == 'hidden':
                        editor._identity(group).set('hidden', '1')
                    else:
                        group_id = editor._identity(group).get('id')
                        for node in rootxml.findall('.//p:spTgt', editor.NS) + rootxml.findall('.//p:bldP', editor.NS):
                            node.set('spid', group_id)
                rewrite_slide(source, hide_group)
                plan['source_sha256'] = plan['source_versions'][plan['source_deck']] = editor.sha256(source)
                child = next(s for s in editor.inspect_deck(source)['slides'][0]['shapes'] if s['name'] == 'math-block-1')
                item = non_answer('already_visible', 'Q4')
                item['existing_shapes'] = [{'shape_id': child['shape_id'], 'expected_text': child['text']}]
                plan['pages'][0]['items'] = [item]
                with self.assertRaisesRegex(ValueError, 'hidden|entrance'):
                    api.build(root, plan)


if __name__ == '__main__':
    unittest.main()
