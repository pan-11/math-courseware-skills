"""Selection and collection checks for supporting-document formats."""
from pathlib import Path
import unittest

from test_delivery_roles import package, save_package
from test_exports import fixture
from runtime import exports, state
from workflow_fixture import enable_modules


class SupportingDeliveryTests(unittest.TestCase):
    def test_collect_ignores_unselected_historical_pdf(self):
        root = fixture()
        enable_modules(root, modules=['documents'])
        result = exports.export_documents(root)
        report = result['documents']['classroom-script']
        pdf = root / report['qa_pdf']
        legacy = pdf.parent.parent / 'classroom-script.pdf'
        legacy.write_bytes(pdf.read_bytes())
        relative = legacy.relative_to(root).as_posix()
        state.register_artifact(root, 'classroom-script-pdf', relative, [],
                                {'export_kind': 'classroom-script', 'source_versions': report['source_versions']})
        before = state.sha256(legacy)

        collected = exports.collect(root)

        self.assertIn('classroom-script-docx', collected['artifacts'])
        self.assertTrue(all(Path(item['delivery_path']).suffix != '.pdf'
                            for item in collected['artifacts'].values()))
        self.assertEqual(state.sha256(legacy), before)
        self.assertIn('classroom-script-pdf', state.load_project(root)['artifacts'])

    def test_collect_honors_explicitly_selected_teacher_pdf(self):
        root = fixture()
        data = enable_modules(root, modules=['documents'])
        result = exports.export_documents(root)
        report = result['documents']['classroom-script']
        pdf = root / report['qa_pdf']
        selected = pdf.parent.parent / 'classroom-script.pdf'
        selected.write_bytes(pdf.read_bytes())
        relative = selected.relative_to(root).as_posix()
        digest = state.sha256(selected)
        manifest = package(root, data)
        manifest['roles']['classroom-script'].append({'path': relative, 'sha256': digest})
        save_package(root, data, manifest)

        collected = exports.collect(root)

        copies = {item['path']: item for item in collected['artifacts'].values()}
        self.assertEqual(state.sha256(root / copies[relative]['delivery_path']), digest)
        self.assertNotIn(report['qa_pdf'], copies)
