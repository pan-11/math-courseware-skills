"""Frozen human/reviewer observations. Never grants adoption, budget or task scope.

Writers hold automation_store.locked. Readers and recovery use saved event snapshots,
never today's artifacts or a later review to reinterpret a historical decision.
"""
from copy import deepcopy
import json

from . import state, review, automation_store as store

STAGES = {'analysis': 'C1', 'blueprint': 'C2', 'cover': 'C3', 'asset': 'C3',
          'pages': 'C4', 'page-image': 'C5', 'image-export': 'C5',
          'editable-handoff': 'C6', 'editable-import': 'C6', 'editable-build': 'C6',
          'documents': 'C7', 'collect': 'C8', 'complete': 'C8'}


def outcome(decision):
    return 'approved' if decision == 'approved' else 'rejected' if decision in ('rejected', 'changes_required') else None


def validate_metadata(value):
    if any(key.startswith('calibration') or key in ('event_id', 'event_seq', 'reviewer_id',
            'reviewer_verdict', 'agreement', 'pair_status', 'review_result_hash') for key in value):
        raise ValueError('Calibration snapshots and reviewer conclusions are derived from saved evidence')
    for key in ('stage', 'human_node', 'human_reason', 'reason', 'human_decision', 'decision_event_id', 'human_event_id'):
        if key in value and value[key] is not None and (not isinstance(value[key], str) or not value[key].strip()):
            raise ValueError(key + ' must be actual nonempty text or null')
    if 'review_packet' in value and 'review_packets' in value:
        raise ValueError('Use review_packet or review_packets, not both')
    refs = value.get('review_packets', [value['review_packet']] if 'review_packet' in value else [])
    if (not isinstance(refs, list) or any(not isinstance(p, str) or not p.strip() for p in refs)
            or len(set(refs)) != len(refs)):
        raise ValueError('Review references must be unique saved packet paths')


def artifacts(project, versions):
    return sorted([{'path': state.relative_path(project, path), 'sha256': sha}
                   for path, sha in versions.items()], key=lambda item: item['path'])


def _folder(project, data):
    return state.resolve(project, store.AREA + '/runs/' + data['run_id'])


def _runs(project, data):
    yield data
    for path in sorted(_folder(project, data).glob('revision-*.json')):
        yield state.read_json(path)


def snapshots(project, data):
    """Read original durable decisions/revisions, including interrupted pointer writes."""
    found = {}
    candidates = [event for run in _runs(project, data) for event in run.get('calibration_events', [])]
    for entry in state.read_lines(state.resolve(project, '_state/decisions.jsonl')):
        if entry.get('calibration_event', {}).get('run_id') == data['run_id']:
            candidates.append(entry['calibration_event'])
    for event in candidates:
        if event['run_id'] != data['run_id']: raise ValueError('Calibration snapshot belongs to another run')
        previous = found.setdefault(event['event_id'], event)
        if previous != event: raise ValueError('Conflicting frozen calibration snapshots')
    return found


