"""Version-bound independent review packets. No production or approval writer."""
from pathlib import Path

from . import state, automation_store as store

RUBRICS = {
    'source': [('coverage', 'Original pages/materials are accounted for; omissions are explicit.'),
               ('accuracy', 'Facts, mathematical quantities and source attribution match the supplied originals.'),
               ('limitations', 'Unknown media/content is explicitly unverified; no invented inspection.')],
    'teaching': [('math', 'Recompute answers and verify mathematical conditions and reasoning.'),
                 ('alignment', 'Goals, activities and assessment follow the adopted source and age level.'),
                 ('continuity', 'Story, teacher transitions, timing and page/video mapping are consistent.')],
    'visual': [('math', 'Visible quantities, diagrams, symbols and text express the intended mathematics.'),
               ('readability', 'Actually view each supplied image; check clipping, legibility and layout.'),
               ('continuity', 'Characters, props, style and source references remain consistent.')],
    'video': [('math', 'Spoken/visible mathematical content and story causality agree with the sources.'),
              ('production', 'For preparation: assets, sound/script and generation instructions agree; for media: inspect real motion/audio.'),
              ('handoff', 'Coverage, versions and classroom entry/exit agree; missing actual playback stays unverified.')],
    'delivery': [('coverage', 'Every item required by the actual scope is present and is the current version.'),
                 ('consistency', 'PPT, real media, four documents and blackboard assets agree where required.'),
                 ('verification', 'Actual editability, pagination and required WPS/audio/playback evidence are available; static checks do not stand in for them.')],
}


def _prepare(project, request):
    rubric = request.get('rubric')
    if rubric not in RUBRICS or not isinstance(request.get('producer_id'), str) or not request['producer_id'].strip():
        raise ValueError('Known rubric and producer_id required')
    if not isinstance(request.get('instruction'), str) or not request['instruction'].strip():
        raise ValueError('Review instruction and actual scope required')
    artifacts, sources = request.get('artifacts'), request.get('sources')
    if not isinstance(artifacts, list) or not artifacts or not isinstance(sources, list) or not sources:
        raise ValueError('Nonempty artifact and source path lists required')
    expected = store.versions(project, artifacts + sources)
    problems = store.issues(project, expected)
    if problems: raise ValueError('; '.join(problems))
    review_id = store.identifier('review')
    folder = store.directory(project, store.AREA + '/reviews')
    folder = store.directory(project, str(folder.relative_to(Path(project))) + '/' + review_id)
    packet = {'schema_version': '1.0', 'review_id': review_id,
              'project': str(Path(project).resolve()), 'producer_id': request['producer_id'],
              'rubric': rubric, 'instruction': request['instruction'],
              'artifacts': [store.relative(project, p) for p in artifacts],
              'sources': [store.relative(project, p) for p in sources], 'versions': expected,
              'bindings': store.bindings(project, expected),
              'criteria': [{'id': key, 'requirement': description} for key, description in RUBRICS[rubric]],
              'created_at': state.now()}
    store.immutable(folder / 'packet.json', packet)
    return {'packet': (folder / 'packet.json').relative_to(Path(project)).as_posix(),
            'packet_sha256': state.sha256(folder / 'packet.json'), 'review_id': review_id}


def prepare(project, request):
    with store.locked(project): return _prepare(project, request)


def _packet(project, relative):
    path = state.resolve(project, relative)
    base = state.resolve(project, store.AREA + '/reviews')
    if not path.is_relative_to(base) or path.name != 'packet.json':
        raise ValueError('Expected a saved review packet in this project')
    data = state.read_json(path)
    if data.get('project') != str(Path(project).resolve()):
        raise ValueError('Review packet belongs to a different project')
    return path, data


