"""Actual copied-file and current-source regressions using retained synthetic projects."""
from pathlib import Path
import shutil
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/math-courseware-studio/scripts'))
from runtime import state, workflow, exports, delivery_roles, grouped_gates
from workflow_fixture import evidence, ref, enable_modules, versions
from test_delivery_roles import fixture, file_ref
import test_workflow as workflow_cases


class DeliveryIntegrityTests(unittest.TestCase):
    def selected(self):
        root, _ = fixture('selected_modules', ['documents'])
        data = enable_modules(root, ['documents'])
        state.record_approval(root, {'targets': [ref(root, '_state/pages.json')],
            'user_evidence': 'Synthetic canonical fixture approval only'})
        source = file_ref(root, 'inputs/lesson-v1.md', '3 + 2 = 5')
        data['inputs']['documents'] = evidence(root, 'input-current', files={'source': source})
        current = file_ref(root, 'documents/lesson-plan/current.md', '# Teach 3 + 2 = 5')
        data['stages']['documents'] = evidence(root, 'current-materials', files={'lesson-plan': current},
            sources={source['path']: source['sha256']})
        state.write_json(root / '_state/workflow.json', data)
        return root, data, source, current

    def deliver(self, root, data):
        report = exports.collect(root)
        data['stages']['delivery'] = evidence(root, 'delivery', files={'manifest': ref(root, report['manifest'])},
            sources=data['stages']['documents']['source_versions'])
        state.write_json(root / '_state/workflow.json', data)
        return report

    def test_selected_complete_rechecks_actual_collected_copies(self):
        root, data, source, current = self.selected()
        report = self.deliver(root, data)
        self.assertTrue(workflow.check(root, 'complete')['allowed'])
        copied = next(a for a in report['artifacts'].values() if a['path'] == current['path'])
        (root / copied['delivery_path']).write_text('Unrelated replacement', encoding='utf8')
        self.assertFalse(workflow.check(root, 'complete')['allowed'])

    def test_current_input_changed_path_invalidates_old_documents_and_completion(self):
        root, data, source, current = self.selected()
        self.deliver(root, data)
        newer = file_ref(root, 'inputs/lesson-v2.md', '3 + 3 = 6')
        data['inputs']['documents'] = evidence(root, 'new-input', files={'source': newer})
        state.write_json(root / '_state/workflow.json', data)
        self.assertFalse(delivery_roles.check(root)['allowed'])
        self.assertFalse(workflow.check(root, 'complete')['allowed'])
        with self.assertRaises(ValueError):
            exports.collect(root)
        self.assertEqual((root / source['path']).read_text(encoding='utf8'), '3 + 2 = 5')

    def test_current_input_alias_is_the_same_source(self):
        root, data, source, current = self.selected()
        data['stages']['documents']['source_versions'] = {str((root / source['path']).resolve()): source['sha256']}
        state.write_json(root / '_state/workflow.json', data)
        self.assertTrue(delivery_roles.check(root)['allowed'])

    def test_registered_document_export_also_requires_current_module_input(self):
        root, data, source, current = self.selected()
        old = file_ref(root, 'documents/export-v001/lesson-plan.md', '# Retained old export')
        state.register_artifact(root, 'lesson-plan-md', old['path'], [source['path']],
            {'source_versions': {source['path']: source['sha256']}})
        data['stages'].pop('documents')
        newer = file_ref(root, 'inputs/lesson-v2.md', '3 + 3 = 6')
        data['inputs']['documents'] = evidence(root, 'new-input', files={'source': newer})
        state.write_json(root / '_state/workflow.json', data)
        with self.assertRaises(ValueError):
            exports.collect(root)

    def test_document_render_cannot_rebind_old_canonical_text_to_new_input(self):
        import test_exports
        root = test_exports.fixture()
        data = enable_modules(root, ['documents'])
        newer = file_ref(root, 'inputs/new-lesson.md', 'A different task: 3 + 3 = 6')
        data['inputs']['documents'] = evidence(root, 'new-document-input', files={'source': newer})
        state.write_json(root / '_state/workflow.json', data)
        with self.assertRaisesRegex(ValueError, 'source binding'):
            exports.export_documents(root)
        self.assertFalse(list((root / 'documents').glob('export-v*')))

    def test_explicit_role_supersedes_retained_exports_even_when_stale(self):
        root, data, source, current = self.selected()
        old = file_ref(root, 'documents/export-v001/lesson-plan.md', '# Historical different lesson')
        state.register_artifact(root, 'lesson-plan-md', old['path'], [source['path']],
            {'source_versions': {source['path']: source['sha256']}})
        for stale in (False, True):
            if stale:
                record = state.load_project(root)
                record['stale_targets'].append('lesson-plan-md')
                state.write_json(root / '_state/project.json', record)
            report = exports.collect(root)
            self.assertEqual({a['path'] for a in report['artifacts'].values()}, {current['path']})
        self.assertEqual((root / old['path']).read_text(encoding='utf8'), '# Historical different lesson')

    def full(self):
        f = workflow_cases.WorkflowTests('runTest')
        f.setUp(); f.completed_files()
        root, data = f.root, f.data
        files = {}
        for name in ('editable', 'documents'):
            for role, item in data['stages'][name]['files'].items():
                dest = root / 'deliveries/verified-v1' / (role + Path(item['path']).suffix)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / item['path'], dest)
                files[role] = ref(root, dest.relative_to(root).as_posix())
        path = 'deliveries/verified-v1/manifest.json'
        sources = versions(data['stages']['editable'], data['stages']['documents'])
        state.write_json(root / path, {'schema_version': '1.0', 'files': files, 'source_versions': sources})
        data['stages']['delivery'] = evidence(root, 'verified-final', sources=sources,
            files={'manifest': ref(root, path), 'wps': data['stages']['delivery']['files']['wps']})
        f.save()
        return root, data, files

    def test_full_complete_rejects_corrupt_final_ppt_and_missing_member(self):
        root, data, files = self.full()
        self.assertTrue(workflow.check(root, 'complete')['allowed'])
        audit = workflow.Inspection(root, data)
        covered = grouped_gates.final_versions(audit)
        self.assertIn(files['pptx']['path'], covered)
        self.assertIn(data['stages']['delivery']['files']['manifest']['path'], covered)
        (root / files['pptx']['path']).write_text('Accidental corruption', encoding='utf8')
        self.assertFalse(workflow.check(root, 'complete')['allowed'])

    def test_refreshed_manifest_hash_cannot_certify_a_different_final_ppt(self):
        root, data, files = self.full()
        path = data['stages']['delivery']['files']['manifest']['path']
        (root / files['pptx']['path']).write_text('Wrong copy', encoding='utf8')
        manifest = state.read_json(root / path)
        manifest['files']['pptx'] = ref(root, files['pptx']['path'])
        state.write_json(root / path, manifest)
        prior = data['stages']['delivery']
        data['stages']['delivery'] = evidence(root, 'refreshed-final', sources=prior['source_versions'],
            files={'manifest': ref(root, path), 'wps': prior['files']['wps']})
        state.write_json(root / '_state/workflow.json', data)
        self.assertFalse(workflow.check(root, 'complete')['allowed'])

    def test_manifest_must_list_every_current_material(self):
        root, data, files = self.full()
        prior = data['stages']['delivery']
        path = 'deliveries/verified-v1/incomplete-manifest.json'
        state.write_json(root / path, {'files': {'pptx': files['pptx']},
            'source_versions': prior['source_versions']})
        data['stages']['delivery'] = evidence(root, 'incomplete-package', sources=prior['source_versions'],
            files={'manifest': ref(root, path), 'wps': prior['files']['wps']})
        state.write_json(root / '_state/workflow.json', data)
        result = workflow.check(root, 'complete')
        self.assertFalse(result['allowed'])
        self.assertTrue(any('current deliverable missing' in issue for issue in result['issues']))

    def test_plain_text_manifest_cannot_certify_selected_task_completion(self):
        root, data, source, current = self.selected()
        pointer = file_ref(root, 'deliveries/unverified.md', 'All files are ready')
        data['stages']['delivery'] = evidence(root, 'unverified-final', files={'manifest': pointer},
            sources={source['path']: source['sha256']})
        state.write_json(root / '_state/workflow.json', data)
        self.assertFalse(workflow.check(root, 'complete')['allowed'])

    def test_direct_role_manifest_cannot_reuse_a_previous_task_input(self):
        root, data, source, current = self.selected()
        data['stages'].pop('documents')
        path = 'deliveries/direct-role-manifest.json'
        sources = {source['path']: source['sha256'], current['path']: current['sha256']}
        state.write_json(root / path, {'files': {'lesson-plan': current}, 'source_versions': sources})
        data['stages']['delivery'] = evidence(root, 'direct-package', files={'manifest': ref(root, path)}, sources=sources)
        state.write_json(root / '_state/workflow.json', data)
        self.assertTrue(workflow.check(root, 'complete')['allowed'])
        newer = file_ref(root, 'inputs/lesson-v2.md', '3 + 3 = 6')
        data['inputs']['documents'] = evidence(root, 'new-direct-input', files={'source': newer})
        state.write_json(root / '_state/workflow.json', data)
        self.assertFalse(workflow.check(root, 'complete')['allowed'])


if __name__ == '__main__':
    unittest.main()
