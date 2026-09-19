#!/usr/bin/env python3
"""Local execution entrypoint; content authoring stays with the calling Codex Skill."""
import argparse
import json
from pathlib import Path
import sys
from runtime import state, checks, prompts, workflow


def validate_editable_authority(project, plan):
    state.require_approved(project, '_state/pages.json')
    pages = {p['page_id']: p for p in state.read_json(state.resolve(project, '_state/pages.json'))['pages']}
    mapping = plan.get('mapping', {})
    if not mapping or set(mapping) - set(pages):
        raise ValueError('Editable plan maps unknown or no pages')
    text_refill = plan.get('build_scope') == 'text-refill'
    if text_refill and set(mapping) != set(pages):
        raise ValueError('Full text-refill must cover every page')
    units = plan.get('text_units', [])
    from runtime.pptx_editor import expand_text_units
    expanded = expand_text_units(units)
    for page_id in mapping:
        source = {u['unit_id']: u['text'] for u in pages[page_id].get('text_units', [])}
        selected = [u for u in units if u['page_id'] == page_id]
        actual = {u['unit_id']: u['text'] for u in selected}
        if len(actual) != len(selected) or source != actual:
            raise ValueError(page_id + ': editable plan must cover every authoritative text unit exactly')
        required = {x['object_id'] for x in pages[page_id].get('native_objects', []) if x.get('required', True)}
        legacy = pages[page_id].get('editable_objects', [])
        text_roles = {u.get('role') for u in pages[page_id].get('text_units', [])}
        for item in legacy:
            if isinstance(item, str) and item not in text_roles and item not in ('text', 'question', 'answer', 'title', 'step', 'label'):
                required.add(item)
        provided = {x.get('object_id') for x in plan.get('required_native_objects', []) if x['page_id'] == page_id}
        provided.update(unit['unit_id'] for unit, logical in expanded if unit['page_id'] == page_id)
        if text_refill:
            remaining = [item for item in plan.get('remaining_native_objects', []) if item.get('page_id') == page_id]
            remaining_ids = {item.get('object_id') for item in remaining}
            if (remaining_ids != required - provided or len(remaining_ids) != len(remaining)
                    or any(not isinstance(item.get('reason'), str) or not item['reason'].strip() for item in remaining)):
                raise ValueError(page_id + ': remaining native objects must list every unresolved requirement exactly')
            continue
        if required - provided:
            raise ValueError(page_id + ': independently editable math objects still need mapping: ' + ', '.join(sorted(required - provided)))
    if any(u['page_id'] not in mapping for u in units):
        raise ValueError('Text unit page is outside the reviewed page mapping')


def parser():
    top = argparse.ArgumentParser(description='小学数学AI赋能课件：本地记录、生成任务、可编辑处理和导出')
    sub = top.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor', help='Read-only environment check')
    commands = ['init', 'status', 'validate', 'workflow-check', 'record-approval', 'impact', 'record-change',
                'render-prompts', 'image-prepare', 'image-run', 'image-resume', 'image-register',
                'export-slides', 'canva-handoff', 'canva-import', 'editable-build', 'export-documents', 'collect']
    for command in commands:
        p = sub.add_parser(command)
        p.add_argument('--project', required=True, type=Path)
        if command == 'init':
            p.add_argument('--title', required=True)
            p.add_argument('--route', choices=state.ROUTES)
            p.add_argument('--mode', choices=('full_course', 'selected_modules'))
            p.add_argument('--scope-evidence', default='')
        if command == 'workflow-check':
            p.add_argument('--step', required=True)
            p.add_argument('--video-id')
        filearg = {'record-approval': 'record', 'impact': 'change', 'record-change': 'change',
                   'image-prepare': 'selection', 'image-run': 'batch', 'image-resume': 'batch',
                   'image-register': 'result', 'editable-build': 'plan', 'canva-handoff': 'selection'}.get(command)
        if filearg:
            p.add_argument('--' + filearg, required=True, type=Path)
        if command in ('image-run', 'image-resume'):
            group = p.add_mutually_exclusive_group()
            group.add_argument('--key-file', type=Path)
            group.add_argument('--key-stdin', action='store_true')
        if command == 'canva-import':
            p.add_argument('--deck', type=Path, required=True)
            p.add_argument('--mapping', type=Path, required=True)
    return top


