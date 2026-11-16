"""Read-only native timing evidence; synthetic XML is not a playback test."""
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import uuid
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/math-courseware-studio/scripts'))
from runtime import classroom_animation, pptx_editor as editor

P = editor.NS['p']
A = editor.NS['a']
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'


def api(test):
    test.assertIsNotNone(importlib.util.find_spec('runtime.classroom_inspect'),
                         'Inspection must preserve native timing evidence without simulating playback')
    return importlib.import_module('runtime.classroom_inspect')


def slide(children='', extra='', shapes=''):
    return editor._parse((f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:m="{M}" xmlns:x="urn:unknown">'
                         '<p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="2" name="equation"/>'
                         '</p:nvSpPr><p:txBody><a:p><a:r><a:t>第一行</a:t></a:r></a:p>'
                         '<a:p><a:r><a:t>分数：</a:t></a:r><m:oMath><m:f><m:num><m:r><m:t>1</m:t>'
                         '</m:r></m:num><m:den><m:r><m:t>2</m:t></m:r></m:den></m:f></m:oMath>'
                         '<a:r><a:t>，完整公式保留。</a:t></a:r></a:p></p:txBody></p:sp>' + shapes +
                         '</p:spTree></p:cSld><p:timing><p:tnLst><p:par>'
                         '<p:cTn id="1" nodeType="tmRoot" dur="indefinite"><p:stCondLst>'
                         '<p:cond delay="0"/></p:stCondLst><p:childTnLst>' + children +
                         '</p:childTnLst></p:cTn></p:par></p:tnLst>' + extra + '</p:timing></p:sld>').encode())


def behavior(tid, target='', kind='set', attributes='', payload=''):
    return (f'<p:{kind} {attributes}><p:cBhvr><p:cTn id="{tid}" dur="1">'
            '<p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn><p:tgtEl><p:spTgt spid="2">' +
            target + '</p:spTgt></p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName>'
            '</p:attrNameLst></p:cBhvr>' + payload + f'</p:{kind}>')


def main_sequence(content):
    return ('<p:seq concurrent="1" nextAc="seek"><p:cTn id="10" nodeType="mainSeq">'
            '<p:childTnLst>' + content + '</p:childTnLst></p:cTn><p:prevCondLst>'
            '<p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond>'
            '</p:prevCondLst><p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl>'
            '<p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq>')


def chain_id(action, tid):
    return next(n for n in action['ancestor_chain'] if n['attributes'].get('id') == str(tid))


