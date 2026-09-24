"""Behavioral checks for real glyph containment and reusable blackboard rendering."""
from pathlib import Path
import hashlib
import importlib.util
import json
import tempfile
import unittest
from contextlib import contextmanager
from PIL import Image, ImageChops

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


if __name__=='__main__':unittest.main()