def freeze(project, data, kind, identity, versions, decision, evidence, metadata,
           task=None, decision_id=None, recorded_at=None):
    """Capture only explicit displayed reports while the caller still holds the write lock."""
    validate_metadata(metadata)
    saved = snapshots(project, data)
    sequence = max((event.get('event_seq', 0) for event in saved.values()), default=0) + 1
    if identity is None: identity = ['occurrence', sequence]
    event_id = 'calibration-' + state.digest([data['run_id'], kind, identity])
    prior = saved.get(event_id)
    if prior: return deepcopy(prior)  # Interrupted original save: do not inspect a newer report.
    spec = task['spec'] if task else {}
    stage = metadata.get('stage') or spec.get('stage') or (
        'C3' if spec.get('step', '').startswith('video-') else STAGES.get(spec.get('step'), 'unspecified'))
    targets = artifacts(project, versions)
    refs = metadata.get('review_packets', [metadata['review_packet']] if 'review_packet' in metadata else [])
    event = dict(run_id=data['run_id'], event_id=event_id, event_seq=sequence, decision_id=decision_id,
                 recorded_at=recorded_at or state.now(), source=kind,
                 stage=stage, human_node=metadata.get('human_node') or spec.get('human_node'),
                 task_id=spec.get('id') or metadata.get('task_id'),
                 video_id=spec.get('video_id') or metadata.get('video_id'),
                 artifacts=targets, version_hash=state.digest(targets),
                 review_references=list(refs), reviews=[], reviewer_id=None,
                 review_packet=None, review_result_hash=None, reviewer_verdict=None,
                 human_decision=decision, human_outcome=outcome(decision), human_evidence=evidence,
                 human_reason=metadata.get('human_reason', metadata.get('reason')),
                 agreement=None, pair_status='unpaired', unpaired_reason=None)
    problems = []
    for relative in refs:
        try:
            event['reviews'].append(review.snapshot(project, relative))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            problems.append(str(exc))
    reports = event['reviews']
    if reports:
        for key in ('reviewer_id', 'review_packet', 'review_result_hash'):
            event[key] = reports[0][key] if len(reports) == 1 else [r[key] for r in reports]
        verdicts = {r['reviewer_verdict'] for r in reports}
        event['reviewer_verdict'] = ('unverified' if 'unverified' in verdicts else
                                     'changes_required' if 'changes_required' in verdicts else 'pass')
    covered = {item['path']: item['sha256'] for r in reports for item in r['artifacts']}
    if outcome(decision) is None:
        reason = 'nonbinary_human_decision'
    elif not refs:
        reason = 'no_review_reference'
    elif problems:
        reason = 'invalid_review'
    elif covered != {item['path']: item['sha256'] for item in targets}:
        reason = 'artifact_coverage_mismatch'
    elif event['reviewer_verdict'] == 'unverified':
        reason = 'unverified_review'
    else:
        reason = None
        event['agreement'] = (event['reviewer_verdict'] == 'pass') == (outcome(decision) == 'approved')
        event['pair_status'] = 'paired'
    event['unpaired_reason'] = reason
    event['recorded_at'] = recorded_at or state.now()
    if problems: event['review_issues'] = problems
    return event


def remember(data, event):
    events = data.setdefault('calibration_events', [])
    if not any(item['event_id'] == event['event_id'] for item in events): events.append(event)


def _ordered(saved):
    return sorted(saved.values(), key=lambda row: (row.get('event_seq', 0), row['event_id']))


def _read_log(path, saved):
    """Read bytes so a short UTF-8/JSON append cannot hide complete historical rows."""
    chunks = (path.read_bytes() if path.exists() else b'').split(b'\n')
    written, issues = {}, []
    for number, raw in enumerate(chunks[:-1], 1):
        try:
            row = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            issues.append('Invalid calibration JSON at line ' + str(number))
            continue
        event_id = row.get('event_id') if isinstance(row, dict) else None
        if not isinstance(event_id, str) or saved.get(event_id) != row:
            issues.append('Unknown or conflicting calibration event at line ' + str(number))
        elif event_id in written:
            issues.append('Duplicate calibration event at line ' + str(number))
        else:
            written[event_id] = row
    tail, suffix = None, None
    if chunks[-1]:
        raw = chunks[-1]
        pending = [event for event in _ordered(saved) if event['event_id'] not in written]
        # Recovery always appends in durable event order. Never choose a later matching report/event.
        if pending:
            expected = json.dumps(pending[0], ensure_ascii=False).encode('utf-8')
            if expected.startswith(raw): suffix = expected[len(raw):] + b'\n'
            elif raw == expected + b'\r': suffix = b'\n'
        tail = dict(line=len(chunks), byte_count=len(raw), recoverable=suffix is not None,
                    event_id=pending[0]['event_id'] if suffix is not None else None)
        if suffix is None: issues.append('Unrecognized calibration tail at line ' + str(len(chunks)))
    return written, issues, tail, suffix


