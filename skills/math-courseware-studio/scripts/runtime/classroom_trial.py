"""Explicitly activated PPT-only classroom trial; legacy selection stays unchanged."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import uuid

from . import classroom_animation, click_answers, editable_delivery, state

PROFILE = 'classroom-trial-v1'
ACTIVATION = '课堂动画试用V1'
ARTIFACT = 'editable-classroom-trial-v1'


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _activate(activation, plan=None):
    _need(activation == ACTIVATION, 'Explicit activation must be exactly ' + ACTIVATION)
    if plan is not None:
        instruction = plan.get('request', {}).get('user_instruction')
        _need(isinstance(instruction, str) and (ACTIVATION in instruction or
              isinstance(plan.get('request', {}).get('activation_ref'), dict)),
              'The locked request must contain ' + ACTIVATION)


def _continuation(project, plan, input_sha256=None):
    reference = plan.get('request', {}).get('activation_ref')
    if reference is None:
        return
    bound = _ref(project, reference)
    _need(plan['source_versions'].get(bound['path']) == bound['sha256'],
          'Activation continuation must be a locked source')
    record = state.read_json(state.resolve(project, bound['path']))
    _need(record.get('activation') == ACTIVATION and record.get('scope') == 'current_task'
          and record.get('status') == 'active'
          and record.get('user_instruction') == plan['request']['user_instruction']
          and record.get('input_sha256') == (input_sha256 or plan['source_sha256'])
          and record.get('project_root') == str(Path(project).resolve()),
          'Activation continuation does not match this task, instruction and input')


def _ref(project, reference):
    if isinstance(reference, str):
        path = state.resolve(project, reference)
        _need(path.is_file(), 'Bound file missing: ' + reference)
        return {'path': state.relative_path(project, path), 'sha256': state.sha256(path)}
    _need(isinstance(reference, dict) and set(reference) == {'path', 'sha256'}, 'Bound path and sha256 required')
    path = editable_delivery._file(project, reference)
    return {'path': state.relative_path(project, path), 'sha256': reference['sha256']}


def _base(project, source=None):
    record = state.load_project(project)
    base = record.get('artifacts', {}).get('editable-base-pptx')
    imported = record.get('artifacts', {}).get('editable-classroom-trial-input')
    if imported and source is not None and imported.get('path') == source.get('path'):
        from . import classroom_refill_input
        receipt = classroom_refill_input.current(project)
        return _ref(project, {'path': receipt['path'], 'sha256': receipt['sha256']})
    _need(base is not None and 'editable-base-pptx' not in record.get('stale_targets', []),
          'A current editable-base-pptx is required')
    editable_delivery._file(project, base)
    editable_delivery._versions(project, base.get('source_versions'))
    return _ref(project, {'path': base['path'], 'sha256': base['sha256']})


def _same(project, left, right):
    return _ref(project, left) == _ref(project, right)


def _scope(project, plan):
    editor = classroom_animation.editor
    count = len(editor._slides(editor._parts(state.resolve(project, plan['source_deck']))))
    _need(set(plan.get('mapping', {}).values()) == set(range(1, count + 1)),
          'The component scan must cover every actual base slide, including zero-answer pages')
    pages_path = state.resolve(project, '_state/pages.json')
    if pages_path.is_file():
        pages = state.read_json(pages_path).get('pages', [])
        if pages:
            _need(set(plan['mapping']) == {p['page_id'] for p in pages},
                  'Component mapping must cover the current registered page scope')
        else:
            from . import classroom_refill_input
            supplied = classroom_refill_input.current(project)
            _need(supplied['path'] == plan['source_deck'] and supplied['mapping'] == plan['mapping'],
                  'An unplanned project must use the complete provided-refill scope')
        return _ref(project, state.relative_path(project, pages_path))
    return None


def components(project, plan, activation):
    """Build an intermediate component deck with the mode in its immutable plan."""
    _activate(activation, plan)
    _continuation(project, plan)
    plan = deepcopy(plan)
    _need(plan.get('mode', 'components_only') == 'components_only', 'Trial requires components_only mode')
    plan['mode'] = 'components_only'
    source = {'path': plan['source_deck'], 'sha256': plan['source_sha256']}
    _need(_same(project, source, _base(project, source)),
          'Component source must be the current editable base')
    classroom_animation._instruction(project, plan)
    _scope(project, plan)
    result = click_answers.build(project, plan)
    return {**result, 'profile': PROFILE, 'intermediate': True}


def _coverage(plan, component_report, objects_by_slide):
    _need(plan.get('mapping') == component_report['mapping'], 'Component page/slide mapping differs')
    pages = {p['page_id']: p for p in plan['pages']}
    _need(len(pages) == len(plan['pages']) and set(pages) == set(component_report['mapping']),
          'Every scanned component page must be covered exactly once')
    coverage, issues = [], []
    for source in component_report['pages']:
        page = pages[source['page_id']]
        _need(plan['mapping'][source['page_id']] == source['slide_index'], 'Component slide differs')
        used = set()
        for answer in source['answers']:
            label = source['page_id'] + '/' + answer['blank_id']
            ids = {c['shape_id'] for c in answer['components']}
            owners = [u for u in page['units'] if any(t['shape_id'] in ids for t in u['targets'])]
            _need(len(owners) == 1, label + ': every answer must occupy one complete unit')
            unit = owners[0]
            _need(unit['unit_id'] not in used and len(unit['targets']) == len(ids)
                  and {t['shape_id'] for t in unit['targets']} == ids
                  and all('paragraph' not in t for t in unit['targets']),
                  label + ': whole-shape answer coverage cannot be split, mixed or partial')
            used.add(unit['unit_id'])
            _need(unit['role'] == 'answer' and unit['purpose'] == 'answer' and unit['initial_visible'] is False,
                  label + ': new answers must be answer units initially hidden')
            if any(c['kind'] == 'bar' for c in answer['components']):
                _need(unit['kind'] == 'fraction' and bool(unit.get('logical_id')),
                      label + ': ordinary fraction requires one fraction unit with logical_id')
            entrances = [a for s in page['steps'] for a in s['actions']
                         if a['unit_id'] == unit['unit_id'] and a['effect'] in classroom_animation.ENTRANCES]
            _need(bool(entrances), label + ': hidden answer requires an actual entrance action')
            coverage.append({'page_id': source['page_id'], 'slide_index': source['slide_index'],
                             'blank_id': answer['blank_id'], 'unit_id': unit['unit_id'], 'shape_ids': sorted(ids)})
        for item in source['retained_blanks']:
            if item['disposition'] == 'ambiguous':
                issues.append({'page_id': source['page_id'], 'slide_index': source['slide_index'], **item})
            elif item['disposition'] == 'already_visible' and 'teaching_contract' not in plan:
                for unit in page['units']:
                    if any(classroom_animation._overlap(target, original, objects_by_slide[source['slide_index']])
                           for target in unit['targets'] for original in item['existing_shapes']):
                        _need(unit['initial_visible'] is True,
                              source['page_id'] + '/' + item['blank_id'] + ': originally visible answers must stay initially visible')
    return coverage, issues


def _context(project, plan, manifest_ref, require_contract=False):
    _activate(ACTIVATION, plan)
    if require_contract:
        for page in plan.get('pages', []):
            for step in page.get('steps', []):
                _need(all(action.get('trigger') != 'after_previous' or 'phase_start_ms' in action
                          for action in step.get('actions', [])),
                      'New V1 automatic follow-up actions require explicit native phase_start_ms')
    comp_ref = _ref(project, manifest_ref)
    component_report = click_answers.validate_components(project, comp_ref)
    _continuation(project, plan, component_report['source_sha256'])
    component_plan = state.read_json(editable_delivery._file(project, component_report['plan']))
    _activate(ACTIVATION, component_plan)
    _continuation(project, component_plan)
    classroom_animation._instruction(project, component_plan)
    _scope(project, component_plan)
    base = _base(project, {'path': component_report['source_deck'], 'sha256': component_report['source_sha256']})
    _need(_same(project, {'path': component_report['source_deck'], 'sha256': component_report['source_sha256']}, base),
          'Components do not use the current editable base')
    _need(_same(project, {'path': plan['source_deck'], 'sha256': plan['source_sha256']},
                {'path': component_report['output'], 'sha256': component_report['output_sha256']}),
          'Classroom source must be the exact component output')
    inventory = classroom_animation.inspect(state.resolve(project, component_report['output']))
    objects = {p['slide_index']: {obj['shape_id']: obj for obj in p['objects']} for p in inventory['slides']}
    from . import classroom_teaching_contract
    for slide in inventory['slides']:
        current_objects = objects[slide['slide_index']]
        animated_atoms = set()
        for target in slide['existing_targets']:
            if 'paragraph_start' in target:
                animated_atoms.update((target['shape_id'], i) for i in
                                      range(target['paragraph_start'], target['paragraph_end'] + 1))
            else:
                animated_atoms.update(classroom_teaching_contract._atoms(target, current_objects))
        for sid, obj in current_objects.items():
            atoms = classroom_teaching_contract._atoms({'shape_id': sid}, current_objects)
            obj['existing_animated'] = bool(atoms) and atoms <= animated_atoms
    coverage, issues = _coverage(plan, component_report, objects)
    teaching = None
    if require_contract or 'teaching_contract' in plan:
        teaching = classroom_teaching_contract.validate(project, plan, objects)
    return component_report, comp_ref, base, coverage, issues, teaching


def check(project, plan, components_manifest_ref, activation):
    _activate(activation, plan)
    _, _, _, coverage, issues, teaching = _context(project, plan, components_manifest_ref, require_contract=True)
    result = classroom_animation.check(project, plan)
    return {**result, 'profile': PROFILE, 'answer_coverage': coverage, 'teaching_coverage': teaching, 'known_issues': issues,
            'answer_completeness': not issues, 'course_complete': False}


def _manifest(project, plan, component_report, comp_ref, base, coverage, issues, teaching, animation):
    animation_ref = _ref(project, {'path': animation['manifest'], 'sha256': animation['manifest_sha256']})
    versions = {}
    references = [base, comp_ref, animation_ref, component_report['plan'], animation['plan'],
                  {'path': component_report['output'], 'sha256': component_report['output_sha256']}]
    pages_path = state.resolve(project, '_state/pages.json')
    if pages_path.is_file():
        references.append(_ref(project, state.relative_path(project, pages_path)))
    for report in (component_report, animation):
        references += [{'path': p, 'sha256': h} for p, h in report['source_versions'].items()]
    for ref in references:
        actual = _ref(project, ref)
        _need(actual['path'] not in versions or versions[actual['path']] == actual['sha256'],
              'Core source versions conflict')
        versions[actual['path']] = actual['sha256']
    return {'schema_version': PROFILE, 'profile': PROFILE, 'base_ref': base,
            'components_manifest': comp_ref, 'animation_manifest': animation_ref,
            'plan': animation['plan'], 'output': state.relative_path(project, animation['output']),
            'output_sha256': animation['output_sha256'], 'source_versions': versions,
            'answer_coverage': coverage, 'known_issues': issues, 'answer_completeness': not issues,
            'scope': 'ppt-only', 'course_complete': False, 'playback': 'unverified',
            **({'teaching_coverage': teaching} if teaching is not None else {})}


def _write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def _report(project, path, data):
    return {**data, 'manifest': state.relative_path(project, path), 'manifest_sha256': state.sha256(path)}


def build(project, plan, components_manifest_ref, activation):
    _activate(activation, plan)
    component_report, comp_ref, base, coverage, issues, teaching = _context(
        project, plan, components_manifest_ref, require_contract=True)
    animation = classroom_animation.build(project, plan)
    data = _manifest(project, plan, component_report, comp_ref, base, coverage, issues, teaching, animation)
    path = state.resolve(project, animation['output']).with_suffix('.trial-v1.json')
    if path.exists():
        return _validate(project, state.relative_path(project, path))
    _write(path, data)
    return _report(project, path, data)


def _validate(project, reference):
    ref = _ref(project, reference)
    path = state.resolve(project, ref['path'])
    data = state.read_json(path)
    _need(data.get('schema_version') == PROFILE and data.get('profile') == PROFILE, 'Unknown trial manifest/profile')
    editable_delivery._versions(project, data.get('source_versions'))
    animation = classroom_animation.validate_final(project, data['animation_manifest'])
    plan = state.read_json(editable_delivery._file(project, animation['plan']))
    context = _context(project, plan, data['components_manifest'])
    expected = _manifest(project, plan, *context, animation)
    _need(data == expected, 'Trial manifest differs from verified source/plan/output/coverage')
    _need(path == state.resolve(project, animation['output']).with_suffix('.trial-v1.json'),
          'Trial manifest must remain beside its output')
    _ref(project, ref)
    return _report(project, path, data)


def _check_refs(project, checks):
    _need(isinstance(checks, dict) and not set(checks) - {'review', 'static', 'playback'},
          'Optional checks use review/static/playback bound references')


def _optional(project, checks, output, frozen=None):
    """Re-evaluate supplied records without promoting them into mandatory sources."""
    from . import review
    results, bindings = {}, {}
    for kind in ('review', 'static', 'playback'):
        reference = checks.get(kind)
        if kind not in checks:
            results[kind] = {'status': 'unverified', 'reason': 'No record supplied'}
            continue
        status = {'status': 'invalid', 'origin': 'supplied_record', 'reference': reference}
        results[kind] = status
        try:
            _need(isinstance(reference, dict) and set(reference) == {'path', 'sha256'}
                  and all(isinstance(v, str) and v for v in reference.values()), 'Optional check needs path and sha256')
            state.resolve(project, reference['path'])
            try:
                ref = _ref(project, reference)
                for bound in (frozen or {}).get(kind, []):
                    _ref(project, bound)
            except ValueError as exc:
                status.update(status='stale', reason=str(exc))
                continue
            path = state.resolve(project, ref['path'])
            data = state.read_json(path)
            if kind == 'review':
                targets = {state.resolve(project, p) for p in data.get('artifacts', [])}
                _need(state.resolve(project, output['path']) in targets, 'Review output must be an artifact target, not only a source')
                versions = {state.resolve(project, p): h for p, h in data.get('versions', {}).items()}
                _need(versions.get(state.resolve(project, output['path'])) == output['sha256'], 'Review target version differs')
                result = review.status(project, ref['path'])
                result_path = path.parent / 'result.json'
                bindings[kind] = [_ref(project, state.relative_path(project, result_path))] if result_path.is_file() else []
                status.update(status=result['verdict'] if result['valid'] else
                              ('stale' if result['issues'] else 'unverified'),
                              valid=result['valid'], issues=result['issues'])
            else:
                _need(data.get('schema_version') == 'classroom_trial_check_v1' and data.get('kind') == kind,
                      'Unknown optional check receipt')
                _need(_same(project, data.get('target'), output), 'Optional check target differs')
                _need(data.get('verdict') in ('pass', 'changes_required', 'unverified')
                      and data.get('method') == ('native_slideshow' if kind == 'playback' else 'native_static_review')
                      and isinstance(data.get('note'), str) and bool(data['note'].strip()), 'Invalid optional check verdict/method/note')
                evidence = data.get('evidence')
                _need(isinstance(evidence, list) and (data['verdict'] == 'unverified' or bool(evidence)),
                      'Verified optional checks require evidence')
                try:
                    bindings[kind] = [_ref(project, item) for item in evidence]
                except ValueError as exc:
                    status.update(status='stale', reason=str(exc))
                    continue
                status.update(status=data['verdict'], note=data['note'], method=data['method'])
        except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
            status['reason'] = str(exc)
    return results, bindings


def register(project, manifest_ref, activation, checks=None):
    _activate(activation)
    result = _validate(project, manifest_ref)
    checks = deepcopy(checks if checks is not None else {})
    _check_refs(project, checks)
    output = {'path': result['output'], 'sha256': result['output_sha256']}
    statuses, bindings = _optional(project, checks, output)
    receipt = {'schema_version': PROFILE, 'trial_manifest': {'path': result['manifest'], 'sha256': result['manifest_sha256']},
               'output': output, 'checks': checks, 'check_bindings': bindings, 'created_at': state.now(),
               'previous_registration': state.load_project(project).get('artifacts', {}).get(ARTIFACT)}
    path = state.resolve(project, result['output']).with_suffix('.trial-registration-' + uuid.uuid4().hex + '.json')
    _write(path, receipt)
    versions = {**result['source_versions'], result['manifest']: result['manifest_sha256'],
                state.relative_path(project, path): state.sha256(path)}
    artifact = state.register_artifact(project, ARTIFACT, result['output'], list(versions), {
        'profile': PROFILE, 'refill_stage': PROFILE, 'trial_manifest': receipt['trial_manifest'],
        'registration_ref': _ref(project, state.relative_path(project, path)), 'source_versions': versions})
    return {**artifact, 'scope': 'ppt-only', 'course_complete': False, 'checks': statuses,
            'known_issues': result['known_issues'], 'answer_completeness': result['answer_completeness'],
            'teaching_coverage': result.get('teaching_coverage')}


def current(project, activation):
    _activate(activation)
    record = state.load_project(project)
    artifact = record.get('artifacts', {}).get(ARTIFACT)
    _need(artifact is not None and artifact.get('profile') == PROFILE and artifact.get('refill_stage') == PROFILE,
          'No registered classroom-trial-v1 current PPT')
    _need(ARTIFACT not in record.get('stale_targets', []), 'Current trial artifact is stale')
    editable_delivery._file(project, artifact)
    editable_delivery._versions(project, artifact.get('source_versions'))
    receipt = state.read_json(editable_delivery._file(project, artifact.get('registration_ref')))
    result = _validate(project, artifact.get('trial_manifest'))
    output = {'path': result['output'], 'sha256': result['output_sha256']}
    _need(receipt.get('schema_version') == PROFILE and receipt.get('trial_manifest') == artifact['trial_manifest']
          and _same(project, receipt['output'], output)
          and _same(project, {'path': artifact['path'], 'sha256': artifact['sha256']}, output),
          'Registered trial identity differs from verified output')
    expected = {**result['source_versions'], result['manifest']: result['manifest_sha256'],
                artifact['registration_ref']['path']: artifact['registration_ref']['sha256']}
    _need(artifact['source_versions'] == expected, 'Registered trial core source_versions differ')
    _check_refs(project, receipt['checks'])
    statuses, _ = _optional(project, receipt['checks'], output, receipt['check_bindings'])
    return {**artifact, 'scope': 'ppt-only', 'course_complete': False, 'checks': statuses,
            'known_issues': result['known_issues'], 'answer_completeness': result['answer_completeness'],
            'answer_coverage': result['answer_coverage'], 'teaching_coverage': result.get('teaching_coverage')}


def collect(project, activation):
    """Retain a versioned PPT plus an honest manifest; never claim full-course delivery."""
    selected = current(project, activation)
    root = state.resolve(project, '03_final/classroom-trial-v1')
    classroom_animation._parent(root)
    number = 1
    while (root / ('trial-v%03d' % number)).exists():
        number += 1
    folder = root / ('trial-v%03d' % number)
    folder.mkdir()
    target = folder / 'classroom-trial-v1.pptx'
    shutil.copyfile(state.resolve(project, selected['path']), target)
    _need(state.sha256(target) == selected['sha256'], 'Collected PPT changed during copy')
    after = current(project, activation)
    _need(after['registration_ref'] == selected['registration_ref'] and after['sha256'] == selected['sha256'],
          'Current trial changed during collection; retained incomplete folder')
    manifest = {'schema_version': PROFILE, 'profile': PROFILE, 'scope': 'ppt-only', 'course_complete': False,
                'created_at': state.now(), 'source': {'path': selected['path'], 'sha256': selected['sha256']},
                'trial_manifest': selected['trial_manifest'], 'registration_ref': selected['registration_ref'],
                'source_versions': selected['source_versions'], 'checks': after['checks'],
                'known_issues': after['known_issues'], 'answer_completeness': after['answer_completeness'],
                'teaching_coverage': after['teaching_coverage'],
                'files': [{'path': state.relative_path(project, target), 'sha256': state.sha256(target)}]}
    path = folder / 'manifest.json'
    _write(path, manifest)
    return {**_report(project, path, manifest), 'directory': state.relative_path(project, folder)}