class ClassroomInspectTests(unittest.TestCase):
    def test_parent_delays_are_preserved_with_all_ancestor_conditions(self):
        branches = []
        for i, delay in enumerate((0, 500, 1000, 1500)):
            pid, eid, bid = 30 + i * 3, 31 + i * 3, 32 + i * 3
            branches.append(f'<p:par><p:cTn id="{pid}"><p:stCondLst><p:cond delay="{delay}"/>'
                            f'</p:stCondLst><p:childTnLst><p:par><p:cTn id="{eid}" nodeType="afterEffect">'
                            '<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>' +
                            behavior(bid) + '</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>')
        grouped = ('<p:par><p:cTn id="20"><p:stCondLst><p:cond delay="indefinite"/>'
                   '<p:cond evt="onEnd" delay="500"><p:tn val="9"/></p:cond></p:stCondLst>'
                   '<p:endCondLst><p:cond delay="2000"/></p:endCondLst><p:childTnLst>' +
                   ''.join(branches) + '</p:childTnLst></p:cTn></p:par>')
        root = slide(main_sequence(grouped))
        before = editor.ET.tostring(root)
        result = api(self).inspect_timing(root)
        self.assertEqual(len(result['actions']), 4)
        for i, action in enumerate(result['actions']):
            parent = chain_id(action, 30 + i * 3)
            self.assertEqual(parent['condition_lists'][0]['conditions'][0]['delay_ms'], i * 500)
            local = chain_id(action, 31 + i * 3)
            self.assertEqual(local['condition_lists'][0]['conditions'][0]['delay_ms'], 0)
            outer = chain_id(action, 20)
            self.assertEqual([c['kind'] for c in outer['condition_lists']], ['stCondLst', 'endCondLst'])
            self.assertEqual(len(outer['condition_lists'][0]['conditions']), 2)
            self.assertEqual(outer['condition_lists'][0]['conditions'][0]['delay_kind'], 'indefinite')
            self.assertIn('<p:tn val="9"', outer['condition_lists'][0]['conditions'][1]['xml'])
            seq = next(n for n in action['ancestor_chain'] if n['type'] == 'seq')
            self.assertEqual([c['kind'] for c in seq['condition_lists']], ['prevCondLst', 'nextCondLst'])
            self.assertNotIn('start_ms', action)
        self.assertEqual(result['resolution'], 'not_simulated')
        self.assertEqual(editor.ET.tostring(root), before)

    def test_root_parallel_initialization_and_direct_interactive_command_are_retained(self):
        initialize = ('<p:par><p:cTn id="3"><p:stCondLst><p:cond delay="0"/></p:stCondLst>'
                      '<p:childTnLst>' + behavior(4, payload='<p:to><p:strVal val="hidden"/></p:to>') +
                      '</p:childTnLst></p:cTn></p:par>')
        interactive = ('<p:seq><p:cTn id="80" nodeType="interactiveSeq" restart="whenNotActive">'
                       '<p:stCondLst><p:cond evt="onClick" delay="0"><p:tgtEl><p:spTgt spid="2"/>'
                       '</p:tgtEl></p:cond></p:stCondLst><p:childTnLst>' +
                       behavior(81, kind='cmd', attributes='type="call" cmd="playFrom(0.0)"') +
                       '</p:childTnLst></p:cTn></p:seq>')
        result = api(self).inspect_timing(slide(initialize + main_sequence('') + interactive))
        self.assertEqual([s['kind'] for s in result['sections']], ['tmRoot_direct_par', 'mainSeq', 'interactiveSeq'])
        self.assertEqual([a['type'] for a in result['actions']], ['set', 'cmd'])
        self.assertEqual(result['sections'][0]['action_paths'], [result['actions'][0]['path']])
        command = result['actions'][1]
        self.assertEqual(command['attributes'], {'type': 'call', 'cmd': 'playFrom(0.0)'})
        self.assertEqual(command['section_path'], result['sections'][2]['path'])
        self.assertEqual(chain_id(command, 80)['condition_lists'][0]['conditions'][0]['attributes']['evt'], 'onClick')
        self.assertIn('val="hidden"', result['actions'][0]['xml'])

    def test_complete_motion_keyframes_math_and_paragraph_range_have_source_locators(self):
        path = 'M 0 0 ' + 'L 0.123456789 0.987654321 ' * 80 + 'E'
        keyframes = ''.join(f'<p:tav tm="{t}"><p:val><p:fltVal val="{t / 100000}"/></p:val></p:tav>'
                            for t in (0, 10000, 30000, 50000, 75000, 100000))
        target = '<p:txEl><p:pRg st="0" end="1"/></p:txEl>'
        content = behavior(41, target, 'animMotion', f'path="{path}" origin="layout"')
        content += behavior(42, target, 'anim', 'calcmode="lin" valueType="num"',
                             '<p:tavLst>' + keyframes + '</p:tavLst>')
        root = slide(main_sequence(content))
        result = api(self).inspect_timing(root)
        motion, animation = result['actions']
        self.assertEqual(motion['attributes']['path'], path)
        self.assertIn(path, motion['xml'])
        self.assertEqual(len(editor._parse(animation['xml'].encode()).findall('p:tavLst/p:tav', editor.NS)), 6)
        self.assertEqual(animation['attribute_names'], ['style.visibility'])
        target_info = motion['targets'][0]
        self.assertEqual(target_info['paragraph_range'], {'start': 0, 'end': 1})
        self.assertEqual(target_info['resolution'], 'bound_paragraphs')
        self.assertEqual(target_info['paragraph_text'], ['第一行', '分数：12，完整公式保留。'])
        paragraph = result['text_evidence'][0]['paragraphs'][1]
        self.assertEqual(paragraph['text'], '分数：12，完整公式保留。')
        math = editor._parse(paragraph['math_xml'][0].encode())
        self.assertEqual(math.find('.//m:num/m:r/m:t', {'m': M}).text, '1')
        self.assertEqual(math.find('.//m:den/m:r/m:t', {'m': M}).text, '2')
        for action in result['actions']:
            self.assertEqual(len(root.getroottree().xpath(action['path'], namespaces=editor.NS)), 1)
        json.dumps(result, ensure_ascii=False)

    def test_unknown_conditions_and_special_targets_are_unresolved_not_zero_delay(self):
        content = ('<p:par><p:cTn id="20"><p:stCondLst><p:cond delay="mystery"/>'
                   '<p:cond evt="unknownEvent"/></p:stCondLst><p:childTnLst>' +
                   behavior(21, '<p:txEl><p:pRg st="4294967295" end="4294967295"/></p:txEl>') +
                   '<x:futureTiming custom="keep-everything"><x:value>whole value</x:value></x:futureTiming>'
                   '</p:childTnLst></p:cTn></p:par>')
        result = api(self).inspect_timing(slide(main_sequence(content)))
        conds = chain_id(result['actions'][0], 20)['condition_lists'][0]['conditions']
        self.assertEqual([c['delay_kind'] for c in conds], ['unresolved', 'unspecified'])
        self.assertTrue(all(c['delay_ms'] is None for c in conds))
        self.assertEqual(result['actions'][0]['targets'][0]['resolution'], 'unresolved')
        reasons = [u['reason'] for u in result['unresolved']]
        self.assertIn('unsupported_delay', reasons)
        self.assertIn('unspecified_delay', reasons)
        self.assertIn('unsupported_event', reasons)
        self.assertIn('unsupported_element', reasons)
        self.assertIn('special_or_out_of_range_paragraph', reasons)
        self.assertIn('whole value', result['xml'])

    def test_inspect_integration_keeps_legacy_fields_and_marks_evidence_not_playback(self):
        root = Path(__file__).parent / 'runs' / ('classroom-inspect-' + uuid.uuid4().hex)
        root.mkdir()
        (root / 'AGENTS.md').write_text('# Synthetic inspection fixture\n'
                                      'Retain the generated deck and all evidence. No real course or playback verification.\n',
                                      encoding='utf-8')
        source = root / 'source.pptx'
        with zipfile.ZipFile(source, 'w') as archive:
            archive.writestr('ppt/presentation.xml', f'<p:presentation xmlns:p="{P}" xmlns:r="{editor.NS["r"]}">'
                             '<p:sldIdLst><p:sldId id="256" r:id="rId1"/><p:sldId id="257" r:id="rId2"/>'
                             '</p:sldIdLst></p:presentation>')
            archive.writestr('ppt/_rels/presentation.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                             '<Relationship Id="rId1" Target="slides/slide2.xml"/><Relationship Id="rId2" Target="slides/slide1.xml"/>'
                             '</Relationships>')
            archive.writestr('ppt/slides/slide2.xml', editor.ET.tostring(slide(main_sequence(behavior(41)))))
            plain = slide()
            plain.remove(plain.find('p:timing', editor.NS))
            archive.writestr('ppt/slides/slide1.xml', editor.ET.tostring(plain))
            archive.writestr('ppt/media/unchanged.bin', b'unchanged')
        before = source.read_bytes()
        result = classroom_animation.inspect(source)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(result['playback'], 'unverified')
        self.assertEqual([s['part'] for s in result['slides']], ['ppt/slides/slide2.xml', 'ppt/slides/slide1.xml'])
        first, plain = result['slides']
        self.assertTrue({'objects', 'has_existing_timing', 'existing_targets', 'timing_sha256',
                         'existing_interactive_sequences'} <= first.keys())
        self.assertEqual(first['objects'][0]['paragraphs'], ['第一行', '分数：12，完整公式保留。'])
        self.assertEqual(first['existing_targets'], [{'shape_id': 2}])
        self.assertEqual(first['timeline']['evidence'], 'readonly_xml')
        self.assertEqual(first['timeline']['playback'], 'unverified')
        self.assertEqual(plain['timeline']['actions'], [])
        self.assertEqual(plain['timeline']['sections'], [])
        self.assertIsNone(plain['timeline']['xml'])


if __name__ == '__main__':
    unittest.main()
