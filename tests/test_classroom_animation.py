"""Synthetic classroom plans; structure evidence is never native playback approval."""
import copy
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/math-courseware-studio/scripts'))
from runtime import pptx_editor as editor, state


def module(test):
    test.assertIsNotNone(importlib.util.find_spec('runtime.classroom_animation'),
                         'Classroom plans need an actual immutable, semantic build/validation stage')
    return importlib.import_module('runtime.classroom_animation')


def fixture():
    root = Path(__file__).parent / 'runs' / ('classroom-plan-' + uuid.uuid4().hex)
    root.mkdir()
    (root / 'AGENTS.md').write_text('# Synthetic fixture rules\ninputs holds synthetic sources; editable holds candidates. '
                                  'Retain all evidence; no cleanup. Never real lesson/playback acceptance.\n', encoding='utf-8')
    (root / 'inputs').mkdir()
    (root / 'editable').mkdir()
    source = root / 'inputs/source.pptx'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('ppt/presentation.xml', ('<p:presentation xmlns:p="' + editor.NS['p'] +
                         '" xmlns:r="' + editor.NS['r'] + '"><p:sldIdLst><p:sldId id="256" r:id="rId1"/>'
                         '<p:sldId id="257" r:id="rId2"/></p:sldIdLst>'
                         '<p:sldSz cx="12192000" cy="6858000"/></p:presentation>'))
        archive.writestr('ppt/_rels/presentation.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Target="slides/slide2.xml"/>'
                         '<Relationship Id="rId2" Target="slides/slide1.xml"/></Relationships>')
        for part, words in [('slide2.xml', ('观察图形', '有四条边\n对边相等', '长方形')),
                            ('slide1.xml', ('计算周长', '5＋3＋5＋3＝16（厘米）', '（5＋3）×2＝16（厘米）'))]:
            slide = editor.ET.Element('{' + editor.NS['p'] + '}sld', nsmap=editor.NS)
            tree = editor.ET.SubElement(editor.ET.SubElement(slide, '{' + editor.NS['p'] + '}cSld'),
                                        '{' + editor.NS['p'] + '}spTree')
            for i, words_ in enumerate(words, 2):
                shape = editor.ET.SubElement(tree, '{' + editor.NS['p'] + '}sp')
                nv = editor.ET.SubElement(shape, '{' + editor.NS['p'] + '}nvSpPr')
                editor.ET.SubElement(nv, '{' + editor.NS['p'] + '}cNvPr', id=str(i), name='shape-' + str(i))
                body = editor.ET.SubElement(shape, '{' + editor.NS['p'] + '}txBody')
                for words__ in words_.split('\n'):
                    para = editor.ET.SubElement(body, '{' + editor.NS['a'] + '}p')
                    run = editor.ET.SubElement(para, '{' + editor.NS['a'] + '}r')
                    editor.ET.SubElement(run, '{' + editor.NS['a'] + '}t').text = words__
            archive.writestr('ppt/slides/' + part, editor.ET.tostring(slide))
        archive.writestr('customXml/preserve.xml', '<preserved>untouched</preserved>')
    basis = root / 'inputs/lesson.txt'
    basis.write_text('P001: 观察边数与对边，再认识长方形。\nP002: 独立算周长。', encoding='utf-8')
    evidence = root / 'inputs/request.json'
    instruction = 'Synthetic instruction: add classroom animations to this synthetic deck.'
    state.write_json(evidence, {'user_instruction': instruction})
    plan = {'schema_version': 'classroom_animation_v1', 'mode': 'classroom',
            'source_deck': 'inputs/source.pptx', 'source_sha256': editor.sha256(source),
            'source_versions': {str(p.relative_to(root).as_posix()): editor.sha256(p)
                                for p in (source, basis, evidence)},
            'output': 'editable/classroom.pptx', 'mapping': {'P001': 1, 'P002': 2},
            'request': {'user_instruction': instruction,
                        'evidence_ref': {'path': 'inputs/request.json', 'sha256': editor.sha256(evidence)}},
            'pages': [page('P001', [unit('feature1', 3, '有四条边', paragraph=0),
                                  unit('feature2', 3, '对边相等', paragraph=1),
                                  unit('name', 4, '长方形')],
                           [step('observe', action('feature1')),
                            step('compare', action('feature2')),
                            step('name', action('name'))]),
                      page('P002', [], [], static_reason='Keep the problem visible for independent calculation')]}
    return root, plan


