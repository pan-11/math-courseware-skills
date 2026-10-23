"""Synthetic role and explicit-package checks; never real-course acceptance."""
from datetime import datetime
from pathlib import Path
import sys
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       'skills/math-courseware-studio/scripts'))
from runtime import state, delivery_roles


def fixture(mode='full_course', modules=None):
    root = Path(__file__).parent / 'runs' / (
        'delivery-roles-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    state.init_project(root, 'Synthetic delivery roles', mode=mode,
                       scope_evidence='Synthetic task, not actual user approval')
    data = state.read_json(root / '_state/workflow.json')
    data['current_task']['modules'] = modules or ['studio']
    state.write_json(root / '_state/pages.json', {'pages': [{'page_id': 'P001', 'order': 1}]})
    state.write_json(root / '_state/workflow.json', data)
    return root, data


def file_ref(root, relative, text='Synthetic actual teaching material'):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return {'path': relative, 'sha256': state.sha256(path)}


def package(root, data, extra=()):
    sources = {'_state/pages.json': state.sha256(root / '_state/pages.json')}
    roles = {name: [file_ref(root, 'documents/test-role/' + name + '.md')]
             for name in delivery_roles.TEACHERS}
    if 'worksheet' in extra:
        from docx import Document
        path = root / 'documents/test-role/worksheet.docx'
        doc = Document()
        doc.add_paragraph('Synthetic student task: write your answer here ______')
        doc.save(path)
        roles['worksheet'] = [{'path': path.relative_to(root).as_posix(), 'sha256': state.sha256(path)}]
    if 'blackboard' in extra:
        from PIL import Image
        path = root / 'assets/test-board.png'
        Image.new('RGB', (20, 20), 'white').save(path)
        roles['blackboard'] = [{'path': 'assets/test-board.png', 'sha256': state.sha256(path)}]
    if 'interactive' in extra:
        roles['interactive'] = [file_ref(root, 'interactive/test/index.html',
            '<!doctype html><html><body><button>Try</button><script>let count=0;</script></body></html>')]
    manifest = {'schema_version': '1.0', 'source_versions': sources, 'roles': roles}
    save_package(root, data, manifest)
    return manifest


def save_package(root, data, manifest):
    path = 'documents/test-role/manifest.json'
    state.write_json(root / path, manifest)
    data['stages']['documents'] = {'files': {
        'materials-manifest': {'path': path, 'sha256': state.sha256(root / path)}}}
    state.write_json(root / '_state/workflow.json', data)


