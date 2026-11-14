"""Standalone animation scope must not require fictitious full-course approvals."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/math-courseware-studio/scripts'
sys.path.insert(0, str(SCRIPTS))
import courseware


class ClassroomAnimationCliTests(unittest.TestCase):
    def test_new_commands_have_explicit_inputs_and_no_implicit_mode_switch(self):
        parser = courseware.parser()
        sub = next(a for a in parser._actions if getattr(a, 'choices', None))
        for command in ('animation-inspect', 'animation-check', 'animation-build',
                        'animation-validate', 'animation-snapshot'):
            self.assertIn(command, sub.choices, 'Approved standalone animation entrypoint is missing')
        args = parser.parse_args(['animation-build', '--project', 'sample', '--plan', 'plan.json'])
        self.assertEqual(args.command, 'animation-build')
        self.assertEqual(args.plan, Path('plan.json'))
        self.assertEqual(parser.parse_args(['editable-answers', '--project', 'sample',
                                           '--plan', 'old-plan.json']).command, 'editable-answers')

    def test_standalone_check_does_not_register_as_final_product(self):
        self.assertIsNotNone(importlib.util.find_spec('runtime.classroom_animation'))
        from runtime import classroom_animation
        args = courseware.parser().parse_args(['animation-check', '--project', '.', '--plan', 'plan.json'])
        with patch.object(courseware.state, 'read_json', return_value={'fixture': True}), \
             patch.object(courseware.state, 'load_project', side_effect=AssertionError('Must not fabricate a course')), \
             patch.object(classroom_animation, 'check', return_value={'ready_for_review': True}) as check:
            result = courseware.execute(args)
        self.assertTrue(result['ready_for_review'])
        check.assert_called_once_with(Path('.').resolve(), {'fixture': True})

    def test_snapshot_requires_explicit_stage_and_new_output(self):
        parser = courseware.parser()
        sub = next(a for a in parser._actions if getattr(a, 'choices', None))
        self.assertIn('animation-snapshot', sub.choices)
        args = parser.parse_args(['animation-snapshot', '--project', '.', '--manifest', 'sample.manifest.json',
                                 '--output', 'snapshots/final.pptx', '--stage', 'final'])
        self.assertEqual(args.stage, 'final')
        self.assertEqual(args.output, 'snapshots/final.pptx')


if __name__ == '__main__':
    unittest.main()
