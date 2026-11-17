"""Provided trial inputs must never join the ordinary editable delivery package."""
from pathlib import Path
import shutil
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/math-courseware-studio/scripts'))
from runtime import classroom_refill_input as refill, editable_delivery, exports, state
from fixture_factory import layered_deck
from test_exports import fixture
from workflow_fixture import enable_modules


class ClassroomRefillExportIsolationTests(unittest.TestCase):
    def test_public_import_under_output_stays_out_of_ordinary_collect(self):
        root = fixture()
        source = layered_deck(root)
        source_ref = {'path': source.relative_to(root).as_posix(), 'sha256': state.sha256(source)}
        enable_modules(root, modules=['editable'], deck=source_ref['path'])
        legacy_path = root / 'editable/output/legacy-final.pptx'
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, legacy_path)
        legacy = state.register_artifact(root, 'editable-pptx', legacy_path.relative_to(root).as_posix(),
            [source_ref['path']], {'source_versions': {source_ref['path']: source_ref['sha256']}})
        instruction = 'Synthetic explicit request: 课堂动画试用V1 for this supplied refill'
        authority = root / 'inputs/trial-instruction.json'
        state.write_json(authority, {'user_instruction': instruction})
        evidence = {'path': authority.relative_to(root).as_posix(), 'sha256': state.sha256(authority)}
        plan = {'source_deck': source_ref['path'], 'source_sha256': source_ref['sha256'],
            'source_versions': {source_ref['path']: source_ref['sha256'], evidence['path']: evidence['sha256']},
            'output': 'editable/output/provided-refill.pptx', 'mapping': {'P001': 1},
            'request': {'user_instruction': instruction, 'evidence_ref': evidence}}

        imported = refill.import_refill(root, plan, refill.ACTIVATION)
        self.assertEqual(refill.current(root), imported)
        self.assertEqual(editable_delivery.current(root), legacy)
        collected = exports.collect(root)

        self.assertEqual(set(collected['artifacts']), {'editable-pptx'})
        self.assertNotIn(imported['path'], {a['path'] for a in collected['artifacts'].values()})
        delivered = collected['artifacts']['editable-pptx']
        self.assertEqual(state.sha256(state.resolve(root, delivered['delivery_path'])), legacy['sha256'])
        self.assertEqual(refill.current(root), imported)
        self.assertEqual(state.sha256(source), source_ref['sha256'])
        self.assertEqual(state.sha256(state.resolve(root, imported['path'])), source_ref['sha256'])


if __name__ == '__main__':
    unittest.main()
