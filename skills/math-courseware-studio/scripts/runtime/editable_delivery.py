"""Select the actual current answer deck; preserve historical registrations."""
from . import state


def _file(project, reference):
    if not isinstance(reference, dict) or not reference.get('path') or not reference.get('sha256'):
        raise ValueError('Actual bound file reference required')
    path = state.resolve(project, reference['path'])
    if not path.is_file() or state.sha256(path) != reference['sha256']:
        raise ValueError('Current editable file changed or missing: ' + reference['path'])
    return path


def _versions(project, versions):
    if not isinstance(versions, dict) or not versions:
        raise ValueError('Editable source_versions required')
    for path, sha in versions.items():
        _file(project, {'path':path, 'sha256':sha})


def _override(project, value):
    if (not isinstance(value, dict) or value.get('variant') not in
            ('faithful_restore_only', 'student_without_answers')
            or not isinstance(value.get('user_instruction'), str) or not value['user_instruction'].strip()):
        raise ValueError('Explicit current user instruction required for a no-answer variant')
    _file(project, value.get('evidence_ref'))


def register_override(project, base, override):
    _file(project, base)
    _versions(project, base.get('source_versions'))
    _override(project, override)
    versions = {**base['source_versions'], base['path']:base['sha256'],
                override['evidence_ref']['path']:override['evidence_ref']['sha256']}
    return state.register_artifact(project, 'editable-pptx', base['path'], list(versions), {
        'source_versions':versions, 'refill_stage':'explicit_no_answers',
        'base_ref':{'path':base['path'], 'sha256':base['sha256']}, 'delivery_override':override,
        'review_status':'structure_checked_playback_pending'})


def current(project, reference=None):
    record = state.load_project(project)
    artifacts = record.get('artifacts', {})
    base, final = artifacts.get('editable-base-pptx'), artifacts.get('editable-pptx')
    if not base:
        # Existing courses are not retroactively migrated or reclassified.
        return final
    if 'editable-base-pptx' in record.get('stale_targets', []):
        raise ValueError('Current editable base is stale')
    _file(project, base)
    _versions(project, base.get('source_versions'))
    if not final or final.get('refill_stage') not in ('click_answers', 'explicit_no_answers'):
        raise ValueError('Current base is intermediate; complete the inline answer deck before final delivery')
    if 'editable-pptx' in record.get('stale_targets', []):
        raise ValueError('Current answer deck is stale')
    _file(project, final)
    _versions(project, final.get('source_versions'))
    bound = final.get('base_ref', {})
    if (_file(project, bound) != state.resolve(project, base['path'])
            or bound['sha256'] != base['sha256']):
        raise ValueError('Answer deck does not use the current editable base')
    if reference and (_file(project, reference) != state.resolve(project, final['path'])
                      or reference['sha256'] != final['sha256']):
        raise ValueError('Selected PPT is not the current inline answer deliverable')
    if final['refill_stage'] == 'explicit_no_answers':
        _override(project, final.get('delivery_override'))
    else:
        from . import click_answers
        result = click_answers.validate_final(project, final.get('answer_manifest'))
        if (not result.get('ready_for_final') or result['output_sha256'] != final['sha256']
                or state.resolve(project, result['output']) != state.resolve(project, final['path'])
                or state.resolve(project, result['source_deck']) != state.resolve(project, base['path'])
                or result['source_sha256'] != base['sha256']):
            raise ValueError('Actual inline answer manifest/output is not ready for final selection')
    return final


def delivery_issues(project, record):
    if not state.load_project(project).get('artifacts', {}).get('editable-base-pptx'):
        return []
    try:
        final = current(project)
        sources = {state.resolve(project, path): sha for path, sha in record.get('source_versions', {}).items()}
        if sources.get(state.resolve(project, final['path'])) != final['sha256']:
            raise ValueError('Delivery must bind the current inline answer file; an older delivery is insufficient')
    except (ValueError, TypeError, KeyError) as exc:
        return ['editable: ' + str(exc)]
    return []