def execute(args):
    c = args.command
    if c == 'doctor':
        return checks.doctor()
    project = args.project.resolve()
    if c == 'init':
        return state.init_project(project, args.title, args.route,
                                  getattr(args, 'mode', None), getattr(args, 'scope_evidence', ''))
    if c == 'workflow-check':
        return workflow.check(project, args.step, video_id=args.video_id)
    state.load_project(project)
    if c == 'status':
        return state.status(project)
    if c == 'validate':
        return checks.validate(project)
    if c == 'record-approval':
        return state.record_approval(project, state.read_json(args.record))
    if c in ('impact', 'record-change'):
        return getattr(state, c.replace('-', '_'))(project, state.read_json(args.change))
    if c == 'render-prompts':
        return prompts.render_pages(project)
    if c == 'image-prepare':
        return prompts.prepare(project, state.read_json(args.selection))
    if c in ('image-run', 'image-resume', 'image-register'):
        from runtime import image_api
        if c == 'image-register':
            return image_api.register_builtin(project, state.read_json(args.result))
        batch = state.read_json(args.batch)
        if batch.get('route') != 'openai_image_api' or not batch.get('authorization_evidence', '').strip():
            raise ValueError('Grsai route and actual batch authorization are required')
        key = image_api.read_key(project, args.key_file, args.key_stdin)
        return image_api.run_batch(project, batch, key, resume=c == 'image-resume')
    if c in ('canva-import', 'editable-build'):
        from runtime import pptx_editor
        workflow.require(project, 'editable-import' if c == 'canva-import' else 'editable-build')
        if c == 'canva-import':
            mapping = state.read_json(args.mapping)
            page_ids = {p['page_id'] for p in state.read_json(state.resolve(project, '_state/pages.json'))['pages']}
            if set(mapping) - page_ids:
                raise ValueError('Canva mapping contains unknown page IDs')
            return pptx_editor.import_deck(project, args.deck, mapping)
        plan = state.read_json(args.plan)
        validate_editable_authority(project, plan)
        result = pptx_editor.build_editable(project, plan)
        versions = {path: state.sha256(state.resolve(project, path))
                    for path in workflow.basis_paths(project)}
        versions[plan['source_deck']] = plan['source_sha256']
        authority = plan.get('authorization', plan.get('review'))
        versions[authority['evidence']] = authority['sha256']
        for page in state.read_json(state.resolve(project, '_state/pages.json'))['pages']:
            if page['page_id'] in plan['mapping'] and page.get('image'):
                versions[page['image']['path']] = page['image']['sha256']
        state.register_artifact(project, 'editable-pptx', result['output'],
                                [*versions, *plan['mapping']],
                                {'source_versions': versions, 'review_status': 'text_refilled_graphics_pending'
                                 if result.get('remaining_native_objects') else 'structure_checked_wps_pending'})
        return result
    from runtime import exports
    if c == 'canva-handoff':
        return exports.export_handoff(project, state.read_json(args.selection))
    return getattr(exports, c.replace('-', '_'))(project)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if isinstance(result, dict):
            if result.get('ok') is False or result.get('allowed') is False:
                return 1
            if 'results' in result and any(r.get('status') != 'downloaded' for r in result['results']):
                return 1
        return 0
    except Exception as exc:
        # Network errors may contain request data; never emit arbitrary transport exceptions.
        message = str(exc) if isinstance(exc, (ValueError, FileNotFoundError)) else type(exc).__name__
        print(json.dumps({'ok': False, 'error': message}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
