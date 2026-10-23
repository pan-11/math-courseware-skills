"""Zero-image export declarations must not borrow generation authorization/budget."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
from runtime import state, image_budget, preferences, autopilot, automation_store as store
from workflow_fixture import enable_modules


class ZeroGenerationExportTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs/autopilot-abcd1-20261004/fixtures' / ('zero-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic export', 'builtin')
        enable_modules(self.root, ['analyze', 'plan', 'editable', 'pages'])
        self.data = {'run_id': 'synthetic', 'preferences': {'editable': {
            'route': 'B', 'entry': 'full', 'evidence': 'Synthetic existing B choice'}},
            'limits': {'max_images': 1}, 'image_budget': {'entries': {'used': {}}}}
        self.data['preference_basis'] = preferences.canonical(self.root)

    def test_explicit_zero_export_ignores_exhausted_and_unknown_budget_without_image_consent(self):
        for step in ('editable-handoff', 'image-export'):
            for budget in (self.data, {k:v for k,v in self.data.items() if k not in ('limits','image_budget')}):
                with self.subTest(step=step, configured='limits' in budget):
                    before = deepcopy(budget)
                    spec = {'step': step, 'image_count': 0}
                    self.assertEqual(image_budget.task_issues(self.root, spec, budget), [])
                    self.assertEqual(preferences.task_issues(self.root, spec, budget), [])
                    self.assertEqual(budget, before)

    def test_zero_cannot_hide_real_generation_or_invalid_count(self):
        for spec in ({'step':'page-image','image_count':0},
                     {'step':'asset','image_count':0},
                     {'step':'editable-handoff','image_count':False},
                     {'step':'editable-handoff','image_count':0,'image_requests':[{'purpose':'erase'}]}):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                image_budget.validate_declaration(spec)
        positive = {'step': 'editable-handoff', 'image_count': 1}
        self.assertTrue(image_budget.task_issues(self.root, positive, self.data))
        self.assertTrue(preferences.task_issues(self.root, positive, self.data))
        self.assertTrue(image_budget.task_issues(self.root, {'step':'editable-handoff'}, self.data))

    def test_zero_declaration_can_start_and_amend_only_matching_unattempted_export(self):
        source = 'planning/source.md'
        state.resolve(self.root, source).write_text('Synthetic known images only', encoding='utf-8')
        task = {'id':'export','step':'editable-handoff','inputs':[source], 'outputs':['package'],
                'instruction':'Package existing images without generation','image_count':0}
        autopilot.start(self.root, {'activation_evidence':'Synthetic auto consent', 'tasks':[task],
                                  'preferences':self.data['preferences']})
        data = store.load_run(self.root)
        self.assertEqual(data['tasks'][0]['spec']['image_count'], 0)
        data['tasks'][0]['spec'].pop('image_count')
        image_budget.amend_declarations(data, [{'task_id':'export','image_count':0,'evidence':'Synthetic existing images'}])
        self.assertEqual(image_budget.task_spec(data['tasks'][0])['image_count'], 0)


if __name__ == '__main__':
    unittest.main()
