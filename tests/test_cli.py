"""Entrypoint and authority checks using retained synthetic projects."""
import argparse
from pathlib import Path
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
import courseware
from runtime import state


class CliTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs' / ('cli-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic CLI authority test')
        state.write_json(self.root / '_state/pages.json', {'pages': [{
            'page_id': 'P001', 'order': 1, 'text_units': [{'unit_id': 'P001-T01', 'text': '5组，每组3个'}],
            'native_objects': [{'object_id': 'group-1', 'required': True}]}]})
        state.record_approval(self.root, {'targets': [{'path': '_state/pages.json',
            'sha256': state.sha256(self.root / '_state/pages.json')}], 'user_evidence': 'Synthetic test'})
        self.plan = {'mapping': {'P001': 1}, 'text_units': [{'page_id': 'P001', 'unit_id': 'P001-T01', 'text': '5组，每组3个'}],
                     'required_native_objects': [{'page_id': 'P001', 'object_id': 'group-1', 'shape_id': 8}]}

    def test_authority_rejects_wrong_text_or_missing_math_object(self):
        courseware.validate_editable_authority(self.root, self.plan)
        self.plan['text_units'][0]['text'] = '4组，每组3个'
        with self.assertRaises(ValueError):
            courseware.validate_editable_authority(self.root, self.plan)
        self.plan['text_units'][0]['text'] = '5组，每组3个'
        self.plan['required_native_objects'] = []
        with self.assertRaises(ValueError):
            courseware.validate_editable_authority(self.root, self.plan)

    def test_dispatch_exports_through_actual_entrypoint(self):
        from test_exports import fixture
        project = fixture()
        slides = courseware.execute(argparse.Namespace(command='export-slides', project=project))
        self.assertTrue((project / slides['artifacts']['image-slides-pptx']['path']).exists())
        docs = courseware.execute(argparse.Namespace(command='export-documents', project=project))
        self.assertEqual(len(docs['documents']), 3)
        delivery = courseware.execute(argparse.Namespace(command='collect', project=project))
        self.assertTrue((project / delivery['manifest']).exists())

    def test_all_documented_commands_parse(self):
        for command, extras in [
            ('status', []), ('validate', []), ('render-prompts', []),
            ('image-prepare', ['--selection', 'input.json']),
            ('canva-handoff', ['--selection', 'input.json']),
            ('editable-build', ['--plan', 'input.json'])]:
            args = courseware.parser().parse_args([command, '--project', str(self.root), *extras])
            self.assertEqual(args.command, command)


if __name__ == '__main__':
    unittest.main()
