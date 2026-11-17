"""Provided-refill copies retain identity without pretending to be reviewed output."""
import copy
import importlib
import importlib.util
from pathlib import Path
import shutil
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/math-courseware-studio/scripts'))
from runtime import state
from test_classroom_animation import fixture as animation_fixture


def api(test):
    test.assertIsNotNone(importlib.util.find_spec('runtime.classroom_refill_input'),
                         'Provided refill needs a real provenance-preserving input entrypoint')
    return importlib.import_module('runtime.classroom_refill_input')


def fixture(five=False):
    root, animated = animation_fixture()
    state.write_json(root / ('中间文件/_state/project.json' if five else '_state/project.json'),
                     {'schema_version': '1.0', 'artifacts': {}, 'stale_targets': []})
    plan = {key: copy.deepcopy(animated[key]) for key in (
        'source_deck', 'source_sha256', 'source_versions', 'output', 'request', 'mapping')}
    plan['request']['user_instruction'] = 'Synthetic explicit request: 课堂动画试用V1 for this provided refill'
    authority = root / plan['request']['evidence_ref']['path']
    state.write_json(authority, {'user_instruction': plan['request']['user_instruction']})
    plan['request']['evidence_ref']['sha256'] = state.sha256(authority)
    plan['source_versions'][plan['request']['evidence_ref']['path']] = state.sha256(authority)
    plan['output'] = 'editable/refill-input-v001.pptx'
    if five:
        for relative in plan['source_versions']:
            target = state.resolve(root, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / relative, target)
    state.register_artifact(root, 'editable-base-pptx', plan['source_deck'], metadata={'legacy_marker': 'retain'})
    state.register_artifact(root, 'editable-pptx', plan['source_deck'], metadata={'legacy_marker': 'retain'})
    return root, plan


class ClassroomRefillInputTests(unittest.TestCase):
    def test_import_copies_exact_bytes_and_registers_only_separate_input(self):
        module = api(self)
        root, plan = fixture()
        originals = copy.deepcopy(state.load_project(root)['artifacts'])
        source = (root / plan['source_deck']).read_bytes()
        result = module.import_refill(root, plan, module.ACTIVATION)
        self.assertEqual((root / result['path']).read_bytes(), source)
        self.assertEqual((root / plan['source_deck']).read_bytes(), source)
        self.assertEqual(result['role'], 'provided_refill')
        self.assertEqual(result['content_review'], 'unverified')
        self.assertEqual(result['playback'], 'unverified')
        self.assertEqual(result['mapping'], {'P001': 1, 'P002': 2})
        self.assertEqual([p['part'] for p in result['inventory']['slides']],
                         ['ppt/slides/slide2.xml', 'ppt/slides/slide1.xml'])
        record = state.load_project(root)['artifacts']
        for key, value in originals.items():
            self.assertEqual(record[key], value)
        self.assertIn(module.ARTIFACT, record)
        self.assertEqual(module.current(root), result)
        self.assertEqual(module.import_refill(root, plan, module.ACTIVATION), result)

    def test_activation_and_real_instruction_evidence_required_before_output(self):
        module = api(self)
        with self.assertRaisesRegex(ValueError, 'activation'):
            module.import_refill(Path('absent-project'), {}, 'wrong')
        root, plan = fixture()
        plan['request']['user_instruction'] = 'This statement is absent from the real evidence'
        with self.assertRaisesRegex(ValueError, 'instruction.*evidence'):
            module.import_refill(root, plan, module.ACTIVATION)
        self.assertFalse((root / plan['output']).exists())

    def test_logical_paths_work_in_five_folder_layout(self):
        module = api(self)
        root, plan = fixture(five=True)
        result = module.import_refill(root, plan, module.ACTIVATION)
        self.assertTrue(state.resolve(root, result['path']).is_relative_to(root / '中间文件'))
        self.assertEqual(state.sha256(state.resolve(root, result['path'])), plan['source_sha256'])
        self.assertEqual(module.current(root), result)

    def test_mapping_covers_all_actual_slides_without_aliasing(self):
        module = api(self)
        for mapping in ({'P001': 1}, {'P001': 1, 'P002': 1}, {'P001': 1, 'P002': 3}):
            root, plan = fixture()
            plan['mapping'] = mapping
            with self.assertRaises(ValueError):
                module.import_refill(root, plan, module.ACTIVATION)
            self.assertFalse((root / plan['output']).exists())

    def test_source_or_any_bound_file_cannot_be_overwritten(self):
        module = api(self)
        for output in ('inputs/source.pptx', '../escape.pptx', 'inputs/request.json'):
            root, plan = fixture()
            plan['output'] = output
            source = (root / plan['source_deck']).read_bytes()
            with self.assertRaises(ValueError):
                module.import_refill(root, plan, module.ACTIVATION)
            self.assertEqual((root / plan['source_deck']).read_bytes(), source)

    def test_existing_unowned_output_is_preserved(self):
        module = api(self)
        root, plan = fixture()
        output = root / plan['output']
        output.write_bytes(b'existing manual file')
        with self.assertRaisesRegex(ValueError, 'overwrite|provenance|exists'):
            module.import_refill(root, plan, module.ACTIVATION)
        self.assertEqual(output.read_bytes(), b'existing manual file')

    def test_current_rejects_changed_source_output_plan_manifest_and_evidence(self):
        module = api(self)
        for kind in ('source', 'output', 'plan', 'manifest', 'instruction'):
            root, plan = fixture()
            result = module.import_refill(root, plan, module.ACTIVATION)
            paths = {'source': plan['source_deck'], 'output': result['path'],
                     'plan': result['plan_ref']['path'], 'manifest': result['manifest_ref']['path'],
                     'instruction': plan['request']['evidence_ref']['path']}
            target = root / paths[kind]
            target.write_bytes(target.read_bytes() + b'\n')
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                module.current(root)

    def test_current_rejects_stale_or_repointed_registration(self):
        module = api(self)
        for mutation in ('stale', 'repoint'):
            root, plan = fixture()
            module.import_refill(root, plan, module.ACTIVATION)
            record = state.load_project(root)
            if mutation == 'stale':
                record['stale_targets'].append(module.ARTIFACT)
            else:
                record['artifacts'][module.ARTIFACT]['path'] = plan['source_deck']
            state.write_json(root / '_state/project.json', record)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                module.current(root)