def _validated_result(path, packet, report):
    if report.get('packet_sha256') != state.sha256(path) or report.get('source_versions') != packet['versions']:
        raise ValueError('Review must cover the exact packet and every current source/output version')
    reviewer = report.get('reviewer_id', '')
    if not isinstance(reviewer, str) or not reviewer.strip() or reviewer == packet['producer_id']:
        raise ValueError('A distinct actual independent reviewer identity is required')
    if report.get('method') != 'independent_agent':
        raise ValueError('Self-review or an unavailable independent agent cannot count as independent review')
    checks = report.get('checks', [])
    keys = {c['id'] for c in packet['criteria']}
    if (not isinstance(checks, list) or len(checks) != len(keys)
            or any(not isinstance(c, dict) for c in checks)
            or {c.get('id') for c in checks} != keys):
        raise ValueError('Report must cover each rubric criterion exactly once')
    for check in checks:
        if check.get('verdict') not in ('pass', 'changes_required', 'unverified'):
            raise ValueError('Use pass, changes_required or unverified per criterion')
        if not isinstance(check.get('note'), str) or not check['note'].strip():
            raise ValueError('Every criterion needs observations or a concrete unverified reason')
        refs = check.get('evidence', [])
        if not isinstance(refs, list) or any(p not in packet['versions'] for p in refs):
            raise ValueError('Evidence must name packet artifacts/sources')
        if check['verdict'] != 'unverified' and not refs:
            raise ValueError('Verified conclusions require actual cited evidence')
    verdicts = {c['verdict'] for c in checks}
    verdict = ('changes_required' if 'changes_required' in verdicts else
               'unverified' if 'unverified' in verdicts else 'pass')
    return {'review_id': packet['review_id'], 'verdict': verdict,
            'report': report, 'adoption_granted': False}


def record(project, packet_path, report):
    with store.locked(project):
        path, packet = _packet(project, packet_path)
        problems = store.issues(project, packet['versions']) + store.binding_issues(project, packet['bindings'])
        if problems: raise ValueError('; '.join(problems))
        result = _validated_result(path, packet, report)
        store.immutable(path.parent / 'result.json', result)
        return {**result, 'result': (path.parent / 'result.json').relative_to(Path(project)).as_posix()}


def status(project, packet_path):
    path, packet = _packet(project, packet_path)
    problems = store.issues(project, packet['versions']) + store.binding_issues(project, packet['bindings'])
    result_path = path.parent / 'result.json'
    result = state.read_json(result_path) if result_path.exists() else None
    if result:
        try:
            if _validated_result(path, packet, result.get('report', {})) != result:
                problems.append('Stored review conclusion does not match the validated report')
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            problems.append('Invalid stored review report: ' + str(exc))
    return {'review_id': packet['review_id'], 'pending': result is None,
            'valid': result is not None and not problems, 'issues': problems,
            'verdict': result['verdict'] if result else None,
            'report': result.get('report') if result else None, 'adoption_granted': False}


def snapshot(project, packet_path):
    """Freeze an explicitly selected valid report before a human decision is written.

    The caller holds the automation write lock. Existing immutable result formats
    remain unchanged; existence under that lock proves this report predates the decision.
    """
    path, packet = _packet(project, packet_path)
    result = status(project, packet_path)
    if not result['valid']:
        raise ValueError('Selected review is pending or invalid: ' + '; '.join(result['issues']))
    result_path = path.with_name('result.json')
    return {'review_id': packet['review_id'], 'reviewer_id': result['report']['reviewer_id'],
            'review_packet': state.relative_path(project, path), 'review_packet_hash': state.sha256(path),
            'review_result': state.relative_path(project, result_path),
            'review_result_hash': state.sha256(result_path), 'reviewer_verdict': result['verdict'],
            'captured_at': state.now(), 'packet_created_at': packet['created_at'],
            'artifacts': sorted([{'path': p, 'sha256': packet['versions'][p]} for p in packet['artifacts']],
                                key=lambda item: item['path']),
            'source_versions': packet['versions'], 'adoption_granted': False}
