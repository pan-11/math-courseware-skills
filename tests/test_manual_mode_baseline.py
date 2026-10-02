"""Frozen pre-autopilot workflow behavior using retained synthetic fixtures.

Normal unittest runs only read fixtures/manual-mode-baseline-v001.json.
One-time capture before runtime edits, from repository root:
  python -B -X utf8 tests/test_manual_mode_baseline.py --capture
Capture refuses an existing baseline and any non-6437018 workflow/state source.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_workflow
from workflow_fixture import enable_modules, evidence, ref, versions
from runtime import state, workflow

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'tests/fixtures/manual-mode-baseline-v001.json'
BASE_COMMIT = '643701823368991d9dc78c2b65e8804721ab173e'


def scenarios():
    results = {}

    def fresh():
        fixture = test_workflow.WorkflowTests()
        fixture.setUp()
        return fixture

    def capture(name, fixture, step, **options):
        fixture.save()
        before = {p.relative_to(fixture.root).as_posix(): state.sha256(p)
                  for p in fixture.root.rglob('*') if p.is_file()}
        results[name] = workflow.check(fixture.root, step, **options)
        after = {p.relative_to(fixture.root).as_posix(): state.sha256(p)
                 for p in fixture.root.rglob('*') if p.is_file()}
        if before != after:
            raise AssertionError('workflow-check mutated the synthetic project: ' + name)

    fixture = fresh()
    fixture.data['project_mode'] = 'unclassified'
    fixture.data['current_task'] = {'mode': 'unclassified', 'modules': [], 'evidence': ''}
    capture('unclassified-pages', fixture, 'pages')

    fixture = fresh()
    capture('missing-analysis', fixture, 'blueprint')
    fixture.source_analysis()
    capture('analysis-ready', fixture, 'blueprint')
    source = fixture.root / fixture.data['stages']['analysis']['files']['report']['path']
    source.write_text('Synthetic revised analysis', encoding='utf-8')
    capture('analysis-stale', fixture, 'blueprint')

    fixture = fresh()
    fixture.blueprint()
    capture('blueprint-adopted', fixture, 'video-script', video_id='V001')
    approval = fixture.data['stages']['blueprint'].pop('approval')
    capture('blueprint-unapproved', fixture, 'video-script', video_id='V001')
    fixture.data['stages']['blueprint']['approval'] = approval
    state.record_approval(fixture.root, {
        'targets': list(fixture.data['stages']['blueprint']['files'].values()),
        'decision': 'rejected', 'user_evidence': 'Synthetic rejection only'})
    capture('blueprint-rejected', fixture, 'video-script', video_id='V001')

    fixture = fresh()
    fixture.prep(('V001', 'V002'))
    capture('videos-prepared-pages', fixture, 'pages')
    capture('video-files-still-required', fixture, 'complete')
    fixture.data['videos'].pop('V002')
    capture('one-preparation-missing', fixture, 'pages')

    fixture = fresh()
    fixture.prep()
    path = '_state/pages.json'
    state.write_json(fixture.root / path, {'pages': [
        {'page_id': 'P' + str(n), 'order': n,
         'video_ids': ['V001'] if n == 2 else [],
         'native_objects': [{'object_id': 'video-frame-V001'}] if n == 2 else []}
        for n in range(1, 6)]})
    fixture.data['stages']['pages'] = evidence(fixture.root, 'pages', approved=True,
        files={'pages': ref(fixture.root, path)},
        sources=versions(fixture.data['stages']['blueprint'], fixture.data['stages']['video-preparation']))
    fixture.shared_assets()
    capture('page-image-ready', fixture, 'page-image')
    fixture.data['stages']['pages'].pop('approval')
    capture('pages-unapproved', fixture, 'page-image')

    fixture = fresh()
    fixture.data = enable_modules(fixture.root, ['documents'])
    capture('documents-only', fixture, 'documents')
    capture('unrequested-pages', fixture, 'pages')
    capture('no-delivery-yet', fixture, 'complete')

    fixture = fresh()
    from fixture_factory import layered_deck
    deck = layered_deck(fixture.root)
    fixture.data = enable_modules(fixture.root, ['editable'],
        deck=deck.relative_to(fixture.root).as_posix(), route='B')
    capture('external-refill', fixture, 'editable-build')
    capture('wrong-route', fixture, 'editable-handoff', route='A')
    fixture.data['route_choice']['user_evidence'] = ''
    capture('route-without-evidence', fixture, 'editable-build')

    fixture = fresh()
    fixture.data = enable_modules(fixture.root, ['video'])
    fixture.video(route='talking', products=['script', 'first-frame'])
    capture('talking-prompts', fixture, 'video-prompts', video_id='V001')
    capture('talking-has-no-board', fixture, 'video-board', video_id='V001')
    return results


class ManualModeBaselineTests(unittest.TestCase):
    def test_pre_autopilot_workflow_contract_and_read_only_checks(self):
        expected = json.loads(BASELINE.read_text(encoding='utf-8-sig'))
        self.assertEqual(expected['source_commit'], BASE_COMMIT)
        self.assertEqual(scenarios(), expected['scenarios'])


if __name__ == '__main__':
    if sys.argv[1:] == ['--capture']:
        if BASELINE.exists():
            raise SystemExit('Baseline already exists; refusing to overwrite')
        hashes = {}
        for name in ('workflow', 'state'):
            relative = 'skills/math-courseware-studio/scripts/runtime/' + name + '.py'
            original = subprocess.run(['git', 'show', BASE_COMMIT + ':' + relative],
                                      check=True, capture_output=True).stdout.decode('utf-8')
            current = (ROOT / relative).read_text(encoding='utf-8')
            if original.replace('\r\n', '\n') != current:
                raise SystemExit('Capture requires the reviewed source: ' + relative)
            hashes[relative] = hashlib.sha256(current.encode('utf-8')).hexdigest()
        data = {'source_commit': BASE_COMMIT, 'source_text_sha256': hashes,
                'scenarios': scenarios()}
        BASELINE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'baseline': str(BASELINE), 'scenarios': len(data['scenarios'])}))
    else:
        unittest.main()