class ClassroomContinuationFlowTests(unittest.TestCase):
    def fixture(self):
        from test_click_answers import fixture as click_fixture, answer
        from test_classroom_trial import initialize
        from runtime import classroom_trial
        root, component = click_fixture()
        initialize(root)
        state.write_json(root / '_state/pages.json', {'schema_version': '1.0', 'pages': []})
        instruction = '可以的'
        authority = root / component['request']['evidence_ref']['path']
        state.write_json(authority, {'user_instruction': instruction})
        component['request']['user_instruction'] = instruction
        component['request']['evidence_ref']['sha256'] = state.sha256(authority)
        component['source_versions'][component['request']['evidence_ref']['path']] = state.sha256(authority)
        activation = root / 'inputs/continuation.json'
        state.write_json(activation, {'activation': classroom_trial.ACTIVATION, 'scope': 'current_task',
            'status': 'active', 'user_instruction': instruction,
            'input_sha256': component['source_sha256'], 'project_root': str(root.resolve())})
        component['request']['activation_ref'] = {'path': 'inputs/continuation.json', 'sha256': state.sha256(activation)}
        component['source_versions']['inputs/continuation.json'] = state.sha256(activation)
        component['output'] = 'editable/output/components.pptx'
        component['pages'][0]['items'] = [answer()]
        imported = {k: copy.deepcopy(component[k]) for k in (
            'source_deck', 'source_sha256', 'source_versions', 'output', 'request', 'mapping')}
        imported['output'] = 'editable/refill-input-v001.pptx'
        return root, component, imported

    def test_import_components_and_classroom_accept_same_real_continuation_input(self):
        from runtime import classroom_trial
        from test_classroom_trial import classroom_plan
        module = api(self)
        root, component, imported = self.fixture()
        source_bytes = state.resolve(root, imported['source_deck']).read_bytes()
        receipt = module.import_refill(root, imported, module.ACTIVATION)
        component['source_deck'] = receipt['path']
        component['source_sha256'] = receipt['sha256']
        component['source_versions'][receipt['path']] = receipt['sha256']
        report = classroom_trial.components(root, component, classroom_trial.ACTIVATION)
        self.assertEqual(report['source_sha256'], imported['source_sha256'])
        self.assertNotEqual(report['output_sha256'], imported['source_sha256'])
        plan = classroom_plan(report, component, root)
        result = classroom_trial.build(root, plan, {'path': report['manifest'],
            'sha256': report['manifest_sha256']}, classroom_trial.ACTIVATION)
        self.assertEqual(result['playback'], 'unverified')
        self.assertTrue(result['teaching_coverage']['matches_declared_teaching_contract'])
        self.assertEqual(plan['request']['user_instruction'], '可以的')
        self.assertEqual(state.resolve(root, imported['source_deck']).read_bytes(), source_bytes)
        self.assertNotIn('editable-base-pptx', state.load_project(root)['artifacts'])

    def test_continuation_cannot_bind_an_unrelated_locked_source_hash(self):
        from runtime import classroom_trial
        module = api(self)
        root, component, imported = self.fixture()
        bad_record = state.read_json(root / 'inputs/continuation.json')
        bad_record['input_sha256'] = imported['source_versions']['inputs/answer-basis.json']
        bad_path = root / 'inputs/unrelated-continuation.json'
        state.write_json(bad_path, bad_record)
        bad_import = copy.deepcopy(imported)
        bad_ref = {'path': 'inputs/unrelated-continuation.json', 'sha256': state.sha256(bad_path)}
        bad_import['request']['activation_ref'] = bad_ref
        bad_import['source_versions'][bad_ref['path']] = bad_ref['sha256']
        with self.assertRaisesRegex(ValueError, 'continuation does not match'):
            module.import_refill(root, bad_import, module.ACTIVATION)
        self.assertFalse(state.resolve(root, imported['output']).exists())
        receipt = module.import_refill(root, imported, module.ACTIVATION)
        component['source_deck'] = receipt['path']
        component['source_sha256'] = receipt['sha256']
        component['source_versions'][receipt['path']] = receipt['sha256']
        component['request']['activation_ref'] = bad_ref
        component['source_versions'][bad_ref['path']] = bad_ref['sha256']
        with self.assertRaisesRegex(ValueError, 'continuation does not match'):
            classroom_trial.components(root, component, classroom_trial.ACTIVATION)
        self.assertFalse(state.resolve(root, component['output']).exists())


if __name__ == '__main__':
    unittest.main()
