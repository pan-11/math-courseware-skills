"""Entrypoint and authority checks using retained synthetic projects."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
import courseware
from runtime import state
from workflow_fixture import enable_modules


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

    def test_default_init_and_status_do_not_infer_task_scope(self):
        self.assertEqual(state.status(self.root).get('workflow', {}).get('task_mode'), 'unclassified')

    def test_workflow_check_is_read_only_without_course_project(self):
        independent = self.root / 'independent-video'
        try:
            result = courseware.execute(argparse.Namespace(
                command='workflow-check', project=independent, step='video-script', video_id='V001'))
        except FileNotFoundError as exc:
            self.fail('Workflow checking must run before loading course project.json: ' + str(exc))
        self.assertFalse(result['allowed'])
        self.assertFalse(independent.exists())

    def test_workflow_check_cli_reports_blocked_with_exit_one(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = courseware.main(['workflow-check', '--project', str(self.root), '--step', 'pages'])
            except SystemExit as exc:
                self.fail('The documented workflow-check CLI must parse: ' + str(exc))
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(out.getvalue())['allowed'])

    def test_editable_commands_check_scope_before_reading_mutation_inputs(self):
        for command in ('canva-import', 'editable-build'):
            with self.subTest(command=command):
                args = argparse.Namespace(command=command, project=self.root,
                    deck=self.root / 'missing.pptx', mapping=self.root / 'mapping.json',
                    plan=self.root / 'plan.json')
                try:
                    with self.assertRaisesRegex(ValueError, 'workflow|Workflow|scope|mode'):
                        courseware.execute(args)
                except FileNotFoundError as exc:
                    self.fail('Editable mutation inputs were read before workflow scope: ' + str(exc))

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
            ('workflow-check', ['--step', 'video-script', '--video-id', 'V001']),
            ('image-prepare', ['--selection', 'input.json']),
            ('canva-handoff', ['--selection', 'input.json']),
            ('editable-build', ['--plan', 'input.json'])]:
            args = courseware.parser().parse_args([command, '--project', str(self.root), *extras])
            self.assertEqual(args.command, command)

    def test_full_text_refill_requires_complete_text_and_explicit_graphics_gaps(self):
        self.plan['build_scope'] = 'text-refill'
        self.plan['required_native_objects'] = []
        self.plan['remaining_native_objects'] = [{'page_id': 'P001', 'object_id': 'group-1',
                                                  'reason': 'Synthetic returned group is not separated.'}]
        courseware.validate_editable_authority(self.root, self.plan)
        self.plan['remaining_native_objects'] = []
        with self.assertRaisesRegex(ValueError, 'remaining'):
            courseware.validate_editable_authority(self.root, self.plan)
        self.plan['text_units'] = []
        with self.assertRaises(ValueError):
            courseware.validate_editable_authority(self.root, self.plan)

    def test_full_text_refill_rejects_partial_page_mapping(self):
        data = state.read_json(self.root / '_state/pages.json')
        data['pages'].append({'page_id': 'P002', 'order': 2, 'text_units': [], 'native_objects': []})
        state.write_json(self.root / '_state/pages.json', data)
        state.record_approval(self.root, {'targets': [{'path': '_state/pages.json',
            'sha256': state.sha256(self.root / '_state/pages.json')}], 'user_evidence': 'Synthetic test'})
        self.plan['build_scope'] = 'text-refill'
        with self.assertRaisesRegex(ValueError, 'every page'):
            courseware.validate_editable_authority(self.root, self.plan)

    def test_direct_refill_dispatch_registers_real_authorization_dependency(self):
        from fixture_factory import layered_deck
        from runtime import pptx_editor
        inventory = pptx_editor.import_deck(self.root, layered_deck(self.root), {'P001': 1})
        enable_modules(self.root, deck=inventory['source_deck'])
        self.plan.update(source_deck=inventory['source_deck'], source_sha256=inventory['source_sha256'],
                         output='editable/output/direct.pptx', build_scope='text-refill',
                         required_native_objects=[], remaining_native_objects=[{
                             'page_id': 'P001', 'object_id': 'group-1', 'reason': 'Synthetic unmapped graphic.'}])
        self.plan['text_units'][0]['box'] = {'x': 50, 'y': 180, 'width': 600, 'height': 60}
        evidence = self.root / '_state/synthetic-direct.json'
        state.write_json(evidence, {'authorized': True, 'scope': 'editable-build',
            'source_sha256': inventory['source_sha256'], 'page_ids': ['P001'], 'requested_by': 'synthetic-unittest',
            'user_instruction': 'Refill the complete synthetic deck.', 'evidence_ref': 'Synthetic fixture only'})
        self.plan['authorization'] = {'evidence': '_state/synthetic-direct.json', 'sha256': state.sha256(evidence)}
        plan_path = self.root / '_state/direct-plan.json'
        state.write_json(plan_path, self.plan)
        result = courseware.execute(argparse.Namespace(command='editable-build', project=self.root, plan=plan_path))
        self.assertTrue((self.root / result['output']).exists())
        self.assertFalse(result['full_editability_verified'])
        artifact = state.load_project(self.root)['artifacts']['editable-pptx']
        self.assertEqual(artifact['source_versions']['_state/synthetic-direct.json'], state.sha256(evidence))


if __name__ == '__main__':
    unittest.main()
