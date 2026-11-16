"""API reference selection uses synthetic local images; no provider calls."""
import base64
from pathlib import Path
import sys
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
from runtime import state, prompts, image_api
import test_prompts as prompt_fixture
from workflow_fixture import enable_modules


class ApiReferenceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = prompt_fixture.PromptTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        data = state.read_json(self.root / '_state/assets.json')
        character = data['assets'][0]
        character['kind'] = 'character'
        character['files'][0]['view'] = 'front'
        character['files'].append(self.image('assets/characters/side.png', 'red', view='side'))
        data['assets'].append({'asset_id': 'SCENE001', 'version': 'v001', 'kind': 'scene',
            'fixed_features': '教室左窗右门', 'files': [self.image('assets/scene.png', 'blue', view='wide')]})
        state.write_json(self.root / '_state/assets.json', data)
        self.fixture.approve()

    def image(self, path, color, **metadata):
        Image.new('RGB', (32, 18), color).save(self.root / path)
        return {'path': path, 'sha256': state.sha256(self.root / path), **metadata}

    def prepare(self, task=None, **selection):
        task = {'purpose': 'page', 'target_id': 'P002', **(task or {})}
        batch = prompts.prepare(self.root, {'tasks': [task], **selection})
        return batch, state.read_json(self.root / batch['jobs'][0])

    def asset_data(self, data):
        state.write_json(self.root / '_state/assets.json', data)
        self.fixture.approve()

    def builtin(self):
        project = state.load_project(self.root)
        project['image_route'] = 'builtin'
        state.write_json(self.root / '_state/project.json', project)

    def test_selected_view_replaces_default_set_and_payload_contains_selected_bytes(self):
        _, job = self.prepare({'reference_assets': [dict(asset_id='CHAR001', version='v001', views=['side'])]})
        self.assertEqual([r['view'] for r in job['references']], ['side'])
        payload = image_api.build_payload(self.root, job)
        self.assertEqual(base64.b64decode(payload['urls'][0].split(',', 1)[1]),
                         (self.root / 'assets/characters/side.png').read_bytes())
        self.assertIn('图1', payload['prompt'])
        self.assertIn('CHAR001', payload['prompt'])
        self.assertIn('side', payload['prompt'])
        self.assertIn('红衣短发男孩', payload['prompt'])

    def test_unknown_or_empty_view_stops_before_writing_jobs(self):
        for views in (['missing'], [], ['front', 'front'], 'front'):
            with self.subTest(views=views), self.assertRaisesRegex(ValueError, 'view'):
                self.prepare({'reference_assets': [dict(asset_id='CHAR001', version='v001', views=views)]})
        self.assertEqual(list((self.root / '_state/jobs').iterdir()), [])

    def test_selected_view_cannot_hide_missing_required_asset(self):
        data = state.read_json(self.root / '_state/assets.json')
        data['assets'][0]['files'][1]['path'] = 'assets/characters/missing.png'
        self.asset_data(data)
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.prepare({'reference_assets': [dict(asset_id='CHAR001', version='v001', views=['side'])]})
        self.assertEqual(list((self.root / '_state/jobs').iterdir()), [])

    def test_task_cannot_replace_canonical_asset_version(self):
        with self.assertRaisesRegex(ValueError, 'version'):
            self.prepare({'reference_assets': [dict(asset_id='CHAR001', version='v002', views=['side'])]})
        self.assertEqual(list((self.root / '_state/jobs').iterdir()), [])

    def test_small_reference_pack_has_real_file_order_and_purpose_for_each_attachment(self):
        _, job = self.prepare({'reference_assets': [dict(asset_id='SCENE001', version='v001')]})
        self.assertEqual([r['path'] for r in job['references']],
                         ['assets/characters/ref.png', 'assets/characters/side.png', 'assets/scene.png'])
        payload = image_api.build_payload(self.root, job)
        self.assertEqual([base64.b64decode(url.split(',', 1)[1]) for url in payload['urls']],
                         [(self.root / ref['path']).read_bytes() for ref in job['references']])
        prompt = (self.root / job['prompt_path']).read_text(encoding='utf-8')
        self.assertLess(prompt.index('图1'), prompt.index('图2'))
        self.assertLess(prompt.index('图2'), prompt.index('图3'))
        self.assertIn('角色', prompt)
        self.assertIn('场景', prompt)
        self.assertIn('教室左窗右门', prompt)

    def test_canonical_explicit_views_remain_required_and_extra_views_follow(self):
        pages = state.read_json(self.root / '_state/pages.json')
        pages['pages'][0]['asset_refs'][0]['views'] = ['side']
        state.write_json(self.root / '_state/pages.json', pages)
        self.fixture.approve()
        _, job = self.prepare({'reference_assets': [dict(asset_id='CHAR001', version='v001', views=['front'])]})
        self.assertEqual([r['view'] for r in job['references']], ['side', 'front'])

    def test_derived_video_asset_inherits_same_canonical_character_view(self):
        data = state.read_json(self.root / '_state/assets.json')
        data['assets'].append(dict(asset_id='FRAME001', version='v001', kind='first_frame',
            fixed_features='同一角色走进教室', files=[],
            reference_assets=[dict(asset_id='CHAR001', version='v001', views=['side'])]))
        self.asset_data(data)
        _, job = self.prepare({'purpose': 'asset', 'target_id': 'FRAME001', 'prompt': '小明走进教室'})
        self.assertEqual([r['view'] for r in job['references']], ['side'])
        self.assertIn('图1', (self.root / job['prompt_path']).read_text(encoding='utf-8'))

    def test_original_asset_can_be_created_without_previous_master(self):
        data = state.read_json(self.root / '_state/assets.json')
        data['assets'].append(dict(asset_id='CHAR_NEW', version='v001', kind='character',
                                   fixed_features='首次建立新角色', files=[]))
        self.asset_data(data)
        _, job = self.prepare({'purpose': 'asset', 'target_id': 'CHAR_NEW', 'prompt': '首次建立新角色'})
        self.assertEqual(job['references'], [])

    def erase_task(self):
        enable_modules(self.root, route='B')
        source = self.image('slides/source.png', 'green')
        state.record_approval(self.root, {'targets': [source], 'user_evidence': 'Synthetic source approval'})
        return dict(purpose='erase', source_image=source, remove_texts=['5组，每组3个'],
                    preserve_elements=['小明与苹果'])

    def test_api_erase_uses_only_approved_source_even_when_master_file_missing(self):
        data = state.read_json(self.root / '_state/assets.json')
        data['assets'][0]['files'][0]['path'] = 'assets/missing-master.png'
        self.asset_data(data)
        task = self.erase_task()
        _, job = self.prepare(task)
        self.assertEqual([r['path'] for r in job['references']], ['slides/source.png'])
        self.assertEqual(job['image_api_input']['size'], '32x18')
        prompt = (self.root / job['prompt_path']).read_text(encoding='utf-8')
        self.assertIn('唯一底稿', prompt)
        self.assertIn('5组，每组3个', prompt)
        self.assertIn('小明与苹果', prompt)

    def test_builtin_page_keeps_original_prompt_all_references_and_input(self):
        self.builtin()
        data = prompts.records(self.root)
        expected, _ = prompts.page_prompt(data['pages']['pages'][0], data)
        batch, job = self.prepare()
        self.assertEqual((self.root / job['prompt_path']).read_text(encoding='utf-8'), expected)
        self.assertEqual([r['view'] for r in job['references']], ['front', 'side'])
        self.assertEqual(job['image_api_input'], {'endpoint': '/v1/draw/completions',
            'model': 'gpt-image-2.5', 'aspectRatio': '1672x941', 'size': '1672x941', 'shutProgress': True})
        self.assertEqual(job['provider'], 'codex')
        self.assertNotIn('provider', batch)

    def test_builtin_erase_keeps_source_and_original_asset_references(self):
        self.builtin()
        _, job = self.prepare(self.erase_task())
        self.assertEqual([r['path'] for r in job['references']],
                         ['slides/source.png', 'assets/characters/ref.png', 'assets/characters/side.png'])
        self.assertNotIn('图1', (self.root / job['prompt_path']).read_text(encoding='utf-8'))

    def test_api_repair_numbers_source_before_character_views(self):
        task = self.erase_task()
        task.update(purpose='repair', prompt='修复本页角色的右手姿势')
        _, job = self.prepare(task)
        self.assertEqual(job['references'][0]['path'], 'slides/source.png')
        prompt = (self.root / job['prompt_path']).read_text(encoding='utf-8')
        self.assertIn('图1：本页已采用的源图', prompt)
        self.assertIn('图2：CHAR001', prompt)
        self.assertIn('图3：CHAR001', prompt)

    def test_duomi_selection_binds_provider_model_size_and_keeps_reference_urls(self):
        data = state.read_json(self.root / '_state/assets.json')
        data['assets'][0]['files'][0]['provider_urls'] = {'duomi': 'https://example.com/front.png'}
        self.asset_data(data)
        batch, job = self.prepare(api={'provider': 'duomi'})
        self.assertEqual(batch['provider'], 'duomi')
        self.assertEqual(job['provider'], 'duomi')
        self.assertEqual(job['image_api_input']['model'], 'gpt-image-2')
        self.assertEqual(job['image_api_input']['size'], '1792x1008')
        self.assertEqual(job['references'][0]['provider_urls']['duomi'], 'https://example.com/front.png')
        with self.assertRaisesRegex(ValueError, 'different inputs'):
            self.prepare(api={'provider': 'grsai'})

    def test_duomi_erase_rejects_unsupported_source_dimensions_without_resizing(self):
        task = self.erase_task()
        before = (self.root / task['source_image']['path']).read_bytes()
        with self.assertRaisesRegex(ValueError, 'Duomi dimensions'):
            self.prepare(task, api={'provider': 'duomi'})
        self.assertEqual((self.root / task['source_image']['path']).read_bytes(), before)
        self.assertEqual(list((self.root / '_state/jobs').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
