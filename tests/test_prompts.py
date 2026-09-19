from pathlib import Path
import sys
import unittest
import uuid
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
from runtime import state
from workflow_fixture import enable_modules
try:
    from runtime import prompts
except ImportError:
    prompts = None


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(prompts, 'prompt runtime must exist')
        self.root = ROOT / 'tests/runs' / ('prompts-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic test only', 'openai_image_api')
        Image.new('RGB', (32, 18), 'white').save(self.root / 'assets/characters/ref.png')
        file = {'path': 'assets/characters/ref.png', 'sha256': state.sha256(self.root / 'assets/characters/ref.png')}
        for name, data in {
            'math': {'problems': [{'math_id': 'M001', 'answer': 15}]},
            'story': {'visual_style': '半3D卡通，浅蓝底色，楷体，大屏简洁留白', 'events': []},
            'assets': {'assets': [{'asset_id': 'CHAR001', 'version': 'v001', 'fixed_features': '红衣短发男孩', 'files': [file]}]},
            'pages': {'pages': [
                {'page_id': 'P002', 'order': 1, 'title': '数一数', 'layout': '左图右文',
                 'visual_description': '呈现5组苹果，每组3个', 'math_ids': ['M001'],
                 'asset_refs': [{'asset_id': 'CHAR001', 'version': 'v001'}],
                 'text_units': [{'unit_id': 'P002-T01', 'text': '5组，每组3个'}, {'unit_id': 'P002-T02', 'text': '3×5＝15（个）'}]},
                {'page_id': 'P001', 'order': 2, 'title': '小结', 'layout': '中央卡片', 'visual_description': '简洁知识卡',
                 'math_ids': [], 'asset_refs': [], 'text_units': [{'unit_id': 'P001-T01', 'text': '我学会了乘法'}]}]}
        }.items():
            state.write_json(self.root / '_state' / (name + '.json'), data)

    def approve(self):
        paths = ['_state/' + x + '.json' for x in ['math', 'story', 'assets', 'pages']]
        state.record_approval(self.root, {'targets': [{'path': p, 'sha256': state.sha256(self.root / p)} for p in paths],
            'user_evidence': 'Synthetic fixture approval'})
        enable_modules(self.root)

    def test_prompts_keep_exact_words_style_and_stable_page_order(self):
        enable_modules(self.root)
        result = prompts.render_pages(self.root)
        body = (self.root / result['prompts']).read_text(encoding='utf-8')
        self.assertLess(body.index('【页面编号】P002'), body.index('【页面编号】P001'))
        self.assertIn('3×5＝15（个）', body)
        self.assertEqual(body.count('半3D卡通，浅蓝底色，楷体，大屏简洁留白'), 2)
        self.assertIn('红衣短发男孩', body)

    def test_render_blocks_unclassified_scope_before_writes(self):
        with self.assertRaisesRegex(ValueError, 'workflow|Workflow|scope|mode'):
            prompts.render_pages(self.root)
        self.assertFalse((self.root / 'slides/image-prompts.md').exists())

    def test_render_rejects_unknown_story_reference_before_writes(self):
        pages = state.read_json(self.root / '_state/pages.json')
        pages['pages'][0]['story_ids'] = ['MISSING_EVENT']
        state.write_json(self.root / '_state/pages.json', pages)
        enable_modules(self.root)
        with self.assertRaisesRegex(ValueError, 'story|MISSING_EVENT'):
            prompts.render_pages(self.root)
        self.assertFalse((self.root / 'slides/image-prompts.md').exists())
        self.assertFalse((self.root / 'planning/visible-text.md').exists())

    def test_prepare_blocks_unclassified_scope_even_with_approved_records(self):
        paths = ['_state/' + name + '.json' for name in ['math', 'story', 'assets', 'pages']]
        state.record_approval(self.root, {'targets': [
            {'path': path, 'sha256': state.sha256(self.root / path)} for path in paths],
            'user_evidence': 'Synthetic input approval without authorization to start a module'})
        with self.assertRaisesRegex(ValueError, 'workflow|Workflow|scope|mode'):
            prompts.prepare(self.root, {'tasks': [{'purpose': 'page', 'target_id': 'P002'}]})
        self.assertEqual(list((self.root / '_state/jobs').iterdir()), [])

    def test_formal_generation_requires_confirmation_and_real_references(self):
        selection = {'tasks': [{'purpose': 'page', 'target_id': 'P002', 'version': 'v001'}]}
        with self.assertRaises(ValueError):
            prompts.prepare(self.root, selection)
        self.approve()
        batch = prompts.prepare(self.root, selection)
        job = state.read_json(self.root / batch['jobs'][0])
        self.assertEqual(job['references'][0]['sha256'], state.sha256(self.root / 'assets/characters/ref.png'))
        self.assertEqual(job['image_api_input']['model'], 'gpt-image-2.5')
        self.assertTrue(job['image_api_input']['shutProgress'])

    def test_missing_reference_or_unknown_page_cannot_dispatch(self):
        self.approve()
        with self.assertRaises(ValueError):
            prompts.prepare(self.root, {'tasks': [{'purpose': 'page', 'target_id': 'P999'}]})
        data = state.read_json(self.root / '_state/assets.json')
        data['assets'][0]['files'][0]['path'] = 'assets/missing.png'
        state.write_json(self.root / '_state/assets.json', data)
        self.approve()
        with self.assertRaises((ValueError, FileNotFoundError)):
            prompts.prepare(self.root, {'tasks': [{'purpose': 'page', 'target_id': 'P002'}]})

    def test_task_override_cannot_remove_page_reference_assets(self):
        self.approve()
        batch = prompts.prepare(self.root, {'tasks': [{'purpose': 'page', 'target_id': 'P002', 'reference_assets': []}]})
        job = state.read_json(self.root / batch['jobs'][0])
        self.assertEqual(len(job['references']), 1)

    def test_formal_multiline_prompt_payload_uses_saved_bytes(self):
        from runtime import image_api
        self.approve()
        batch = prompts.prepare(self.root, {'tasks': [{'purpose': 'page', 'target_id': 'P002'}]})
        payload = image_api.build_payload(self.root, state.read_json(self.root / batch['jobs'][0]))
        self.assertIn('3×5＝15（个）', payload['prompt'])

    def test_reorder_reuses_same_pending_page_task(self):
        from runtime import image_api
        from test_image_api import Transport
        self.approve()
        selection = {'tasks': [{'purpose': 'page', 'target_id': 'P002'}]}
        original = prompts.prepare(self.root, selection)
        pages = state.read_json(self.root / '_state/pages.json')
        for page in pages['pages']:
            page['order'] = 3 - page['order']
        state.write_json(self.root / '_state/pages.json', pages)
        self.approve()
        again = prompts.prepare(self.root, selection)
        self.assertEqual(original['jobs'], again['jobs'])
        transport = Transport()
        result = image_api.run_job(self.root, again['jobs'][0], transport, timeout=1, poll_interval=0)
        self.assertEqual(result['status'], 'downloaded')

    def test_stale_page_cannot_generate_before_updated_content_approved(self):
        self.approve()
        data = state.load_project(self.root)
        data['stale_targets'] = ['P002']
        state.write_json(self.root / '_state/project.json', data)
        with self.assertRaises(ValueError):
            prompts.prepare(self.root, {'tasks': [{'purpose': 'page', 'target_id': 'P002'}]})

    def test_asset_task_inherits_canonical_reference_assets(self):
        data = state.read_json(self.root / '_state/assets.json')
        data['assets'].append({'asset_id': 'CHAR002', 'version': 'v001', 'fixed_features': '同一男孩侧面',
                               'reference_assets': [{'asset_id': 'CHAR001', 'version': 'v001'}], 'files': []})
        state.write_json(self.root / '_state/assets.json', data)
        self.approve()
        batch = prompts.prepare(self.root, {'tasks': [{'purpose': 'asset', 'target_id': 'CHAR002',
                                                       'prompt': '生成同一男孩侧面设定图'}]})
        job = state.read_json(self.root / batch['jobs'][0])
        self.assertEqual(len(job['references']), 1)
        self.assertIn('_state/assets.json', job['input_versions'])


if __name__ == '__main__':
    unittest.main()
