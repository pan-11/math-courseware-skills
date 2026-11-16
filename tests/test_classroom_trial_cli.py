"""An explicit trial invocation must never silently switch the legacy workflow."""
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/math-courseware-studio/scripts'))
import courseware


class ClassroomTrialCliTests(unittest.TestCase):
    def test_trial_build_requires_exact_activation_before_reading_plan(self):
        parser = courseware.parser()
        commands = next(a.choices for a in parser._actions if getattr(a, 'choices', None))
        self.assertIn('classroom-trial-build', commands)
        base = ['classroom-trial-build', '--project', '.', '--plan', 'p.json',
                '--components-manifest', 'c.json']
        for extra in ([], ['--activation', 'v1'], ['--activation', '关闭课堂动画试用V1']):
            with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parser.parse_args(base + extra)
        args = parser.parse_args(base + ['--activation', '课堂动画试用V1'])
        self.assertEqual(args.activation, '课堂动画试用V1')

    def test_legacy_commands_have_no_implicit_trial_profile(self):
        parser = courseware.parser()
        for command, extra in [('editable-answers', ['--plan', 'legacy.json']),
                               ('animation-build', ['--plan', 'legacy.json']), ('collect', [])]:
            args = parser.parse_args([command, '--project', '.', *extra])
            self.assertFalse(hasattr(args, 'activation'))

    def test_trial_build_routes_both_plans_without_touching_legacy(self):
        from runtime import classroom_trial
        args = courseware.parser().parse_args([
            'classroom-trial-build', '--project', '.', '--activation', '课堂动画试用V1',
            '--plan', 'p.json', '--components-manifest', 'c.json'])
        with patch.object(courseware.state, 'read_json', return_value={'plan': 1}), \
             patch.object(classroom_trial, 'build', return_value={'profile': 'classroom-trial-v1'}) as build, \
             patch.object(courseware.workflow, 'require', side_effect=AssertionError('Not a legacy build')):
            result = courseware.execute(args)
        build.assert_called_once_with(Path('.').resolve(), {'plan': 1}, 'c.json', '课堂动画试用V1')
        self.assertEqual(result['profile'], 'classroom-trial-v1')

    def test_trial_register_passes_optional_checks_without_fabricating_approval(self):
        from runtime import classroom_trial
        args = courseware.parser().parse_args([
            'classroom-trial-register', '--project', '.', '--activation', '课堂动画试用V1',
            '--manifest', 'trial.json'])
        with patch.object(classroom_trial, 'register', return_value={'registered': True}) as register, \
             patch.object(courseware.state, 'record_approval', side_effect=AssertionError('No approval')):
            courseware.execute(args)
        register.assert_called_once_with(Path('.').resolve(), 'trial.json', '课堂动画试用V1', checks=None)

    def test_legacy_answer_entry_rejects_components_before_making_output(self):
        args = courseware.parser().parse_args(['editable-answers', '--project', '.', '--plan', 'p.json'])
        with patch.object(courseware.state, 'read_json', return_value={'mode': 'components_only'}), \
             patch.object(courseware.state, 'load_project', return_value={}), \
             patch.object(courseware.workflow, 'require', side_effect=AssertionError('Reject before workflow')):
            with self.assertRaisesRegex(ValueError, 'classroom-trial-components'):
                courseware.execute(args)


if __name__ == '__main__':
    unittest.main()
