"""Behavioral checks for real glyph containment and reusable blackboard rendering."""
from pathlib import Path
import hashlib
import importlib.util
import json
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from PIL import Image, ImageChops, ImageFilter

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'skills/math-courseware-studio/scripts/runtime/blackboard.py'
FONT=ROOT/'skills/math-courseware-studio/assets/blackboard/fonts/LXGWZhenKaiGB-Regular.ttf'


@contextmanager
def preserved_case():
    base=ROOT/'tests/runs/blackboard-skill-20260924/outputs/unit-cases'
    base.mkdir(parents=True,exist_ok=True)
    yield Path(tempfile.mkdtemp(prefix='case-',dir=base))


class BlackboardTests(unittest.TestCase):
    def engine(self):
        self.assertTrue(MODULE.is_file(),'Reusable blackboard renderer is not implemented yet')
        spec=importlib.util.spec_from_file_location('blackboard_under_test',MODULE)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_visible_glyphs_fit_curved_backing(self):
        engine=self.engine()
        for text in ['乘数','乘号','积','相同加数的个数']:
            with self.subTest(text=text):
                image,meta,masks=engine.pill(text,FONT,'pink',oval=True,size=180)
                self.assertIsNone(ImageChops.subtract(masks['glyph'],masks['safe']).getbbox())
                self.assertGreater(meta['safe_inset'],10)
                self.assertGreater(meta['glyph_pixels'],100)
                self.assertLess(meta['text_height_fraction'],0.7)
                self.assertEqual(image.getpixel((0,0))[3],0)

    def fixture(self,folder):
        source=folder/'source.txt';source.write_text('P1 平均分\nP2 12个苹果平均放入3盘\nP3 每份同样多\n',encoding='utf-8')
        spec={'title':'平均分','sources':[{'id':'lesson','path':'source.txt','sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'page_count':3}],
              'assets':[{'id':'keyword','name':'平均分','kind':'word','role':'display','text':'平均分','color':'pink','source_refs':[{'source_id':'lesson','pages':[1]}],'purpose':'课题词'},
                        {'id':'term','name':'每份同样多','kind':'pill','role':'explanation','text':'每份同样多','color':'yellow','params':{'oval':True},'source_refs':[{'source_id':'lesson','pages':[3]}],'purpose':'核心方法'}],
              'boards':[{'name':'核心板书','items':[{'id':'keyword','box':[100,60,1100,150]},{'id':'term','box':[500,450,800,190]}]}]}
        path=folder/'spec.json';path.write_text(json.dumps(spec,ensure_ascii=False),encoding='utf-8');return path,spec

    def test_real_output_transparency_source_binding_and_no_overwrite(self):
        engine=self.engine()
        with preserved_case() as tmp:
            folder=Path(tmp);spec,_=self.fixture(folder);out=folder/'v001'
            result=engine.render(spec,out)
            self.assertEqual(len(result['assets']),2)
            for asset in result['assets']:
                im=Image.open(out/'output'/asset['file'])
                self.assertEqual(im.mode,'RGBA');self.assertEqual(im.getchannel('A').getextrema(),(0,255))
            with self.assertRaises(FileExistsError):engine.render(spec,out)
            (folder/'source.txt').write_text('changed source',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'source|来源|hash'):engine.render(spec,folder/'v002')

    def test_missing_font_or_unsafe_name_is_not_silently_accepted(self):
        engine=self.engine()
        with preserved_case() as tmp:
            folder=Path(tmp);path,spec=self.fixture(folder)
            spec['fonts']={'display':'absent.ttf'}
            path.write_text(json.dumps(spec,ensure_ascii=False),encoding='utf-8')
            with self.assertRaisesRegex((ValueError,FileNotFoundError),'font|字体'):engine.render(path,folder/'missing')
            spec.pop('fonts');spec['assets'][0]['name']='../outside'
            path.write_text(json.dumps(spec,ensure_ascii=False),encoding='utf-8')
            with self.assertRaises(ValueError):engine.render(path,folder/'unsafe')

    def test_unreviewed_mathematical_typo_is_rejected(self):
        engine=self.engine()
        with preserved_case() as tmp:
            folder=Path(tmp);path,spec=self.fixture(folder)
            spec['assets'][0].update(kind='card',role='math',text='4+4+4=13')
            path.write_text(json.dumps(spec,ensure_ascii=False),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'算式|arithmetic'):engine.render(path,folder/'bad-math')

    def test_invalid_style_parameter_fails_before_output(self):
        engine=self.engine()
        with preserved_case() as folder:
            path,spec=self.fixture(folder)
            spec['assets'][0].update(kind='blank',params={'color':'blue'})
            path.write_text(json.dumps(spec,ensure_ascii=False),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'param'):engine.render(path,folder/'invalid-parameter')
            self.assertFalse((folder/'invalid-parameter').exists())

    def test_default_chinese_roles_share_kaiti_and_explicit_fonts_win(self):
        engine=self.engine()
        roles={'title','display','explanation','reading','unit'}
        with preserved_case() as folder:
            system=folder/'system';(system/'Fonts').mkdir(parents=True)
            kaiti=system/'Fonts/simkai.ttf';kaiti.write_bytes(FONT.read_bytes())
            with patch.dict(engine.os.environ,{'WINDIR':str(system)}):
                resolved=engine.resolve_fonts({},folder,roles)
                self.assertEqual(set(resolved.values()),{kaiti})
                explicit=engine.resolve_fonts({'fonts':{'reading':str(FONT)}},folder,roles)
                self.assertEqual(explicit['reading'],FONT)
                self.assertEqual(explicit['title'],kaiti)
            with patch.dict(engine.os.environ,{'WINDIR':str(folder/'missing-system')}):
                with self.assertRaisesRegex(ValueError,'font|字体'):
                    engine.resolve_fonts({},folder,{'title'})

    def assert_cloud_ink_is_supported(self,image):
        opaque_black=Image.new('L',image.size)
        opaque_black.putdata([255 if p==(5,5,5,255) else 0 for p in image.getdata()])
        self.assertIsNotNone(opaque_black.getbbox(),'Expected black lettering/arrow')
        support=image.getchannel('A').filter(ImageFilter.MinFilter(17))
        self.assertIsNone(ImageChops.subtract(opaque_black,support).getbbox(),
                          'Black strokes and line endpoints need complete backing')
        self.assertEqual(image.getpixel((0,0))[3],0)
        self.assertIn((255,255,255,255),image.getdata())

    def test_title_and_keywords_have_black_ink_white_backing_and_colored_edges(self):
        engine=self.engine();engine.FONTS={'title':FONT,'brush':FONT}
        for title,text,color,rgb in [(True,'分数的意义','yellow',(231,179,76,255)),
                                     (False,'平均分','teal',(28,182,190,255))]:
            with self.subTest(title=title):
                image=engine.word(text,color=color,title=title,size=100)
                self.assert_cloud_ink_is_supported(image)
                self.assertIn(rgb,image.getdata())
                self.assertNotIn((255,223,88,255),image.getdata())

    def test_cloud_math_stacks_fractions_keeps_units_and_preserves_anchors(self):
        engine=self.engine();engine.FONTS={'math':Path('C:/Windows/Fonts/arial.ttf'),'sans':FONT}
        fraction=engine.card('3/4=75%',size=100)
        flat=engine.card('75%',size=100)
        self.assertGreater(fraction.height,flat.height*1.35)
        self.assertEqual(fraction.info['fractions'],[{'numerator':'3','denominator':'4'}])
        self.assert_cloud_ink_is_supported(fraction)
        length=engine.card('5/10',unit='米',size=100)
        self.assertEqual(length.info['unit'],'米')
        self.assertEqual(length.info['fractions'],[{'numerator':'5','denominator':'10'}])
        self.assert_cloud_ink_is_supported(length)
        equation=engine.card('3+3+3+3=3×4',size=80)
        tokens=equation.info['anchors']['tokens']
        self.assertEqual([t['text'] for t in tokens],['3','+','3','+','3','+','3','=','3','×','4'])
        centers=[t['center'] for t in tokens]
        self.assertTrue(all(0<a<b<1 for a,b in zip(centers,centers[1:])))
        start,end=equation.info['anchors']['addends']
        self.assertLess(start,end);self.assertLess(end,tokens[7]['center'])
        self.assert_cloud_ink_is_supported(engine.arrow())

    def test_standalone_relation_symbol_remains_a_valid_cloud_card(self):
        engine=self.engine();engine.FONTS={'math':Path('C:/Windows/Fonts/arial.ttf'),'sans':FONT}
        image=engine.card('=',size=100)
        self.assertEqual(image.info['anchors']['tokens'][0]['text'],'=')
        self.assert_cloud_ink_is_supported(image)

    def test_zero_denominator_is_rejected_before_output(self):
        engine=self.engine()
        with preserved_case() as folder:
            path,spec=self.fixture(folder)
            spec['assets'][0].update(kind='card',role='math',text='3/0=75%')
            path.write_text(json.dumps(spec,ensure_ascii=False),encoding='utf8')
            out=folder/'invalid-denominator'
            with self.assertRaisesRegex(ValueError,'denominator|分母'):
                engine.render(path,out)
            self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