def unit(uid, sid, text, paragraph=None, **extra):
    target = {'shape_id': sid, 'expected_text': text}
    if paragraph is not None:
        target['paragraph'] = paragraph
    return {'unit_id': uid, 'role': 'explanation', 'kind': 'text', 'purpose': 'explanation',
            'initial_visible': False, 'targets': [target], **extra}


def action(uid, effect='appear', trigger='on_click', **extra):
    return {'unit_id': uid, 'effect': effect, 'trigger': trigger, **extra}


def step(sid, *actions):
    return {'step_id': sid, 'pause_reason': 'Students explain what they observed', 'actions': list(actions)}


def page(pid, units, steps, **extra):
    return {'page_id': pid, 'teaching_goal': 'Observe properties and explain the conclusion',
            'student_action': 'Observe, compare, explain',
            'basis': {'path': 'inputs/lesson.txt', 'locator': pid},
            'initial_reason': 'The observation material and question are already visible',
            'units': units, 'steps': steps, 'existing_policy': 'reject_conflicts', **extra}


def patch_source(root, plan, change):
    source = root / plan['source_deck']
    parts = editor._parts(source)
    slides = editor._slides(parts)
    change(parts, slides)
    with zipfile.ZipFile(source, 'w') as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    plan['source_sha256'] = plan['source_versions'][plan['source_deck']] = editor.sha256(source)