def recover(project, data):
    """Append missing durable snapshots only. Caller holds the shared write lock."""
    path = _folder(project, data) / 'calibration.jsonl'
    saved = snapshots(project, data)
    written, issues, tail, suffix = _read_log(path, saved)
    if issues: raise ValueError('; '.join(issues))
    if tail:
        with path.open('ab') as stream:
            if stream.write(suffix) != len(suffix): raise OSError('Incomplete calibration tail repair')
        written[tail['event_id']] = saved[tail['event_id']]
    for event in _ordered(saved):
        if event['event_id'] in written: continue
        state.append_line(path, event)
        written[event['event_id']] = event


def settings(project, data, choices):
    """Only explicit evidenced choices count; image_declarations/default limits never do."""
    for group in ('image', 'video', 'editable', 'limits'):
        if group not in choices: continue
        choice = choices[group]
        signature = state.digest(choice)
        last = data.get('calibration_choices', {}).get(group, {})
        if last.get('signature') == signature: continue
        evidence = choice.get('evidence') or choice.get('authorization', {}).get('scope_evidence')
        snapshot = {group: deepcopy(data['limits'] if group == 'limits' else data['preferences'][group])}
        metadata = {'stage': 'C0', 'human_node': {'image': 'H05', 'video': 'H10', 'editable': 'H16',
                                               'limits': 'image-budget'}[group],
                    'human_reason': choices.get('human_reason')}
        event = freeze(project, data, 'settings', [group, signature, last.get('event_id')], {},
                       'choice', evidence, metadata)
        if 'settings_snapshot' not in event:
            event.update(settings_snapshot=snapshot, settings_hash=state.digest(snapshot),
                         version_hash=state.digest(snapshot))
        remember(data, event)
        data.setdefault('calibration_choices', {})[group] = {'signature': signature, 'event_id': event['event_id']}


def receipt_identity(project, result, versions):
    return state.digest([result['claim'], result['status'], artifacts(project, versions),
                         outcome(result.get('human_decision')) or result.get('human_decision', 'operation_completed'),
                         result.get('user_evidence')])


def receipt_replay(project, data, task, result):
    """Find the original receipt even if its immutable revision outlived a pointer write."""
    if task['spec'].get('kind') != 'human' or result.get('status') not in ('completed', 'returned'):
        return None, None
    files = result.get('artifacts')
    if not isinstance(files, dict) or set(files) != set(task['spec']['outputs']): return None, None
    versions = store.versions(project, list(files.values()))
    signature = receipt_identity(project, result, versions)
    saved = snapshots(project, data)
    for run in _runs(project, data):
        for previous in run['tasks']:
            receipt = previous.get('last_human_receipt', {})
            if (previous['spec']['id'] == task['spec']['id'] and previous.get('claim') == task['claim']
                    and receipt.get('signature') == signature):
                event = saved[receipt['event_id']]
                if not _changed_since(project, data, event):
                    linked, _ = _receipt_link(project, data, result, versions)
                    if not linked or linked['event_id'] == event['event_id']:
                        return deepcopy(event), signature
    return None, None


def _receipt_link(project, data, result, versions):
    """Source links are validated before replay; unlike report labels they are not annotations."""
    decision_id = result.get('decision_id')
    if result.get('decision_event_id') and not decision_id:
        raise ValueError('decision_event_id needs an actual same-run decision_id')
    if decision_id:
        matches = [entry['calibration_event'] for entry in state.read_lines(
            state.resolve(project, '_state/decisions.jsonl'))
            if entry.get('decision_id') == decision_id and
            entry.get('calibration_event', {}).get('run_id') == data['run_id']]
        if result.get('decision_event_id'):
            matches = [e for e in matches if e['event_id'] == result['decision_event_id']]
        if not matches: raise ValueError('No actual same-run approval occurrence for decision_id')
        targets = artifacts(project, versions)
        if any(e['artifacts'] != targets for e in matches):
            raise ValueError('Approval and human receipt must name the same exact artifact versions')
        if len(matches) == 1:
            event = matches[0]
            if outcome(result.get('human_decision', event['human_decision'])) != outcome(event['human_decision']):
                raise ValueError('Human receipt conflicts with the linked actual decision')
            _require_current_occurrence(project, data, event)
            return deepcopy(event), False
        return None, True
    return None, False


