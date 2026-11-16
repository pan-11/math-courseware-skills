"""API provider choices and consent remain separate from builtin image behavior."""
from copy import deepcopy
from pathlib import Path
import os
import sys
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
import courseware
from runtime import state, preferences, errors


class ApiPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs' / ('api-preferences-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic API choices', 'openai_image_api', api_provider='grsai')

    def run_record(self, provider=None):
        data = {'run_id': 'run-' + '1' * 32}
        patch = {'route': 'openai_image_api', 'evidence': 'Synthetic actual selection',
                 'authorization': {'scope': 'run', 'purposes': ['test'], 'paid_generation': True,
                                   'scope_evidence': 'Synthetic provider-specific consent'}}
        if provider: patch['provider'] = provider
        preferences.update(self.root, data, {'image': patch})
        return data

    def test_legacy_api_defaults_to_grsai_without_writing_project(self):
        path = self.root / '_state/project.json'
        legacy = state.read_json(path)
        legacy.pop('image_provider')
        state.write_json(path, legacy)
        before = (self.root / '_state/project.json').read_bytes()
        self.assertEqual(preferences.image_settings(self.root), {'provider': 'grsai'})
        self.assertEqual(before, (self.root / '_state/project.json').read_bytes())

    def test_manual_selection_can_choose_duomi_and_reject_unknown_provider(self):
        self.assertEqual(preferences.image_settings(self.root, selection_api={'provider': 'duomi', 'model': 'gpt-image-2'}),
                         {'provider': 'duomi', 'model': 'gpt-image-2'})
        with self.assertRaises(ValueError):
            preferences.image_settings(self.root, selection_api={'provider': 'unknown'})

    def test_project_duomi_settings_persist_and_init_does_not_overwrite(self):
        target = self.root / 'duomi-project'
        first = state.init_project(target, 'Synthetic Duomi', 'openai_image_api',
                                   api_provider='duomi', api_model='gpt-image-2')
        self.assertEqual(first['image_provider'], 'duomi')
        self.assertEqual(preferences.image_settings(target), {'provider': 'duomi', 'model': 'gpt-image-2'})
        state.init_project(target, 'Ignored', 'openai_image_api', api_provider='grsai')
        self.assertEqual(state.load_project(target)['image_provider'], 'duomi')

    def test_builtin_canonical_choices_do_not_gain_api_fields(self):
        path = self.root / '_state/project.json'
        data = state.read_json(path)
        data.update(image_route='builtin', image_provider='duomi', image_model='gpt-image-2')
        state.write_json(path, data)
        self.assertEqual(preferences.canonical(self.root)['image'], {'route': 'builtin'})

    def test_init_rejects_api_options_on_builtin_before_creating_files(self):
        target = self.root / 'invalid-builtin'
        with self.assertRaises(ValueError):
            state.init_project(target, 'Synthetic', 'builtin', api_provider='duomi')
        self.assertFalse(target.exists())

    def test_run_provider_change_does_not_reuse_grsai_consent(self):
        data = self.run_record()
        preferences.update(self.root, data, {'image': {'provider': 'duomi', 'evidence': 'Synthetic switch only'}})
        issues = preferences.image_authorization_issues(self.root,
            [{'purpose': 'test', 'provider': 'duomi'}], 'openai_image_api', data)
        self.assertTrue(any('provider' in item for item in issues))
        preferences.update(self.root, data, {'image': {'authorization': {
            'scope_evidence': 'Synthetic explicit paid consent for selected Duomi'}}})
        self.assertEqual(preferences.image_authorization_issues(self.root,
            [{'purpose': 'test', 'provider': 'duomi'}], 'openai_image_api', data), [])

    def test_run_batch_cannot_silently_override_provider(self):
        data = self.run_record('duomi')
        with self.assertRaisesRegex(ValueError, 'run-configure|selection'):
            preferences.image_settings(self.root, data, {'provider': 'grsai'})
        self.assertEqual(preferences.image_settings(self.root, data), {'provider': 'duomi'})

    def test_wrong_provider_job_is_not_covered_by_current_run_consent(self):
        data = self.run_record('duomi')
        issues = preferences.image_authorization_issues(self.root,
            [{'purpose': 'test', 'provider': 'grsai'}], 'openai_image_api', data)
        self.assertTrue(any('provider' in item for item in issues))

    def test_bad_provider_update_preserves_run_record(self):
        data = self.run_record()
        before = deepcopy(data)
        with self.assertRaises(ValueError):
            preferences.update(self.root, data, {'image': {'provider': 'invalid', 'evidence': 'Synthetic'}})
        self.assertEqual(data, before)

    def test_cli_init_accepts_api_provider_and_model(self):
        target = self.root / 'cli-duomi'
        args = courseware.parser().parse_args(['init', '--project', str(target), '--title', 'Synthetic',
            '--route', 'openai_image_api', '--api-provider', 'duomi', '--api-model', 'gpt-image-2'])
        self.assertEqual(courseware.execute(args)['image_provider'], 'duomi')

    def test_explicit_model_change_requires_matching_consent(self):
        data = self.run_record('duomi')
        preferences.update(self.root, data, {'image': {'model': 'gpt-image-2.5-flare',
            'evidence': 'Synthetic model selection'}})
        issues = preferences.image_authorization_issues(self.root,
            [{'purpose': 'test', 'provider': 'duomi'}], 'openai_image_api', data)
        self.assertTrue(any('model' in item for item in issues))
        preferences.update(self.root, data, {'image': {'authorization': {
            'scope_evidence': 'Synthetic explicit consent for new selected model'}}})
        self.assertEqual(preferences.image_authorization_issues(self.root,
            [{'purpose': 'test', 'provider': 'duomi'}], 'openai_image_api', data), [])

    def test_duomi_environment_key_is_redacted_even_without_explicit_secret_argument(self):
        token = 'synthetic-duomi-only-value'
        with patch.dict(os.environ, {'DUOMI_API_KEY': token}):
            self.assertNotIn(token, errors.redact('Unexpected response ' + token))

    def test_switching_run_provider_does_not_inherit_project_model(self):
        for original, model, selected in [('grsai', 'gpt-image-2.5', 'duomi'),
                                         ('duomi', 'gpt-image-2', 'grsai')]:
            with self.subTest(original=original):
                path = self.root / '_state/project.json'
                project = state.read_json(path)
                project.update(image_provider=original, image_model=model)
                state.write_json(path, project)
                data = self.run_record(original)
                preferences.update(self.root, data, {'image': {
                    'provider': selected, 'evidence': 'Synthetic change to provider default model'}})
                self.assertEqual(preferences.image_settings(self.root, data), {'provider': selected})

    def test_pending_job_cannot_reuse_consent_for_a_different_default_model(self):
        data = self.run_record('duomi')
        job = {'route': 'openai_image_api', 'provider': 'duomi', 'run_id': data['run_id'],
               'purpose': 'test', 'version': 'v001', 'resolution_tier': 'default',
               'image_api_input': {'model': 'gpt-image-2.5-flare'}}
        with patch.object(preferences.store, 'load_run', return_value=data):
            with self.assertRaisesRegex(ValueError, 'model'):
                preferences.require_image_job(self.root, job)
            job['image_api_input']['model'] = 'gpt-image-2'
            preferences.require_image_job(self.root, job)


if __name__ == '__main__': unittest.main()