class ClassroomAnimationTests(unittest.TestCase):
    def test_inspection_uses_relationship_order_and_exact_paragraph_text(self):
        api = module(self)
        root, plan = fixture()
        report = api.inspect(root / plan['source_deck'])
        self.assertEqual([p['part'] for p in report['slides']], ['ppt/slides/slide2.xml', 'ppt/slides/slide1.xml'])
        self.assertEqual(report['slides'][0]['objects'][1]['paragraphs'], ['有四条边', '对边相等'])

    def test_paragraph_steps_build_recover_and_recompute_without_office(self):
        api = module(self)
        root, plan = fixture()
        original = (root / plan['source_deck']).read_bytes()
        report = api.build(root, plan)
        self.assertTrue(report['ready_for_review'])
        self.assertNotIn('ready_for_final', report)
        self.assertEqual(report['playback'], 'unverified')
        self.assertEqual([s['visible_units'] for s in report['pages'][0]['states']],
                         [[], ['feature1'], ['feature1', 'feature2'], ['feature1', 'feature2', 'name']])
        self.assertEqual(api.build(root, plan)['output_sha256'], report['output_sha256'])
        self.assertTrue(api.validate_final(root, {'path': report['manifest'],
                                                'sha256': report['manifest_sha256']})['idempotent'])
        self.assertEqual((root / plan['source_deck']).read_bytes(), original)
        parts = editor._parts(root / plan['source_deck'])
        output = editor._parts(root / report['output'])
        for name, data in parts.items():
            if name != editor._slides(parts)[0]:
                self.assertEqual(output[name], data, name)

    def test_check_rejects_empty_click_and_does_not_write(self):
        api = module(self)
        root, plan = fixture()
        plan['pages'][0]['steps'][0]['actions'] = []
        before = sorted(p.relative_to(root).as_posix() for p in root.rglob('*'))
        with self.assertRaisesRegex(ValueError, 'P001.*observe.*empty|P001.*observe.*nonempty'):
            api.check(root, plan)
        self.assertEqual(before, sorted(p.relative_to(root).as_posix() for p in root.rglob('*')))

    def test_repeated_enter_is_rejected_in_page_step_context(self):
        api = module(self)
        root, plan = fixture()
        plan['pages'][0]['steps'].append(step('again', action('name')))
        with self.assertRaisesRegex(ValueError, 'P001.*again.*visible'):
            api.check(root, plan)

    def test_request_text_must_exist_in_locked_evidence(self):
        api = module(self)
        root, plan = fixture()
        plan['request']['user_instruction'] = 'Fabricated approval that is absent from evidence'
        with self.assertRaisesRegex(ValueError, 'instruction.*evidence'):
            api.check(root, plan)

    def test_ownership_and_paragraph_bounds_are_real(self):
        api = module(self)
        for mutation, expected in [
            (lambda p: p['units'][0]['targets'][0].update(paragraph=5), 'paragraph'),
            (lambda p: p['units'].append(unit('whole', 3, '有四条边\n对边相等', initial_visible=True)), 'overlap'),
            (lambda p: p['units'][0]['targets'][0].update(shape_id=999), 'shape'),
            (lambda p: p['units'][0]['targets'][0].update(expected_text='wrong'), 'text')]:
            with self.subTest(expected=expected):
                root, plan = fixture()
                mutation(plan['pages'][0])
                with self.assertRaisesRegex(ValueError, expected):
                    api.check(root, plan)

    def test_unknown_and_missing_fields_fail_closed(self):
        api = module(self)
        for mutate in [lambda p: p.update(automatic_approval=True),
                       lambda p: p['pages'][0]['steps'][0]['actions'][0].update(trigger='onClick'),
                       lambda p: p['pages'][0]['units'][0].pop('initial_visible'),
                       lambda p: p['pages'][0]['units'][0]['targets'][0].pop('expected_text'),
                       lambda p: p['pages'][1].pop('static_reason')]:
            with self.subTest(mutate=mutate):
                root, plan = fixture()
                mutate(plan)
                with self.assertRaises(ValueError):
                    api.check(root, plan)

    def test_state_switch_and_text_emphasis_are_cumulative(self):
        api = module(self)
        root, plan = fixture()
        plan['pages'][0] = page('P001', [unit('old', 3, '有四条边\n对边相等', initial_visible=True),
                                       unit('new', 4, '长方形')],
                               [step('replace', action('old', 'disappear'),
                                     action('new', 'fade', 'with_previous')),
                                step('focus', action('new', 'emphasize')),
                                step('restore', action('new', 'fade_out'),
                                     action('old', 'appear', 'after_previous'))])
        report = api.build(root, plan)
        self.assertEqual([s['visible_units'] for s in report['pages'][0]['states']],
                         [['old'], ['new'], ['new'], ['old']])

    def test_logical_fraction_split_requires_notation_objective(self):
        api = module(self)
        root, plan = fixture()
        plan['pages'][0] = page('P001', [unit('numerator', 3, '有四条边\n对边相等', kind='fraction',
                                            purpose='answer', logical_id='fraction-one-half'),
                                       unit('denominator', 4, '长方形', kind='fraction',
                                            purpose='answer', logical_id='fraction-one-half')],
                               [step('top', action('numerator')), step('bottom', action('denominator'))])
        with self.assertRaisesRegex(ValueError, 'fraction|logical'):
            api.check(root, plan)
        for value in plan['pages'][0]['units']:
            value.update(purpose='notation_instruction', objective='Teach notation in writing order')
        self.assertTrue(api.check(root, plan)['ready_for_review'])

    def test_source_and_manifest_tampering_never_recertifies(self):
        api = module(self)
        root, plan = fixture()
        report = api.build(root, plan)
        manifest = root / report['manifest']
        data = state.read_json(manifest)
        data['pages'][0]['states'][0]['visible_units'] = ['name']
        state.write_json(manifest, data)
        with self.assertRaisesRegex(ValueError, 'Manifest.*pages'):
            api.validate_final(root, report['manifest'])
        (root / 'inputs/lesson.txt').write_text('Changed source', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Source hash changed'):
            api.check(root, plan)

    def test_tampered_output_fails_even_if_manifest_hash_is_rewritten(self):
        api = module(self)
        root, plan = fixture()
        report = api.build(root, plan)
        output = root / report['output']
        parts = editor._parts(output)
        first = editor._slides(parts)[0]
        slide = editor._parse(parts[first])
        slide.find('.//p:timing//p:spTgt', editor.NS).set('spid', '2')
        parts[first] = editor.ET.tostring(slide)
        with zipfile.ZipFile(output, 'w') as archive:
            for name, data in parts.items():
                archive.writestr(name, data)
        manifest = root / report['manifest']
        record = state.read_json(manifest)
        record['output_sha256'] = editor.sha256(output)
        state.write_json(manifest, record)
        changed = output.read_bytes()
        with self.assertRaisesRegex(ValueError, 'timing differs'):
            api.validate_final(root, report['manifest'])
        with self.assertRaisesRegex(ValueError, 'timing differs'):
            api.build(root, plan)
        self.assertEqual(output.read_bytes(), changed)

    def test_partial_attempt_recovery_and_foreign_output_protection(self):
        api = module(self)
        root, plan = fixture()
        original = api._write_new

        def interrupt(path, value):
            if path.name.endswith('.manifest.json'):
                raise OSError('Synthetic interruption before manifest creation')
            return original(path, value)

        with patch.object(api, '_write_new', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'Synthetic interruption'):
                api.build(root, plan)
        output = root / plan['output']
        before = output.read_bytes()
        recovered = api.build(root, plan)
        self.assertTrue(recovered['recovered_output'])
        self.assertEqual(output.read_bytes(), before)
        changed_plan = copy.deepcopy(plan)
        changed_plan['pages'][0]['steps'][0]['pause_reason'] = 'Different teaching plan'
        with self.assertRaisesRegex(ValueError, 'Existing plan differs'):
            api.build(root, changed_plan)
        root2, plan2 = fixture()
        foreign = root2 / plan2['output']
        foreign.write_bytes(b'User-owned file')
        with self.assertRaisesRegex(ValueError, 'lacks immutable plan'):
            api.build(root2, plan2)
        self.assertEqual(foreign.read_bytes(), b'User-owned file')

    def test_existing_nonconflicting_sequence_requires_explicit_append(self):
        api = module(self)
        from runtime.classroom_timing import compile_timing
        root, plan = fixture()
        timing = compile_timing(None, [step('retained', action('old'))],
                                {'old': unit('old', 2, '观察图形')})

        def add_timing(parts, slides):
            tree = editor._parse(parts[slides[0]])
            tree.append(timing)
            parts[slides[0]] = editor.ET.tostring(tree)
            parts['ppt/media/retained-video.bin'] = b'Synthetic retained video payload'
        patch_source(root, plan, add_timing)
        with self.assertRaisesRegex(ValueError, 'append_after_existing'):
            api.check(root, plan)
        plan['pages'][0].update(existing_policy='append_after_existing',
                                existing_reason='Existing first reveal is already part of the lesson')
        report = api.build(root, plan)
        before = editor._parts(root / plan['source_deck'])
        after = editor._parts(root / report['output'])
        self.assertEqual(after['ppt/media/retained-video.bin'], before['ppt/media/retained-video.bin'])
        prior = editor._parse(before[editor._slides(before)[0]])
        later = editor._parse(after[editor._slides(after)[0]])
        original_group = prior.find(".//p:cTn[@nodeType='mainSeq']/p:childTnLst/p:par", editor.NS)
        output_group = later.find(".//p:cTn[@nodeType='mainSeq']/p:childTnLst/p:par", editor.NS)
        self.assertEqual(editor._xml_value(original_group), editor._xml_value(output_group))
        plan['pages'][0]['units'].append(unit('conflict', 2, '观察图形', initial_visible=True))
        with self.assertRaisesRegex(ValueError, 'existing animation ownership conflict'):
            api.check(root, plan)

    def test_group_target_and_hidden_descendant_checks(self):
        api = module(self)
        root, plan = fixture()

        def group_shapes(parts, slides):
            tree = editor._parse(parts[slides[0]])
            shapes = tree.find('p:cSld/p:spTree', editor.NS)
            group = editor.ET.SubElement(shapes, '{' + editor.NS['p'] + '}grpSp')
            nv = editor.ET.SubElement(group, '{' + editor.NS['p'] + '}nvGrpSpPr')
            editor.ET.SubElement(nv, '{' + editor.NS['p'] + '}cNvPr', id='10', name='Logical group')
            for shape in list(shapes)[:2]:
                group.append(shape)
            parts[slides[0]] = editor.ET.tostring(tree)
        patch_source(root, plan, group_shapes)
        plan['pages'][0] = page('P001', [unit('group', 10, None, kind='group')], [step('reveal', action('group'))])
        self.assertTrue(api.build(root, plan)['ready_for_review'])
        plan['pages'][0]['units'].append(unit('child', 2, '观察图形', initial_visible=True))
        with self.assertRaisesRegex(ValueError, 'overlap'):
            api.check(root, plan)
        plan['pages'][0]['units'].pop()

        def hide_child(parts, slides):
            tree = editor._parse(parts[slides[0]])
            tree.find('.//p:cNvPr[@id="2"]', editor.NS).set('hidden', '1')
            parts[slides[0]] = editor.ET.tostring(tree)
        patch_source(root, plan, hide_child)
        with self.assertRaisesRegex(ValueError, 'hidden source'):
            api.check(root, plan)

    def test_fraction_components_in_one_unit_share_one_click(self):
        api = module(self)
        root, plan = fixture()
        fraction = unit('fraction', 3, '有四条边\n对边相等', kind='fraction', purpose='answer', logical_id='one-half')
        fraction['targets'].append({'shape_id': 4, 'expected_text': '长方形'})
        plan['pages'][0] = page('P001', [fraction], [step('answer', action('fraction'))])
        report = api.build(root, plan)
        self.assertEqual(report['pages'][0]['click_count'], 1)
        output = editor._parts(root / report['output'])
        slide = editor._parse(output[editor._slides(output)[0]])
        group = slide.find(".//p:cTn[@nodeType='mainSeq']/p:childTnLst/p:par", editor.NS)
        self.assertEqual({t.get('spid') for t in group.findall('.//p:spTgt', editor.NS)}, {'3', '4'})

    def test_same_unit_simultaneous_transition_is_rejected(self):
        api = module(self)
        root, plan = fixture()
        plan['pages'][0] = page('P001', [unit('u', 4, '长方形', initial_visible=True)],
                               [step('replace', action('u', 'fade_out'), action('u', 'fade', 'with_previous'))])
        with self.assertRaisesRegex(ValueError, 'overlapping actions'):
            api.check(root, plan)
        plan['pages'][0]['steps'][0]['actions'][1]['trigger'] = 'after_previous'
        self.assertTrue(api.check(root, plan)['ready_for_review'])

    def test_invalid_timing_effect_and_directions_fail_closed(self):
        api = module(self)
        for fields in [{'delay_ms': 2001}, {'duration_ms': True}, {'duration_ms': 5001},
                       {'effect': 'motion_path'}, {'effect': 'wipe'}, {'effect': 'wipe', 'direction': 'diagonal'},
                       {'effect': 'appear', 'scale': 1.25}]:
            with self.subTest(fields=fields):
                root, plan = fixture()
                plan['pages'][0]['steps'][0]['actions'][0].update(fields)
                with self.assertRaises(ValueError):
                    api.check(root, plan)

    def test_zero_animation_page_retains_entire_source_bytes(self):
        api = module(self)
        root, plan = fixture()
        plan['pages'][0] = page('P001', [unit('visible', 2, '观察图形', initial_visible=True)], [],
                               static_reason='All observation material stays visible')
        report = api.build(root, plan)
        self.assertEqual((root / report['output']).read_bytes(), (root / plan['source_deck']).read_bytes())

    def test_static_snapshot_projects_known_paragraph_states_in_separate_copy(self):
        api = module(self)
        self.assertTrue(callable(getattr(api, 'snapshot', None)), 'Known static states need a separate, honest export copy')
        root, plan = fixture()
        report = api.build(root, plan)
        classroom = (root / report['output']).read_bytes()
        snap = api.snapshot(root, report['manifest'], 'editable/initial-static.pptx', stage='initial')
        projected = editor._parts(root / snap['output'])
        source = editor._parts(root / plan['source_deck'])
        slide = editor._parse(projected[editor._slides(projected)[0]])
        self.assertEqual(editor._text(next(n for n in editor._shape_nodes(slide)
                                          if editor._identity(n).get('id') == '3')), '\n')
        self.assertNotIn('4', [editor._identity(n).get('id') for n in editor._shape_nodes(slide)])
        self.assertIsNone(slide.find('p:timing', editor.NS))
        self.assertEqual(projected[editor._slides(projected)[1]], source[editor._slides(source)[1]])
        self.assertEqual((root / report['output']).read_bytes(), classroom)
        self.assertEqual(snap['stage'], 'initial')
        self.assertEqual(snap['projected_pages'], ['P001'])
        self.assertEqual(api.snapshot(root, report['manifest'], 'editable/initial-static.pptx', 'initial')['output_sha256'],
                         snap['output_sha256'])

    def test_static_final_snapshot_rejects_unknown_emphasis_fonts(self):
        api = module(self)
        self.assertTrue(callable(getattr(api, 'snapshot', None)), 'Snapshot limits must be enforced')
        root, plan = fixture()
        plan['pages'][0]['steps'].append(step('focus', action('name', 'emphasize')))
        report = api.build(root, plan)
        with self.assertRaisesRegex(ValueError, 'emphasis'):
            api.snapshot(root, report['manifest'], 'editable/final-static.pptx')

    def test_source_race_does_not_emit_manifest(self):
        api = module(self)
        root, plan = fixture()
        original = api._verify

        def drift(context, candidate):
            (root / 'inputs/lesson.txt').write_text('Changed during verification', encoding='utf-8')
            return original(context, candidate)
        with patch.object(api, '_verify', side_effect=drift):
            with self.assertRaisesRegex(ValueError, 'Source hash changed'):
                api.build(root, plan)
        self.assertFalse((root / plan['output']).with_suffix('.manifest.json').exists())

    def test_json_wrong_types_are_validation_errors_not_internal_exceptions(self):
        api = module(self)
        mutations = [lambda p: p.update(source_deck=[]),
                     lambda p: p['request']['evidence_ref'].update(path=[]),
                     lambda p: p['pages'][0].update(page_id={}),
                     lambda p: p['pages'][0]['basis'].update(path=[]),
                     lambda p: p['pages'][0].update(existing_policy=[]),
                     lambda p: p['pages'][0]['units'][0].update(role=[]),
                     lambda p: p['pages'][0]['units'][0].update(kind=[]),
                     lambda p: p['pages'][0]['steps'][0]['actions'][0].update(effect=[]),
                     lambda p: p['pages'][0]['steps'][0]['actions'][0].update(trigger=[]),
                     lambda p: p['pages'][0]['steps'][0]['actions'][0].update(effect='wipe', direction=[])]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                root, plan = fixture()
                mutate(plan)
                with self.assertRaises(ValueError):
                    api.check(root, plan)

    def test_snapshot_rejects_preexisting_timing_and_tampered_copy(self):
        api = module(self)
        root, plan = fixture()
        report = api.build(root, plan)
        snapshot = api.snapshot(root, report['manifest'], 'editable/static.pptx')
        (root / snapshot['output']).write_bytes(b'Changed by a human')
        with self.assertRaisesRegex(ValueError, 'do not overwrite'):
            api.snapshot(root, report['manifest'], 'editable/static.pptx')
        from runtime.classroom_timing import compile_timing
        root, plan = fixture()

        def add_timing(parts, slides):
            slide = editor._parse(parts[slides[0]])
            slide.append(compile_timing(None, [step('existing', action('old'))],
                                        {'old': unit('old', 2, '观察图形')}))
            parts[slides[0]] = editor.ET.tostring(slide)
        patch_source(root, plan, add_timing)
        plan['pages'][0].update(existing_policy='append_after_existing', existing_reason='Retain introduction click')
        report = api.build(root, plan)
        with self.assertRaisesRegex(ValueError, 'pre-existing animation states'):
            api.snapshot(root, report['manifest'], 'editable/static.pptx')


if __name__ == '__main__':
    unittest.main()