def receipt(project, data, task, result, versions):
    """Link a real approval occurrence when unambiguous; never guess between reused IDs."""
    validate_metadata(result)
    linked, ambiguous = _receipt_link(project, data, result, versions)
    if linked: return linked
    event = freeze(project, data, 'human-receipt', None, versions,
                   result.get('human_decision', 'operation_completed'), result['user_evidence'],
                   result, task, result.get('decision_id'))
    if ambiguous:
        event.update(agreement=None, pair_status='unpaired', unpaired_reason='ambiguous_decision_occurrence')
    return event


def approval_link(project, data, record, versions, decision):
    """An explicit reverse link keeps the first receipt snapshot, including unpaired status."""
    event = snapshots(project, data).get(record['human_event_id'])
    if (not event or event['source'] != 'human-receipt' or outcome(event['human_decision']) != decision
            or event['artifacts'] != artifacts(project, versions)):
        raise ValueError('human_event_id must identify the same actual human decision and artifact versions')
    _require_current_occurrence(project, data, event)
    return deepcopy(event)


def _require_current_occurrence(project, data, event):
    if _changed_since(project, data, event):
        raise ValueError('A later human decision supersedes this occurrence; record the actual new decision')


def _changed_since(project, data, event):
    targets = {(item['path'], item['sha256']) for item in event['artifacts']}
    for later in snapshots(project, data).values():
        later_outcome = outcome(later['human_decision'])
        # Unsequenced historical snapshots cannot prove a link is current after a conflicting decision.
        if (later['event_id'] != event.get('event_id')
                and ('event_seq' not in event or 'event_seq' not in later or later['event_seq'] > event['event_seq'])
                and ((later_outcome is not None and later_outcome != outcome(event['human_decision']))
                     or str(later['human_decision']).startswith('partial'))
                and targets & {(item['path'], item['sha256']) for item in later['artifacts']}):
            return True
    return False


def approval_replay(project, data, entry, history):
    """Unrelated decisions do not make a replay new; actual intervening changes do."""
    targets = {(item['path'], item['sha256']) for item in entry['targets']}
    for index in range(len(history) - 1, -1, -1):
        previous = history[index]
        if (previous['decision'] != entry['decision'] or previous['user_evidence'] != entry['user_evidence']
                or {(item['path'], item['sha256']) for item in previous['targets']} != targets): continue
        for later in history[index + 1:]:
            if later['decision'] != entry['decision'] and targets & {
                    (item['path'], item['sha256']) for item in later['targets']}:
                return None
        original = previous.get('calibration_event', {
            'artifacts': previous['targets'], 'recorded_at': previous['recorded_at'],
            'human_decision': previous['decision']})
        return None if _changed_since(project, data, original) else previous
    return None


def _counts(rows):
    agreed = sum(row['agreement'] is True for row in rows)
    disagreed = sum(row['agreement'] is False for row in rows)
    comparable = agreed + disagreed
    return dict(total=len(rows), comparable=comparable, agreed=agreed, disagreed=disagreed,
                unpaired=len(rows) - comparable, agreement_rate=agreed / comparable if comparable else None,
                sample_status='comparable_samples' if comparable else 'no_comparable_samples',
                pass_human_rejected=sum(r['agreement'] is False and r['reviewer_verdict'] == 'pass' for r in rows),
                changes_required_human_approved=sum(r['agreement'] is False and
                    r['reviewer_verdict'] == 'changes_required' for r in rows))


def summary(project, data):
    """Read-only statistics from historical rows; changed sources cannot rewrite history."""
    saved = snapshots(project, data)
    written, issues, tail, _ = _read_log(_folder(project, data) / 'calibration.jsonl', saved)
    rows = list(written.values())
    missing = sorted(set(saved) - set(written))
    return {**_counts(rows), 'by_stage': {stage: _counts([r for r in rows if r['stage'] == stage])
            for stage in sorted({r['stage'] for r in rows})},
            'missing_event_ids': missing, 'log_complete': not (issues or tail or missing),
            'log_issues': issues, 'incomplete_tail': tail}