class DeliveryRolesTests(unittest.TestCase):
    def test_full_course_three_documents_do_not_satisfy_materials(self):
        root, data = fixture()
        package(root, data)
        result = delivery_roles.check(root)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('worksheet' in x for x in result['issues']))
        self.assertTrue(any('blackboard' in x for x in result['issues']))

    def test_full_course_requires_only_promised_interactive(self):
        root, data = fixture()
        manifest = package(root, data, ('worksheet', 'blackboard'))
        self.assertTrue(delivery_roles.check(root)['allowed'])
        data['stages']['blueprint'] = {'interactive_ids': ['H001']}
        save_package(root, data, manifest)
        self.assertTrue(delivery_roles.check(root)['allowed'])
        from workflow_fixture import evidence
        data['stages']['blueprint'] = evidence(root, 'role-blueprint', approved=True,
            interactive_ids=['H001'])
        save_package(root, data, manifest)
        self.assertIn('interactive', delivery_roles.check(root)['required_roles'])
        self.assertFalse(delivery_roles.check(root)['allowed'])

    def test_canonical_page_promise_cannot_be_omitted_from_manifest(self):
        root, data = fixture()
        state.write_json(root / '_state/pages.json', {'pages': [
            {'page_id': 'P001', 'order': 1, 'interactive_ids': ['H001']}]})
        package(root, data, ('worksheet', 'blackboard'))
        self.assertTrue(delivery_roles.check(root)['allowed'])
        state.record_approval(root, {'user_evidence': 'Synthetic adoption of page interaction promise',
            'targets': [{'path': '_state/pages.json', 'sha256': state.sha256(root / '_state/pages.json')}]})
        self.assertFalse(delivery_roles.check(root)['allowed'])

    def test_existing_direct_stage_roles_need_no_new_manifest(self):
        root, data = fixture()
        manifest = package(root, data, ('worksheet', 'blackboard'))
        data['stages']['documents'] = {'source_versions': manifest['source_versions'],
            'files': {role: files[0] for role, files in manifest['roles'].items()}}
        state.write_json(root / '_state/workflow.json', data)
        self.assertTrue(delivery_roles.check(root)['allowed'])
        data['stages']['delivery'] = data['stages'].pop('documents')
        state.write_json(root / '_state/workflow.json', data)
        self.assertTrue(delivery_roles.check(root)['allowed'])

    def test_independent_documents_and_refill_have_no_full_course_requirements(self):
        for module in ('documents', 'editable'):
            root, data = fixture('selected_modules', [module])
            data['project_mode'] = 'full_course'
            state.write_json(root / '_state/workflow.json', data)
            result = delivery_roles.check(root)
            self.assertTrue(result['allowed'])
            self.assertEqual(result['required_roles'], [])

    def test_changed_file_and_changed_source_are_rejected(self):
        root, data = fixture()
        manifest = package(root, data, ('worksheet', 'blackboard'))
        (root / manifest['roles']['worksheet'][0]['path']).write_text('changed', encoding='utf-8')
        self.assertFalse(delivery_roles.check(root)['allowed'])
        manifest = package(root, data, ('worksheet', 'blackboard'))
        state.write_json(root / '_state/pages.json', {'pages': [{'page_id': 'P002', 'order': 1}]})
        self.assertFalse(delivery_roles.check(root)['allowed'])

    def test_unrelated_source_binding_does_not_certify_current_course(self):
        root, data = fixture()
        manifest = package(root, data, ('worksheet', 'blackboard'))
        unrelated = file_ref(root, 'documents/unrelated.md')
        manifest['source_versions'] = {unrelated['path']: unrelated['sha256']}
        save_package(root, data, manifest)
        self.assertFalse(delivery_roles.check(root)['allowed'])

    def test_actual_editable_deck_must_be_bound_when_present(self):
        root, data = fixture()
        manifest = package(root, data, ('worksheet', 'blackboard'))
        deck = file_ref(root, 'editable/output/actual-deck.pptx')
        data['stages']['editable'] = {'files': {'pptx': deck}}
        save_package(root, data, manifest)
        self.assertFalse(delivery_roles.check(root)['allowed'])

    def test_waiver_requires_current_actual_user_evidence(self):
        root, data = fixture()
        manifest = package(root, data, ('worksheet',))
        manifest['waivers'] = {'blackboard': {'reason': 'User only needs digital class'}}
        save_package(root, data, manifest)
        self.assertFalse(delivery_roles.check(root)['allowed'])
        evidence_path = '_state/qa/actual-role-request.json'
        state.write_json(root / evidence_path, {'user_evidence': 'Synthetic explicit request to omit blackboard',
            'waived_roles': ['blackboard'], 'source_versions': manifest['source_versions']})
        manifest['waivers']['blackboard']['evidence'] = {
            'path': evidence_path, 'sha256': state.sha256(root / evidence_path)}
        save_package(root, data, manifest)
        self.assertTrue(delivery_roles.check(root)['allowed'])
        (root / evidence_path).write_text('{}', encoding='utf-8')
        self.assertFalse(delivery_roles.check(root)['allowed'])

    def test_specification_is_not_actual_blackboard_or_interactive(self):
        root, data = fixture()
        manifest = package(root, data, ('worksheet',))
        manifest['roles']['blackboard'] = [file_ref(root, 'assets/board-spec.md')]
        data['stages']['blueprint'] = {'interactive_ids': ['H001']}
        manifest['roles']['interactive'] = [file_ref(root, 'interactive/spec.md')]
        save_package(root, data, manifest)
        result = delivery_roles.check(root)
        self.assertFalse(result['allowed'])
        self.assertTrue(any('blackboard' in x for x in result['issues']))
        self.assertTrue(any('interactive' in x for x in result['issues']))

    def test_destination_cannot_escape_explicit_package(self):
        root, data = fixture()
        manifest = package(root, data, ('worksheet', 'blackboard'))
        manifest['roles']['worksheet'][0]['destination'] = '../escape.md'
        save_package(root, data, manifest)
        self.assertFalse(delivery_roles.check(root)['allowed'])

    def test_conflicting_destinations_rejected_before_collection(self):
        root, data = fixture()
        manifest = package(root, data, ('worksheet', 'blackboard'))
        manifest['roles']['worksheet'][0]['destination'] = 'same-file.md'
        other = file_ref(root, 'documents/test-role/print-guide.md', 'A distinct guide')
        other['destination'] = 'same-file.md'
        manifest['roles']['worksheet'].append(other)
        save_package(root, data, manifest)
        self.assertFalse(delivery_roles.check(root)['allowed'])

    def test_worksheet_plan_is_not_actual_student_document(self):
        root, data = fixture()
        manifest = package(root, data, ('worksheet', 'blackboard'))
        manifest['roles']['worksheet'] = [file_ref(root, 'documents/test-role/worksheet-plan.md')]
        save_package(root, data, manifest)
        self.assertFalse(delivery_roles.check(root)['allowed'])

    def test_explicit_manifest_does_not_authorize_private_or_executable_files(self):
        for name in ('.env', 'credentials.json', 'secret.txt', 'setup.exe', '.cache/file.js'):
            with self.subTest(name=name):
                root, data = fixture()
                manifest = package(root, data, ('worksheet', 'blackboard', 'interactive'))
                manifest['roles']['interactive'].append(file_ref(root, 'interactive/test/' + name))
                save_package(root, data, manifest)
                self.assertFalse(delivery_roles.check(root)['allowed'])


if __name__ == '__main__':
    unittest.main()
