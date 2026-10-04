"""Actual human/reviewer pairings, retained synthetic fixtures and recovery only."""
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
from runtime import state, autopilot, review, automation_store as store
from workflow_fixture import enable_modules


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'tests/runs/autopilot-abcd1-20261004/fixtures' / ('c-' + uuid.uuid4().hex)
        state.init_project(self.root, 'Synthetic calibration', layout='four-folders')
        enable_modules(self.root / '02_work', ['analyze'])
        self.source = self.file('source', 'Synthetic source: 2 + 3 = 5.')
        self.artifact = self.file('artifact', 'Synthetic current result.')

    def file(self, name, text='Synthetic retained output.'):
        relative = 'planning/' + name + '.md'
        state.resolve(self.root, relative).write_text(text, encoding='utf-8')
        return relative

    def task(self, name='analysis', **extra):
        return dict(id=name, step='analysis', inputs=[self.source], outputs=['report'],
                    instruction='Read only the synthetic supplied source.', **extra)

    def start(self, tasks=None, **extra):
        self.plan = dict(activation_evidence='Synthetic actual activation',
                         tasks=tasks or [self.task()], **extra)
        return autopilot.start(self.root, self.plan)

    def packet(self, verdict='pass', artifacts=None):
        result = review.prepare(self.root, dict(producer_id='synthetic-maker', rubric='source',
            artifacts=artifacts or [self.artifact], sources=[self.source], instruction='Synthetic actual inspection'))
        self.record_review(result['packet'], verdict)
        return result['packet']

    def record_review(self, packet, verdict='pass'):
        path = state.resolve(self.root, packet)
        data = state.read_json(path)
        report = dict(packet_sha256=state.sha256(path), reviewer_id='synthetic-reader',
                      method='independent_agent', source_versions=data['versions'],
                      checks=[dict(id=c['id'], verdict=verdict, evidence=data['artifacts'],
                                   note='Synthetic actual observed evidence') for c in data['criteria']])
        review.record(self.root, packet, report)

    def approval(self, decision='approved', packet=None, artifacts=None, **extra):
        record = dict(targets=[dict(path=p, sha256=state.sha256(state.resolve(self.root, p)))
                               for p in artifacts or [self.artifact]],
                      decision=decision, user_evidence='Synthetic actual ' + decision,
                      stage='C3', human_node='H06', **extra)
        if packet is not None: record['review_packet'] = packet
        return state.record_approval(self.root, record)

    def rows(self):
        data = store.load_run(self.root)
        return state.read_lines(state.resolve(self.root, store.AREA + '/runs/' + data['run_id'] + '/calibration.jsonl'))

    def files(self):
        return {p.relative_to(self.root).as_posix(): (state.sha256(p), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def human(self):
        self.start([self.task('human', kind='human', stage='C3', human_node='H06')])
        return autopilot.next_task(self.root, 'host')['human_tasks'][0]

    def receipt(self, action, **extra):
        return dict(task_id='human', claim=action['claim'], status='completed',
                    artifacts={'report': self.artifact}, user_evidence='Synthetic actual response', **extra)

    def test_status_has_zero_sample_counts_without_default_limit_vote(self):
        result = self.start()
        self.assertIn('calibration', result, 'run-status must expose real human/reviewer calibration')
        stats = result['calibration']
        self.assertEqual(stats['total'], 0)
        self.assertEqual(stats['comparable'], 0)
        self.assertIsNone(stats['agreement_rate'])
        self.assertEqual(stats['missing_event_ids'], [])
        self.assertEqual(self.rows(), [])

    def test_four_binary_combinations_and_separate_disagreement_counts(self):
        self.start()
        for i, (verdict, decision, agreement) in enumerate([
                ('pass', 'approved', True), ('changes_required', 'rejected', True),
                ('pass', 'rejected', False), ('changes_required', 'approved', False)]):
            artifact = self.file('case-' + str(i))
            packet = self.packet(verdict, [artifact])
            self.approval(decision, packet, [artifact])
            self.assertEqual(self.rows()[-1]['agreement'], agreement)
        stats = autopilot.status(self.root)['calibration']['by_stage']['C3']
        self.assertEqual((stats['agreed'], stats['disagreed'], stats['comparable']), (2, 2, 4))
        self.assertEqual(stats['agreement_rate'], .5)
        self.assertEqual(stats['pass_human_rejected'], 1)
        self.assertEqual(stats['changes_required_human_approved'], 1)

    def test_rejection_freezes_valid_review_before_invalidation_and_keeps_real_reason(self):
        self.start(); packet = self.packet()
        entry = self.approval('rejected', packet, human_reason='Synthetic visible math error')
        self.assertFalse(review.status(self.root, packet)['valid'])
        row = self.rows()[0]
        self.assertFalse(row['agreement'])
        self.assertEqual(row['human_reason'], 'Synthetic visible math error')
        self.assertEqual(row['reviewer_id'], 'synthetic-reader')
        self.assertEqual(row['decision_id'], entry['decision_id'])
        self.assertEqual(row, entry['calibration_event'])
        self.assertFalse(state.is_approved(self.root, self.artifact))

    def test_missing_and_unverified_review_do_not_enter_denominator(self):
        self.start(); self.approval()
        second = self.file('second')
        self.approval(packet=self.packet('unverified', [second]), artifacts=[second])
        stats = autopilot.status(self.root)['calibration']
        self.assertEqual((stats['total'], stats['unpaired'], stats['comparable']), (2, 2, 0))
        self.assertIsNone(stats['agreement_rate'])
        self.assertTrue(all(r['human_reason'] is None and r['agreement'] is None for r in self.rows()))

    def test_same_path_new_hash_never_pairs_old_review(self):
        self.start(); packet = self.packet()
        state.resolve(self.root, self.artifact).write_text('A genuinely different version.', encoding='utf-8')
        self.approval(packet=packet)
        row = self.rows()[0]
        self.assertEqual(row['pair_status'], 'unpaired')
        self.assertIsNone(row['agreement'])
        self.assertEqual(row['artifacts'][0]['sha256'], state.sha256(state.resolve(self.root, self.artifact)))

    def test_late_review_is_not_backfilled_and_history_does_not_follow_files(self):
        self.start(); self.approval()
        before = self.rows()
        self.packet()
        autopilot.control(self.root, paused=True, evidence='Actual synthetic pause')
        state.resolve(self.root, self.artifact).write_text('Changed after decision.', encoding='utf-8')
        self.assertEqual(self.rows(), before)
        self.assertEqual(autopilot.status(self.root)['calibration']['unpaired'], 1)

    def test_explicit_packets_must_cover_whole_bundle_exactly(self):
        self.start(); other = self.file('other')
        first = self.packet(artifacts=[self.artifact]); second = self.packet(artifacts=[other])
        entry = self.approval(artifacts=[other, self.artifact], review_packets=[second, first])
        row = self.rows()[0]
        self.assertTrue(row['agreement'])
        self.assertEqual(len(row['reviews']), 2)
        self.assertEqual(row['artifacts'], sorted(entry['targets'], key=lambda item: item['path']))
        self.assertEqual(row['version_hash'], state.digest(row['artifacts']))

    def test_partial_or_extra_review_coverage_is_unpaired(self):
        self.start(); other = self.file('other')
        packet = self.packet(artifacts=[self.artifact, other])
        self.approval(packet=packet)
        self.assertEqual(self.rows()[0]['unpaired_reason'], 'artifact_coverage_mismatch')

    def test_no_reference_does_not_scan_for_favorable_packet(self):
        self.start(); self.packet('pass'); self.packet('changes_required')
        self.approval()
        self.assertEqual(self.rows()[0]['unpaired_reason'], 'no_review_reference')

    def test_tampered_report_and_packet_are_unpaired(self):
        self.start(); packet = self.packet()
        path = state.resolve(self.root, packet).with_name('result.json')
        data = state.read_json(path); data['verdict'] = 'changes_required'; state.write_json(path, data)
        self.approval(packet=packet)
        self.assertIsNone(self.rows()[-1]['agreement'])
        other = self.file('other'); packet = self.packet(artifacts=[other])
        path = state.resolve(self.root, packet)
        data = state.read_json(path); data['instruction'] = 'Changed after review'; state.write_json(path, data)
        self.approval(packet=packet, artifacts=[other])
        self.assertIsNone(self.rows()[-1]['agreement'])

    def test_approval_replay_and_change_of_mind_are_distinct_occurrences(self):
        self.start()
        first = self.approval(); replay = self.approval()
        self.assertEqual(first, replay)
        self.approval('rejected'); last = self.approval()
        self.assertEqual(first['decision_id'], last['decision_id'])
        self.assertEqual(len(self.rows()), 3)
        self.assertNotEqual(self.rows()[0]['event_id'], self.rows()[2]['event_id'])

    def test_approval_then_receipt_links_exact_occurrence_without_second_vote(self):
        action = self.human(); packet = self.packet()
        entry = self.approval(packet=packet)
        result = self.receipt(action, decision_id=entry['decision_id'], human_decision='approved')
        autopilot.record(self.root, result); autopilot.record(self.root, result)
        self.assertEqual(len(self.rows()), 1)
        self.assertTrue(self.rows()[0]['agreement'])

    def test_link_rejects_different_artifact_before_saving(self):
        action = self.human(); entry = self.approval()
        other = self.file('other'); result = self.receipt(action, decision_id=entry['decision_id'])
        result['artifacts'] = {'report': other}
        before = self.files()
        with self.assertRaises(ValueError): autopilot.record(self.root, result)
        self.assertEqual(self.files(), before)

    def test_operation_and_partial_receipts_are_unpaired(self):
        action = self.human(); packet = self.packet()
        autopilot.record(self.root, self.receipt(action, review_packet=packet))
        row = self.rows()[0]
        self.assertEqual(row['human_decision'], 'operation_completed')
        self.assertEqual(row['unpaired_reason'], 'nonbinary_human_decision')

    def test_status_is_read_only_even_with_missing_calibration_append(self):
        self.start(); packet = self.packet()
        original = state.append_line
        def interrupt(path, value):
            if Path(path).name == 'calibration.jsonl': raise OSError('Synthetic interrupted append')
            original(path, value)
        with patch.object(state, 'append_line', side_effect=interrupt):
            with self.assertRaises(OSError): self.approval('rejected', packet)
        before = self.files()
        result = autopilot.status(self.root)['calibration']
        self.assertEqual(len(result['missing_event_ids']), 1)
        self.assertEqual(result['total'], 0)
        self.assertEqual(before, self.files())
        autopilot.control(self.root, paused=True, evidence='Synthetic pause and recovery')
        self.assertEqual(len(self.rows()), 1)
        self.assertFalse(self.rows()[0]['agreement'])
        self.assertEqual(autopilot.status(self.root)['calibration']['missing_event_ids'], [])

    def test_append_completed_before_interruption_recovers_without_duplicate(self):
        self.start(); original = state.append_line
        def interrupt(path, value):
            original(path, value)
            if Path(path).name == 'calibration.jsonl': raise OSError('Synthetic lost acknowledgement')
        with patch.object(state, 'append_line', side_effect=interrupt):
            with self.assertRaises(OSError): self.approval()
        self.approval()
        autopilot.next_task(self.root, 'host')
        self.assertEqual(len(self.rows()), 1)

    def test_receipt_snapshot_recovers_and_replay_deduplicates(self):
        action = self.human(); result = self.receipt(action)
        original = state.append_line
        def interrupt(path, value):
            if Path(path).name == 'calibration.jsonl': raise OSError('Synthetic receipt append interruption')
            original(path, value)
        with patch.object(state, 'append_line', side_effect=interrupt):
            with self.assertRaises(OSError): autopilot.record(self.root, result)
        autopilot.record(self.root, result)
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(autopilot.status(self.root)['calibration']['missing_event_ids'], [])

    def test_active_manual_records_but_absent_run_keeps_original_no_automation_path(self):
        self.approval()
        self.assertFalse(state.resolve(self.root, store.AREA).exists())
        self.start(); autopilot.control(self.root, mode='manual', evidence='Synthetic mode choice')
        self.approval('rejected')
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'manual')

    def test_settings_startup_and_configure_replay_record_actual_choices_only(self):
        choice = {'video': {'platform': 'Synthetic platform', 'evidence': 'Actual synthetic platform choice'}}
        self.start(preferences=choice)
        self.assertEqual(len(self.rows()), 1)
        autopilot.start(self.root, self.plan); autopilot.configure(self.root, choice)
        self.assertEqual(len(self.rows()), 1)
        autopilot.configure(self.root, {'limits': {'max_images': 80, 'evidence': 'Actual synthetic 80 limit'}})
        self.assertEqual(len(self.rows()), 2)
        self.assertTrue(all(r['agreement'] is None for r in self.rows()))
        self.assertEqual(self.rows()[-1]['settings_snapshot']['limits']['max_images'], 80)

    def test_declaration_only_never_invents_human_choice(self):
        self.start()
        autopilot.configure(self.root, {'image_declarations': [dict(task_id='analysis', image_count=2,
                                                                   evidence='Host future quantity basis')]})
        self.assertEqual(self.rows(), [])

    def test_mixed_invalid_settings_persist_nothing_including_calibration(self):
        self.start(); before = self.files()
        with self.assertRaises(ValueError):
            autopilot.configure(self.root, {'video': {'platform': 'Synthetic', 'evidence': 'Actual choice'},
                                            'limits': {'max_images': -1, 'evidence': 'Actual bad limit'}})
        self.assertEqual(before, self.files())

    def test_callers_cannot_supply_calibration_or_reviewer_conclusions(self):
        action = self.human(); before = self.files()
        for extra in ({'calibration_event': {'agreement': True}}, {'reviewer_verdict': 'pass'}):
            with self.assertRaises(ValueError): self.approval(**extra)
            with self.assertRaises(ValueError): autopilot.record(self.root, self.receipt(action, **extra))
        self.assertEqual(before, self.files())

    def test_returned_partial_and_rejection_stay_waiting_until_real_completion(self):
        action = self.human(); packet = self.packet()
        returned = self.receipt(action, human_decision='partial_approved', review_packet=packet)
        returned['status'] = 'returned'
        self.assertEqual(autopilot.record(self.root, returned)['status'], 'waiting_external')
        autopilot.record(self.root, returned)
        self.assertEqual(len(self.rows()), 1)
        self.assertIsNone(self.rows()[0]['agreement'])
        rejection = {**returned, 'human_decision': 'rejected', 'human_reason': 'Actual synthetic objection'}
        autopilot.record(self.root, rejection)
        self.assertFalse(self.rows()[-1]['agreement'])
        self.assertFalse(autopilot.status(self.root)['queue_complete'])
        completed = self.receipt(action, human_decision='approved', review_packet=packet)
        self.assertEqual(autopilot.record(self.root, completed)['status'], 'done')
        self.assertEqual(len(self.rows()), 3)

    def test_rejected_and_partial_decisions_cannot_use_completed(self):
        action = self.human(); before = self.files()
        for choice in ('rejected', 'partial_approved', 'partial_rejected', 'changes_required'):
            with self.assertRaises(ValueError):
                autopilot.record(self.root, self.receipt(action, human_decision=choice))
        self.assertEqual(before, self.files())

    def test_returned_does_not_resolve_producer_or_unknown_submission(self):
        self.start(); action = autopilot.next_task(self.root, 'maker')
        result = self.receipt(action, human_decision='rejected')
        result.update(task_id='analysis', status='returned')
        with self.assertRaises(ValueError): autopilot.record(self.root, result)
        autopilot.record(self.root, dict(task_id='analysis', claim=action['claim'], status='unknown',
                                         message='Actual synthetic unknown external outcome'))
        before = self.files()
        with self.assertRaises(ValueError): autopilot.record(self.root, result)
        self.assertEqual(before, self.files())

    def test_returned_links_already_rejected_approval_without_new_vote(self):
        action = self.human(); packet = self.packet()
        entry = self.approval('rejected', packet)
        result = self.receipt(action, decision_id=entry['decision_id'], human_decision='rejected')
        result['status'] = 'returned'
        self.assertEqual(autopilot.record(self.root, result)['status'], 'waiting_external')
        self.assertEqual(len(self.rows()), 1)
        self.assertFalse(self.rows()[0]['agreement'])

    def test_reused_decision_id_requires_occurrence_for_receipt_pairing(self):
        action = self.human()
        first = self.approval(); self.approval('rejected'); last = self.approval()
        self.assertEqual(first['decision_id'], last['decision_id'])
        result = self.receipt(action, decision_id=last['decision_id'],
                              decision_event_id=last['calibration_event']['event_id'], human_decision='approved')
        autopilot.record(self.root, result)
        self.assertEqual(len(self.rows()), 3)

    def test_ambiguous_decision_id_is_honestly_unpaired(self):
        action = self.human()
        first = self.approval(); self.approval('rejected'); self.approval()
        autopilot.record(self.root, self.receipt(action, decision_id=first['decision_id'], human_decision='approved'))
        self.assertEqual(self.rows()[-1]['unpaired_reason'], 'ambiguous_decision_occurrence')
        self.assertIsNone(self.rows()[-1]['agreement'])

    def test_receipt_then_explicitly_linked_approval_preserves_original_snapshot(self):
        action = self.human()
        autopilot.record(self.root, self.receipt(action, human_decision='approved'))
        row = self.rows()[0]
        packet = self.packet()  # Too late to describe what the human originally saw.
        entry = self.approval(packet=packet, human_event_id=row['event_id'])
        self.assertEqual(entry['calibration_event']['event_id'], row['event_id'])
        self.assertEqual(self.rows(), [row])
        self.assertTrue(state.is_approved(self.root, self.artifact))

    def test_revision_durable_before_run_pointer_interruption_is_recovered_once(self):
        action = self.human(); packet = self.packet()
        result = self.receipt(action, review_packet=packet, human_decision='approved')
        write = state.write_json
        def fail_pointer(path, value):
            if Path(path).name == 'run.json': raise OSError('Synthetic after durable revision')
            return write(path, value)
        with patch.object(state, 'write_json', side_effect=fail_pointer):
            with self.assertRaises(OSError): autopilot.record(self.root, result)
        self.assertEqual(len(autopilot.status(self.root)['calibration']['missing_event_ids']), 1)
        autopilot.control(self.root, paused=True, evidence='Actual recovery pause')
        historical = self.rows()[0]
        autopilot.record(self.root, result)
        self.assertEqual(self.rows(), [historical])
        self.assertTrue(historical['agreement'])

    def test_settings_hash_and_actual_changed_mind_are_versioned(self):
        first = {'video': {'platform': 'one', 'evidence': 'Actual first choice'}}
        self.start(preferences=first)
        autopilot.configure(self.root, {'video': {'platform': 'two', 'evidence': 'Actual changed choice'}})
        autopilot.configure(self.root, first)
        rows = self.rows()
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({r['event_id'] for r in rows}), 3)
        self.assertTrue(all(r['version_hash'] == r['settings_hash'] for r in rows))
        self.assertNotEqual(rows[0]['version_hash'], rows[1]['version_hash'])

    def test_stage_statistics_separate_video_and_page_decisions(self):
        self.start(); packet = self.packet()
        self.approval(packet=packet)
        other = self.file('page')
        record = dict(targets=[dict(path=other, sha256=state.sha256(state.resolve(self.root, other)))],
                      decision='rejected', user_evidence='Actual synthetic page rejection', stage='C5', human_node='H14',
                      review_packet=self.packet(artifacts=[other]))
        state.record_approval(self.root, record)
        stages = autopilot.status(self.root)['calibration']['by_stage']
        self.assertEqual(stages['C3']['agreement_rate'], 1)
        self.assertEqual(stages['C5']['agreement_rate'], 0)
        self.assertEqual(stages['C5']['pass_human_rejected'], 1)

    def test_old_receipt_link_cannot_reuse_vote_after_actual_rejection(self):
        action = self.human()
        autopilot.record(self.root, self.receipt(action, human_decision='approved'))
        original = self.rows()[0]
        self.approval(human_event_id=original['event_id'])
        self.approval('rejected')
        before = self.files()
        with self.assertRaises(ValueError): self.approval(human_event_id=original['event_id'])
        self.assertEqual(before, self.files())
        self.approval()  # A later actual changed mind is a new event.
        self.assertEqual(len(self.rows()), 3)

    def test_old_explicit_approval_occurrence_cannot_replace_current_one(self):
        action = self.human()
        first = self.approval(); self.approval('rejected'); self.approval()
        result = self.receipt(action, decision_id=first['decision_id'],
            decision_event_id=first['calibration_event']['event_id'], human_decision='approved')
        before = self.files()
        with self.assertRaises(ValueError): autopilot.record(self.root, result)
        self.assertEqual(before, self.files())

    def test_request_for_changes_is_binary_rejection_but_keeps_original_words(self):
        action = self.human(); packet = self.packet('changes_required')
        result = self.receipt(action, human_decision='changes_required', review_packet=packet)
        result['status'] = 'returned'
        autopilot.record(self.root, result)
        row = self.rows()[0]
        self.assertTrue(row['agreement'])
        self.assertEqual(row['human_decision'], 'changes_required')
        self.assertEqual(row['human_outcome'], 'rejected')
        self.approval('rejected', human_event_id=row['event_id'])
        self.assertEqual(self.rows(), [row])

    def dependent_human(self):
        self.start([self.task('producer'), self.task('human', kind='human', depends_on=['producer'])])
        producer = autopilot.next_task(self.root, 'synthetic-maker')
        produced = autopilot.record(self.root, dict(task_id='producer', claim=producer['claim'],
            status='produced', artifacts={'report': self.artifact}))
        self.record_review(produced['packet'])
        return autopilot.next_task(self.root, 'host')['human_tasks'][0], produced['packet']

    def dependent_rejection(self, persist_first=False):
        action, packet = self.dependent_human()
        entry = self.approval('rejected', packet)
        result = self.receipt(action, human_decision='rejected', decision_id=entry['decision_id'],
                              decision_event_id=entry['calibration_event']['event_id'])
        result['status'] = 'returned'
        if persist_first:
            blocked = autopilot.next_task(self.root, 'host')
            self.assertEqual(blocked['action'], 'waiting')
            self.assertEqual(blocked['human_tasks'][0]['claim'], action['claim'])
            self.assertIn('An upstream task is stale', blocked['human_tasks'][0]['issues'])
            self.assertTrue(blocked['human_tasks'][0]['blocked_by_upstream'])
        recorded = autopilot.record(self.root, result)
        self.assertEqual(recorded['status'], 'waiting_external')
        self.assertEqual(recorded['claim'], action['claim'])
        autopilot.record(self.root, result)
        current = autopilot.status(self.root)
        self.assertEqual([t['status'] for t in current['tasks']], ['stale', 'waiting_external'])
        self.assertIn('An upstream task is stale', current['tasks'][1]['issues'])
        self.assertEqual(len(self.rows()), 1)
        self.assertFalse(self.rows()[0]['agreement'])
        self.assertEqual(current['tasks'][0]['attempt'], 1)
        self.assertFalse(current['queue_complete'])
        with self.assertRaises(ValueError):
            autopilot.record(self.root, {**result, 'status': 'completed', 'human_decision': 'approved'})
        self.assertEqual(autopilot.next_task(self.root, 'host')['action'], 'waiting')
        return result

    def test_dependent_human_rejection_keeps_actual_receipt_channel(self):
        self.dependent_rejection()

    def test_dependent_human_rejection_after_run_next_persists_waiting_and_block(self):
        self.dependent_rejection(persist_first=True)

    def test_blocked_human_return_rejects_changed_artifact_version(self):
        action, packet = self.dependent_human()
        entry = self.approval('rejected', packet)
        autopilot.next_task(self.root, 'host')
        state.resolve(self.root, self.artifact).write_text('Changed after this claim.', encoding='utf-8')
        result = self.receipt(action, human_decision='rejected', decision_id=entry['decision_id'])
        result['status'] = 'returned'
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'Changed artifact'):
            autopilot.record(self.root, result)
        self.assertEqual(before, self.files())

    def test_completed_human_is_not_reopened_when_producer_is_rejected(self):
        action, packet = self.dependent_human()
        autopilot.record(self.root, self.receipt(action))
        entry = self.approval('rejected', packet)
        current = autopilot.next_task(self.root, 'host')
        self.assertEqual(current['human_tasks'], [])
        result = self.receipt(action, human_decision='rejected', decision_id=entry['decision_id'])
        result['status'] = 'returned'
        before = self.files()
        with self.assertRaises(ValueError): autopilot.record(self.root, result)
        self.assertEqual(before, self.files())

    def test_interleaved_unrelated_approval_replay_is_one_original_event(self):
        self.start(); first = self.approval()
        other = self.file('other'); self.approval(artifacts=[other])
        replay = self.approval()
        self.assertEqual(replay, first)
        self.assertEqual(len(self.rows()), 2)
        self.assertEqual(len(state.read_lines(state.resolve(self.root, '_state/decisions.jsonl'))), 2)

    def test_interleaved_subset_rejection_then_group_approval_is_a_new_event(self):
        self.start(); member = self.file('group-member')
        group = [self.artifact, member]
        first = self.approval(artifacts=group)
        unrelated = self.file('unrelated'); self.approval(artifacts=[unrelated])
        self.approval('rejected', artifacts=[member])
        another = self.file('another'); self.approval(artifacts=[another])
        latest = self.approval(artifacts=group)
        self.assertEqual(first['decision_id'], latest['decision_id'])
        self.assertNotEqual(first['calibration_event']['event_id'], latest['calibration_event']['event_id'])
        self.assertEqual(len(self.rows()), 5)
        self.assertTrue(all(state.is_approved(self.root, path) for path in group))
        self.assertEqual(self.approval(artifacts=group), latest)

    def test_unchanged_subset_approval_does_not_turn_group_replay_into_new_vote(self):
        self.start(); member = self.file('group-member')
        first = self.approval(artifacts=[self.artifact, member])
        self.approval(artifacts=[member])
        self.assertEqual(self.approval(artifacts=[self.artifact, member]), first)
        self.assertEqual(len(self.rows()), 2)

    def test_interleaved_approval_and_receipt_link_keep_one_occurrence(self):
        action = self.human(); entry = self.approval()
        unrelated = self.file('unrelated'); self.approval(artifacts=[unrelated])
        autopilot.record(self.root, self.receipt(action, decision_id=entry['decision_id'], human_decision='approved'))
        self.assertEqual(self.approval(), entry)
        self.assertEqual(len(self.rows()), 2)

    def test_later_human_returned_rejection_makes_reapproval_a_new_event(self):
        action = self.human(); first = self.approval()
        returned = self.receipt(action, human_decision='changes_required'); returned['status'] = 'returned'
        autopilot.record(self.root, returned)
        latest = self.approval()
        self.assertNotEqual(first['calibration_event']['event_id'], latest['calibration_event']['event_id'])
        self.assertEqual(len(self.rows()), 3)

    def test_blocked_human_return_rejects_changed_source_selection(self):
        path = state.resolve(self.root, '_state/workflow.json')
        data = state.read_json(path)
        data['stages']['synthetic-selection'] = {'files': {'report': {
            'path': self.artifact, 'sha256': state.sha256(state.resolve(self.root, self.artifact))}}}
        state.write_json(path, data)
        action, packet = self.dependent_human()
        entry = self.approval('rejected', packet)
        other = self.file('selected-new-version')
        data['stages']['synthetic-selection']['files']['report'] = {
            'path': other, 'sha256': state.sha256(state.resolve(self.root, other))}
        state.write_json(path, data)
        autopilot.next_task(self.root, 'host')
        result = self.receipt(action, human_decision='rejected', decision_id=entry['decision_id'])
        result['status'] = 'returned'
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'Current source selection changed'):
            autopilot.record(self.root, result)
        self.assertEqual(before, self.files())

    def test_unknown_human_submission_does_not_reopen_as_returned_on_rejection(self):
        action, packet = self.dependent_human()
        autopilot.record(self.root, dict(task_id='human', claim=action['claim'], status='unknown',
                                        message='Synthetic external result remains unknown'))
        entry = self.approval('rejected', packet)
        self.assertEqual(autopilot.next_task(self.root, 'host')['human_tasks'], [])
        result = self.receipt(action, human_decision='rejected', decision_id=entry['decision_id'])
        result['status'] = 'returned'
        before = self.files()
        with self.assertRaises(ValueError): autopilot.record(self.root, result)
        self.assertEqual(before, self.files())

    def test_metadata_only_approval_replay_cannot_pair_a_late_review(self):
        self.start(); first = self.approval()
        packet = self.packet()
        self.assertEqual(self.approval(packet=packet), first)
        request = {key: value for key, value in first.items()
                   if key not in ('decision_id', 'recorded_at', 'calibration_event')}
        request.update(stage='C5', human_node='H14', human_reason='Later explanatory annotation',
                       review_packets=[packet])
        self.assertEqual(state.record_approval(self.root, request), first)
        self.assertEqual(self.rows(), [first['calibration_event']])
        self.assertEqual(autopilot.status(self.root)['calibration']['comparable'], 0)

    def test_metadata_only_replacement_report_keeps_original_pairing(self):
        self.start(); first = self.approval(packet=self.packet('changes_required'))
        self.assertEqual(self.approval(packet=self.packet('pass')), first)
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0]['reviewer_verdict'], 'changes_required')
        self.assertFalse(self.rows()[0]['agreement'])

    def test_metadata_only_returned_receipt_keeps_original_unpaired_event(self):
        action = self.human()
        result = self.receipt(action, human_decision='rejected'); result['status'] = 'returned'
        autopilot.record(self.root, result)
        original = self.rows()[0]; packet = self.packet()
        repeated = autopilot.record(self.root, {**result, 'review_packet': packet,
            'stage': 'C5', 'human_node': 'H14', 'human_reason': 'Later explanation'})
        self.assertEqual(repeated['status'], 'waiting_external')
        self.assertEqual(self.rows(), [original])
        self.assertIsNone(original['human_reason'])
        self.assertIsNone(original['agreement'])

    def test_metadata_only_completed_receipt_does_not_reopen_task(self):
        action = self.human(); result = self.receipt(action, human_decision='approved')
        autopilot.record(self.root, result)
        original = self.rows()[0]; packet = self.packet()
        self.assertEqual(autopilot.record(self.root, {**result, 'review_packet': packet})['status'], 'done')
        self.assertEqual(self.rows(), [original])
        self.assertTrue(autopilot.status(self.root)['queue_complete'])

    def test_metadata_only_linked_receipt_replay_keeps_canonical_occurrence(self):
        action = self.human(); first = self.approval('rejected')
        result = self.receipt(action, human_decision='rejected', decision_id=first['decision_id'])
        result['status'] = 'returned'; autopilot.record(self.root, result)
        repeated = {**result, 'stage': 'C5', 'human_node': 'H14'}
        self.assertEqual(autopilot.record(self.root, repeated)['status'], 'waiting_external')
        self.assertEqual(self.rows(), [first['calibration_event']])

    def test_metadata_only_replay_after_real_changed_mind_keeps_new_occurrence(self):
        action = self.human(); first = self.approval()
        returned = self.receipt(action, human_decision='changes_required'); returned['status'] = 'returned'
        autopilot.record(self.root, returned)
        latest = self.approval(packet=self.packet())
        self.assertNotEqual(first['calibration_event']['event_id'], latest['calibration_event']['event_id'])
        self.assertEqual(self.approval(human_reason='Later annotation'), latest)
        self.assertEqual(len(self.rows()), 3)

    def test_event_sequence_equal_times_cannot_revive_old_receipt_link(self):
        action = self.human()
        with patch.object(state, 'now', return_value='2026-10-05T01:00:00+00:00'):
            autopilot.record(self.root, self.receipt(action, human_decision='approved'))
            original = self.rows()[0]
            self.approval(human_event_id=original['event_id']); self.approval('rejected')
            before = self.files()
            with self.assertRaisesRegex(ValueError, 'supersedes'):
                self.approval(human_event_id=original['event_id'])
            self.assertEqual(before, self.files())
        self.assertFalse(state.is_approved(self.root, self.artifact))
        self.assertEqual([row['event_seq'] for row in self.rows()], [1, 2])

    def test_event_sequence_clock_rollback_cannot_revive_old_approval_link(self):
        action = self.human()
        with patch.object(state, 'now', return_value='2026-10-05T02:00:00+00:00'):
            first = self.approval()
        with patch.object(state, 'now', return_value='2026-10-05T01:00:00+00:00'):
            self.approval('rejected')
            latest = self.approval()
            before = self.files()
            with self.assertRaisesRegex(ValueError, 'supersedes'):
                autopilot.record(self.root, self.receipt(action, human_decision='approved',
                    decision_id=first['decision_id'], decision_event_id=first['calibration_event']['event_id']))
            self.assertEqual(before, self.files())
        self.assertEqual([row['event_seq'] for row in self.rows()], [1, 2, 3])
        self.assertNotEqual(first['calibration_event']['event_id'], latest['calibration_event']['event_id'])

    def test_event_sequence_uses_durable_revision_before_pointer_and_preserves_on_recovery(self):
        action = self.human(); result = self.receipt(action, human_decision='approved')
        write = state.write_json
        def interrupt(path, value):
            if Path(path).name == 'run.json': raise OSError('Synthetic durable revision before pointer')
            return write(path, value)
        with patch.object(state, 'write_json', side_effect=interrupt):
            with self.assertRaises(OSError): autopilot.record(self.root, result)
        other = self.file('unrelated-sequence'); self.approval(artifacts=[other])
        rows = self.rows()
        self.assertEqual([row['event_seq'] for row in rows], [1, 2])
        autopilot.record(self.root, {**result, 'stage': 'C5'})
        self.assertEqual(self.rows(), rows)
        self.assertTrue(autopilot.status(self.root)['queue_complete'])

    def test_event_sequence_same_receipt_after_intervening_opinion_is_new_each_time(self):
        action = self.human()
        result = self.receipt(action, human_decision='rejected'); result['status'] = 'returned'
        with patch.object(state, 'now', return_value='2026-10-05T01:00:00+00:00'):
            autopilot.record(self.root, result)
            self.approval(); autopilot.record(self.root, result)
            self.approval(); autopilot.record(self.root, result)
        self.assertEqual(len(self.rows()), 5)
        self.assertEqual([row['event_seq'] for row in self.rows()], [1, 2, 3, 4, 5])
        self.assertEqual(len({row['event_id'] for row in self.rows()}), 5)
        autopilot.record(self.root, {**result, 'stage': 'C5'})
        self.assertEqual(len(self.rows()), 5)

    def test_event_sequence_cannot_be_supplied_by_caller(self):
        action = self.human(); before = self.files()
        with self.assertRaises(ValueError): self.approval(event_seq=100)
        with self.assertRaises(ValueError): autopilot.record(self.root, self.receipt(action, event_seq=100))
        self.assertEqual(before, self.files())

    def test_explicit_link_old_receipt_is_checked_before_approval_replay(self):
        action = self.human()
        result = self.receipt(action, human_decision='approved'); result['status'] = 'returned'
        autopilot.record(self.root, result)
        original = self.rows()[0]
        self.approval(human_event_id=original['event_id']); self.approval('rejected'); self.approval()
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'supersedes'):
            self.approval(human_event_id=original['event_id'])
        self.assertEqual(before, self.files())

    def test_explicit_link_old_approval_is_checked_before_receipt_replay(self):
        action = self.human(); first = self.approval('rejected')
        result = self.receipt(action, human_decision='rejected', decision_id=first['decision_id'])
        result['status'] = 'returned'
        autopilot.record(self.root, {**result, 'decision_event_id': first['calibration_event']['event_id']})
        self.approval(); latest = self.approval('rejected')
        autopilot.record(self.root, {**result, 'decision_event_id': latest['calibration_event']['event_id']})
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'supersedes'):
            autopilot.record(self.root, {**result, 'decision_event_id': first['calibration_event']['event_id']})
        self.assertEqual(before, self.files())
        self.assertEqual(len(self.rows()), 3)

    def test_explicit_link_unknown_approval_is_checked_before_completed_replay(self):
        action = self.human(); result = self.receipt(action, human_decision='approved')
        autopilot.record(self.root, result)
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'same-run'):
            autopilot.record(self.root, {**result, 'decision_id': 'no-such-decision',
                                        'decision_event_id': 'no-such-occurrence'})
        self.assertEqual(before, self.files())

    def test_explicit_link_new_valid_source_is_not_replaced_by_older_same_opinion(self):
        action = self.human()
        result = self.receipt(action, human_decision='approved'); result['status'] = 'returned'
        autopilot.record(self.root, result)
        first = self.rows()[0]; self.approval(human_event_id=first['event_id'])
        autopilot.record(self.root, {**result, 'user_evidence': 'Actual later separate confirmation'})
        latest = self.rows()[-1]
        canonical = self.approval(human_event_id=latest['event_id'])
        self.assertEqual(canonical['calibration_event'], latest)
        self.assertEqual(len(self.rows()), 2)

    def test_legacy_completed_receipt_without_calibration_still_replays_without_new_vote(self):
        action = self.human(); result = self.receipt(action)
        # Reconstruct the persisted A/B receipt shape: no calibration event or occurrence association.
        with store.locked(self.root):
            data = store.load_run(self.root); task = data['tasks'][0]
            task.update(status='done', last_result_digest=state.digest(result), user_evidence=result['user_evidence'],
                        output_versions=store.versions(self.root, [self.artifact]))
            task['history'][-1]['outputs'] = task['output_versions']
            store.save_run(self.root, data, 'synthetic-legacy-completion')
        before = self.files()
        self.assertEqual(autopilot.record(self.root, result)['status'], 'done')
        self.assertEqual(before, self.files())
        self.assertEqual(self.rows(), [])

    def test_linked_completion_revision_restores_progress_after_returned_pointer(self):
        action = self.human(); approved = self.approval()
        completed = self.receipt(action, human_decision='approved', decision_id=approved['decision_id'])
        autopilot.record(self.root, {**completed, 'status': 'returned'})
        write = state.write_json
        def interrupt(path, value):
            if Path(path).name == 'run.json': raise OSError('Synthetic lost completed pointer')
            return write(path, value)
        with patch.object(state, 'write_json', side_effect=interrupt):
            with self.assertRaises(OSError): autopilot.record(self.root, completed)
        self.assertEqual(store.load_run(self.root)['tasks'][0]['status'], 'waiting_external')
        replay = autopilot.record(self.root, {**completed, 'stage': 'C5'})
        self.assertEqual(replay['status'], 'done')
        self.assertEqual(self.rows(), [approved['calibration_event']])

    def interrupted_log_append(self, operation, prefix):
        append = state.append_line
        def interrupt(path, value):
            if Path(path).name == 'calibration.jsonl':
                with Path(path).open('ab') as stream:
                    stream.write(prefix(json.dumps(value, ensure_ascii=False).encode('utf-8')))
                raise OSError('Synthetic process interruption during calibration append')
            return append(path, value)
        with patch.object(state, 'append_line', side_effect=interrupt):
            with self.assertRaises(OSError): operation()
        data = store.load_run(self.root)
        path = state.resolve(self.root, store.AREA + '/runs/' + data['run_id'] + '/calibration.jsonl')
        return path, path.read_bytes()

    def test_log_tail_partial_status_is_readonly_and_next_repairs_original_snapshot(self):
        action = self.human(); result = self.receipt(action, human_decision='approved')
        path, interrupted = self.interrupted_log_append(lambda: autopilot.record(self.root, result),
                                                       lambda raw: raw[:len(raw) // 2])
        saved = store.load_run(self.root)['calibration_events'][0]
        packet = self.packet()  # A later review cannot be used for recovery or metadata replay.
        before = self.files(); stats = autopilot.status(self.root)['calibration']
        self.assertEqual(before, self.files())
        self.assertFalse(stats['log_complete'])
        self.assertTrue(stats['incomplete_tail']['recoverable'])
        self.assertEqual(stats['missing_event_ids'], [saved['event_id']])
        self.assertEqual(stats['total'], 0)
        autopilot.next_task(self.root, 'host')
        self.assertTrue(path.read_bytes().startswith(interrupted))
        self.assertEqual(self.rows(), [saved])
        self.assertIsNone(saved['agreement'])
        autopilot.record(self.root, {**result, 'review_packet': packet})
        self.assertEqual(self.rows(), [saved])
        self.assertTrue(autopilot.status(self.root)['calibration']['log_complete'])

    def test_log_tail_complete_json_without_newline_recovers_via_receipt_replay(self):
        action = self.human(); result = self.receipt(action, human_decision='approved')
        path, interrupted = self.interrupted_log_append(lambda: autopilot.record(self.root, result), lambda raw: raw)
        saved = store.load_run(self.root)['calibration_events'][0]
        self.assertEqual(json.loads(interrupted), saved)
        before = self.files(); stats = autopilot.status(self.root)['calibration']
        self.assertEqual(before, self.files())
        self.assertFalse(stats['log_complete'])
        self.assertEqual(stats['missing_event_ids'], [saved['event_id']])
        self.assertEqual(autopilot.record(self.root, result)['status'], 'done')
        self.assertEqual(path.read_bytes(), interrupted + b'\n')
        self.assertEqual(self.rows(), [saved])

    def test_log_tail_utf8_byte_cut_recovers_without_replacing_original_bytes(self):
        action = self.human(); result = self.receipt(action, human_decision='approved')
        result['user_evidence'] = '真实人工答复：采用当前版本'
        path, interrupted = self.interrupted_log_append(lambda: autopilot.record(self.root, result),
            lambda raw: raw[:raw.index('真'.encode('utf-8')) + 1])
        with self.assertRaises(UnicodeDecodeError): interrupted.decode('utf-8')
        before = self.files(); stats = autopilot.status(self.root)['calibration']
        self.assertEqual(before, self.files())
        self.assertTrue(stats['incomplete_tail']['recoverable'])
        autopilot.record(self.root, result)
        self.assertTrue(path.read_bytes().startswith(interrupted))
        self.assertEqual(self.rows()[0]['human_evidence'], result['user_evidence'])
        self.assertEqual(self.rows()[0]['event_seq'], 1)
        self.assertTrue(autopilot.status(self.root)['calibration']['log_complete'])

    def test_log_tail_repair_preserves_all_complete_lines_and_partial_prefix(self):
        self.start(); first = self.approval()['calibration_event']
        other = self.file('second-tail-event')
        path, interrupted = self.interrupted_log_append(lambda: self.approval(artifacts=[other]),
                                                       lambda raw: raw[:len(raw) // 2])
        before = self.files(); stats = autopilot.status(self.root)['calibration']
        self.assertEqual(before, self.files())
        self.assertEqual(stats['total'], 1)
        self.assertEqual(len(stats['missing_event_ids']), 1)
        autopilot.control(self.root, paused=True, evidence='Actual recovery pause')
        self.assertTrue(path.read_bytes().startswith(interrupted))
        self.assertEqual(self.rows()[0], first)
        self.assertEqual([row['event_seq'] for row in self.rows()], [1, 2])

    def test_log_tail_unknown_bytes_are_reported_and_writer_preserves_them(self):
        action = self.human(); result = self.receipt(action, human_decision='approved')
        path, interrupted = self.interrupted_log_append(lambda: autopilot.record(self.root, result),
                                                       lambda raw: b'{"unknown_event":')
        before = self.files(); stats = autopilot.status(self.root)['calibration']
        self.assertEqual(before, self.files())
        self.assertFalse(stats['log_complete'])
        self.assertFalse(stats['incomplete_tail']['recoverable'])
        self.assertTrue(stats['log_issues'])
        with self.assertRaisesRegex(ValueError, 'calibration'):
            autopilot.next_task(self.root, 'host')
        self.assertEqual(before, self.files())
        self.assertEqual(path.read_bytes(), interrupted)

    def test_log_tail_middle_corruption_is_reported_not_silently_skipped(self):
        action = self.human(); result = self.receipt(action, human_decision='approved')
        path, interrupted = self.interrupted_log_append(lambda: autopilot.record(self.root, result),
            lambda raw: b'{synthetic-corruption}\n' + raw + b'\n')
        before = self.files(); stats = autopilot.status(self.root)['calibration']
        self.assertEqual(before, self.files())
        self.assertFalse(stats['log_complete'])
        self.assertTrue(stats['log_issues'])
        self.assertIsNone(stats['incomplete_tail'])
        with self.assertRaisesRegex(ValueError, 'calibration'):
            autopilot.record(self.root, result)
        self.assertEqual(before, self.files())
        self.assertEqual(path.read_bytes(), interrupted)


if __name__ == '__main__':
    unittest.main()
