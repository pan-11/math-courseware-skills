"""Expand approved content into independent full-slide prompts and immutable jobs."""
import hashlib
import json
from pathlib import Path
import re
from PIL import Image
from . import state, checks, workflow, preferences, automation_store as store
from .refill_modes import visibility

LESS = ('版式疏朗，视觉重心明确，标题与正文大而清晰，适合课堂投屏。'
        '按页面用途控制密度：封面突出课题形象与故事入口，可展开有层次的完整主场景，'
        '文字区低干扰，不机械限定背景元素数量或大片空底；'
        '知识与练习页突出教学内容，背景适度简化，保留操作区与清晰间距。'
        '内容较多时先删无关装饰与重复UI，不要把全部元素一起缩小，也不降低已定画风的材质与光影完成度。')


def records(project):
    return {name: state.read_json(state.resolve(project, '_state/' + name + '.json'))
            for name in ('pages', 'story', 'math', 'assets')}


def page_fingerprint(data, target):
    page = next((p for p in data['pages'].get('pages', []) if p['page_id'] == target), None)
    if not page:
        raise ValueError('Page no longer exists: ' + target)
    page_content = {k: v for k, v in page.items() if k not in ('order', 'image')}
    refs = {x['asset_id'] for x in page.get('asset_refs', [])}
    return state.digest({'page': page_content, 'visual_style': data['story'].get('visual_style'),
        'math': [m for m in data['math'].get('problems', []) if m['math_id'] in page.get('math_ids', [])],
        'assets': [a for a in data['assets'].get('assets', []) if a['asset_id'] in refs],
        'events': [e for e in data['story'].get('events', []) if e['event_id'] in page.get('story_ids', [])]})


def page_view(page, render_state='review_complete'):
    """Choose review content without rewriting classroom visibility or source text."""
    if render_state not in ('review_complete', 'initial'):
        raise ValueError('Unknown render_state')
    at = visibility(page)
    units = page.get('text_units', [])
    overrides = page.get('review_complete', {}) if render_state == 'review_complete' else {}
    if not isinstance(overrides, dict) or set(overrides) - {'layout', 'visual_description', 'restrictions', 'unit_ids'}:
        raise ValueError('Invalid review_complete fields')
    by_id = {unit['unit_id']: unit for unit in units}
    ids = overrides.get('unit_ids', list(by_id))
    if (not isinstance(ids, list) or any(not isinstance(uid, str) for uid in ids)
            or len(ids) != len(by_id) or set(ids) != set(by_id)):
        raise ValueError('review_complete.unit_ids must cover every text unit exactly once')
    texts = [by_id[uid]['text'] for uid in ids
             if render_state == 'review_complete' or at[uid] == 'initial']
    view = {key: overrides.get(key, page.get(key, ''))
            for key in ('layout', 'visual_description', 'restrictions')}
    if any(not isinstance(value, str) for value in view.values()):
        raise ValueError('Page view descriptions must be strings')
    if not units or not view['layout'].strip() or not view['visual_description'].strip():
        raise ValueError('Page needs exact text_units, layout and visual_description')
    view['texts'] = texts
    return view


def page_prompt(page, data, render_state='review_complete'):
    style = data['story'].get('visual_style', '')
    if not isinstance(style, str) or not style.strip():
        raise ValueError('A complete visual_style string is required in story.json')
    assets = {a['asset_id']: a for a in data['assets'].get('assets', [])}
    character = []
    for ref in page.get('asset_refs', []):
        asset = assets.get(ref['asset_id'])
        if not asset or asset.get('version') != ref.get('version'):
            raise ValueError('Missing matching asset: ' + ref['asset_id'])
        fixed = asset.get('fixed_features')
        if not fixed:
            raise ValueError('Asset needs fixed_features: ' + ref['asset_id'])
        character.append(fixed if isinstance(fixed, str) else json.dumps(fixed, ensure_ascii=False))
    view = page_view(page, render_state)
    texts = view['texts']
    restrictions = view['restrictions'] or '避免画面杂乱、文字过密、背景抢主体；避免数学关系、物体数量与人物设定错误。'
    visual = view['visual_description']
    if page.get('visual_requirements'):
        visual += '；必须准确满足：' + json.dumps(page['visual_requirements'], ensure_ascii=False)
    if render_state == 'review_complete':
        actions = [step['action'] for step in page.get('reveal_steps', []) if step.get('action')]
        if actions:
            visual += '；以下为本页已定教学过程，须画出对应结果和理解所需的有序分步示意（动作说明不上屏）：' + '；'.join(actions)
        state_instruction = ('本图用于完整讲解结果审阅：题干、必要推导、已确认答案、标注和实际数学图示完整可见。'
            '课堂初始隐藏和点击说明仅约束以后放映，不用于隐藏本次审阅内容。'
            '拼摆、剪拼、折叠须画出过程证据与结果；互相替换的状态用有序分步小图，不叠压。'
            '原位填空将已确认答案填入对应空位，题干、运算符与单位只显示一次；独立答案单元不另排重复算式。'
            '只用本页已确认内容，不借后页答案，不为开放题编造唯一答案，不新增讲稿文字。')
    else:
        state_instruction = '本图是明确要求的课堂初始状态；仅显示初始文字和图形，后显内容暂不显示。'
    body = (f'16:9横版PPT最终完整静态成品页，包含真实文字，不是单独背景图。{style}。'
            f'{state_instruction}页面名称：{page["title"]}。构图与版式：{view["layout"]}。'
            f'场景、核心插画与教学画面：{visual}。'
            f'固定角色/地点/道具：{"；".join(character) if character else "本页无指定共享角色"}。'
            '按页面布局清晰呈现以下真实文案，逐字准确，不增删题目条件：\n' +
            ('\n'.join('「' + text + '」' for text in texts) if texts else '初始画面无上屏文字；保留待回答位置，不提前显示答案。') + '\n' + LESS + '\n本页限制：' + restrictions)
    if any(phrase in body for phrase in ('同上', '延续上一页风格')):
        raise ValueError('Prompts must expand every page independently')
    formatted = (f'【页面编号】{page["page_id"]}\n【页面名称】{page["title"]}\n'
                 f'【生图提示词】\n{body}\n【画面核心文字】\n' + ('\n'.join(texts) if texts else '初始画面无上屏文字') +
                 '\n【关键画面元素】\n' + visual + ('；' + '；'.join(character) if character else ''))
    return body, formatted


def render_pages(project, render_state='review_complete'):
    workflow.require(project, 'pages')
    checked = checks.validate(project)
    if not checked['ok']:
        raise ValueError('; '.join(checked['errors']))
    data = records(project)
    pages = sorted(data['pages'].get('pages', []), key=lambda p: p['order'])
    if not pages:
        raise ValueError('No planned pages')
    formatted = []
    visible = []
    for page in pages:
        _, full = page_prompt(page, data, render_state)
        formatted.append(full)
        texts = page_view(page, render_state)['texts']
        visible.append(f'## {page["page_id"]} {page["title"]}\n\n' +
                       ('\n'.join(texts) if texts else '初始画面无上屏文字'))
    used = set(workflow.basis_paths(project)) | {'_state/story.json'}
    versions = {path: state.sha256(state.resolve(project, path)) for path in sorted(used)}
    for relative, body in [('slides/image-prompts.md', '\n\n'.join(formatted)),
                           ('planning/visible-text.md', '\n\n'.join(visible))]:
        state.resolve(project, relative).write_text(body + '\n', encoding='utf-8')
    manifest_path = state.resolve(project, '_state/prompt-exports.json')
    prior = state.read_json(manifest_path) if manifest_path.exists() else {}
    retained = []
    if all(prior.get('source_versions', {}).get(k) == v for k, v in versions.items() if k != '_state/pages.json'):
        for file in prior.get('files', []):
            if file['path'].startswith('assets/'):
                target = state.resolve(project, file['path'])
                if target.is_file() and state.sha256(target) == file['sha256']:
                    retained.append(file)
    state.write_json(manifest_path, {'source_versions': versions, 'render_state': render_state, 'files': retained + [
        {'path': relative, 'sha256': state.sha256(state.resolve(project, relative))}
        for relative in ('slides/image-prompts.md', 'planning/visible-text.md')]})
    return {'prompts': 'slides/image-prompts.md', 'visible_text': 'planning/visible-text.md',
            'pages': len(pages), 'render_state': render_state}


def image_ref(project, file):
    path = state.resolve(project, file['path'])
    if state.sha256(path) != file.get('sha256'):
        raise ValueError('Reference image hash differs: ' + file['path'])
    with Image.open(path) as img:
        img.verify()
    with Image.open(path) as img:
        return {**file, 'width_px': img.width, 'height_px': img.height}


def prepare(project, selection):
    project_data = state.load_project(project)
    run = store.load_run(project)
    route = preferences.effective(project, run, groups={'image'})['image'].get('route')
    if route not in state.ROUTES:
        raise ValueError('Select the project image route before preparing jobs')
    tasks = selection.get('tasks', [])
    if not tasks:
        raise ValueError('Select at least one image task')
    if any(t.get('purpose') == 'test' for t in tasks) and len(tasks) != 1:
        raise ValueError('Single-image connection test cannot start a production batch')
    data = records(project)
    assets = {a['asset_id']: a for a in data['assets'].get('assets', [])}
    pages = {p['page_id']: p for p in data['pages'].get('pages', [])}
    pending = []
    for task in tasks:
        purpose, target = task['purpose'], task['target_id']
        if purpose not in ('page', 'asset', 'cover', 'erase', 'repair', 'test'):
            raise ValueError('Unknown image task purpose')
        workflow.require_image(project, purpose)
        from . import story_adoption
        story_basis = story_adoption.require_image(project, purpose)
        version = task.get('version', 'v001')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', target) or not re.fullmatch(r'v\d{3,}', version):
            raise ValueError('Unsafe task ID or version')
        if purpose == 'test':
            required = []
        elif purpose in ('page', 'erase', 'repair'):
            required = list(workflow.basis_paths(project))
            if purpose == 'page' and '_state/story.json' not in required:
                required.append('_state/story.json')
        else:
            required = [path for path in workflow.basis_paths(project) if path != '_state/pages.json']
        from . import grouped_gates
        candidate = (grouped_gates.image_candidate(project, purpose) if purpose in ('cover', 'asset')
                     and not state.is_approved(project, '_state/assets.json') else None)
        state.require_approved(project, *(p for p in required if not candidate or p != '_state/assets.json'))
        snapshots = {p: state.sha256(state.resolve(project, p)) for p in required}
        page = pages.get(target)
        if purpose in ('page', 'erase', 'repair') and not page:
            raise ValueError('Unknown page ID: ' + target)
        if purpose in ('page', 'erase', 'repair') and target in project_data.get('stale_targets', []):
            raise ValueError('Page needs updated content and approval before generation: ' + target)
        # Selection may add references, but cannot remove canonical page assets.
        refs = list(page.get('asset_refs', [])) if page else []
        if purpose == 'asset':
            target_asset = assets.get(target)
            if not target_asset or target_asset.get('version') != version:
                raise ValueError('Asset task requires its matching canonical definition/version')
            if not candidate: state.require_approved(project, '_state/assets.json')
            snapshots['_state/assets.json'] = state.sha256(state.resolve(project, '_state/assets.json'))
            refs.extend(target_asset.get('reference_assets', []))
        for ref in task.get('reference_assets', []):
            if ref not in refs:
                refs.append(ref)
        files = []
        for ref in refs:
            asset = assets.get(ref['asset_id'])
            if not asset or asset.get('version') != ref.get('version') or not asset.get('files'):
                raise ValueError('Missing generated reference asset: ' + ref['asset_id'])
            if not candidate: state.require_approved(project, '_state/assets.json')
            snapshots['_state/assets.json'] = state.sha256(state.resolve(project, '_state/assets.json'))
            files.extend(image_ref(project, f) for f in asset['files'])
        high = bool(selection.get('high_resolution', False))
        size = '3840x2160' if high else '1672x941'
        if purpose in ('erase', 'repair'):
            if not task.get('source_image'):
                raise ValueError('Edit tasks require the confirmed source image')
            source = image_ref(project, task['source_image'])
            state.require_approved(project, source['path'])
            snapshots[source['path']] = source['sha256']
            files.insert(0, source)
            size = f'{source["width_px"]}x{source["height_px"]}'
            high = max(source['width_px'], source['height_px']) > 2048
        elif purpose == 'asset' and task.get('size'):
            if not re.fullmatch(r'[1-9]\d{1,4}x[1-9]\d{1,4}', task['size']):
                raise ValueError('Asset size must be a pixel width x height')
            size = task['size']
        if purpose == 'page':
            render_state = task.get('render_state', 'review_complete')
            prompt, _ = page_prompt(page, data, render_state)
        elif purpose == 'erase':
            if not task.get('remove_texts') or not task.get('preserve_elements'):
                raise ValueError('Erase requires explicit remove_texts and preserve_elements')
            prompt = ('以提供的已确认页面为唯一底稿做保真去字编辑。只移除以下文字并恢复其下底色：' +
                      '；'.join(task['remove_texts']) + '。必须保留：' + '；'.join(task['preserve_elements']) +
                      '。保留人物、布局、色彩、物体数量、数轴刻度线、几何边界和表格线；不重设计页面、不改变裁切或比例。')
        else:
            prompt = task.get('prompt', '')
            if not prompt.strip():
                raise ValueError('Asset/cover/test/repair requires a complete prompt')
        job_id = f'{target}-{purpose}-{version}'
        directory = f'_state/jobs/{job_id}'
        prompt_path = f'{directory}/prompt.txt'
        path = state.resolve(project, directory + '/job.json')
        old = state.read_json(path) if path.exists() else None
        legacy = old and old.get('route') == 'openai_image_api' and old.get('provider', 'grsai') == 'grsai'
        job = {'job_id': job_id, 'target_id': target, 'purpose': purpose, 'version': version,
               'route': route, 'provider': 'grsai' if route == 'openai_image_api' else 'codex',
               'prompt_path': prompt_path, 'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
               'references': files, 'input_versions': snapshots,
               'resolution_tier': 'high' if high else 'default',
               'image_api_input': {'endpoint': '/v1/draw/completions',
                                   'model': 'gpt-image-2-vip' if high else 'gpt-image-2.5',
                                   'aspectRatio': size, 'size': size, 'shutProgress': True},
               'status': 'pending', 'output_path': f'{directory}/image.png'}
        if route == 'openai_image_api' and not legacy:
            from . import image_toapis
            job['provider'] = 'toapis'
            job['image_api_input'] = image_toapis.job_options(selection, task, size)
        if purpose == 'page':
            job['semantic_fingerprint'] = page_fingerprint(data, target)
            job['render_state'] = render_state
        # Candidate permission is an execution constraint, not a provider input.
        job['input_digest'] = state.digest(job)
        if story_basis: job['story_basis'] = story_basis
        if candidate:
            problems = store.issues(project, {r['path']: r['sha256'] for r in files})
            if problems: raise ValueError('; '.join(problems))
            job['creative_candidate'] = candidate
        if run: job['run_id'] = run['run_id']
        if old is not None:
            equivalent = purpose == 'page' and all(old.get(k) == job.get(k) for k in
                ('semantic_fingerprint', 'prompt_sha256', 'references', 'route', 'image_api_input', 'render_state'))
            if old.get('input_digest') != job['input_digest'] and not equivalent:
                raise ValueError('Task ID already has different inputs; create a new version')
            if old.get('status') == 'pending':
                story_adoption.check_job(project, old)
            if old.get('creative_candidate') and old.get('status') == 'pending':
                grouped_gates.check_image_candidate(project, old)
        pending.append((job, prompt, directory))
    # Validate whole selection before creating any jobs.
    if len({j['job_id'] for j, _, _ in pending}) != len(pending):
        raise ValueError('Duplicate tasks in selection')
    providers = {job['provider'] for job, _, _ in pending}
    if len(providers) != 1:
        raise ValueError('Prepare separate batches for existing Grsai and new ToAPIs tasks')
    jobs = []
    for job, prompt, directory in pending:
        path = state.resolve(project, directory + '/job.json')
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            state.resolve(project, job['prompt_path']).write_text(prompt, encoding='utf-8', newline='\n')
            state.write_json(path, job)
        jobs.append(directory + '/job.json')
    if run: preferences.bind_pending_jobs(project, run['run_id'], jobs)
    batch_id = state.digest(jobs)[:16]
    batch = {'batch_id': batch_id, 'jobs': jobs, 'route': route,
             'authorization_evidence': selection.get('authorization_evidence', ''),
             'concurrency': min(6, len(jobs)), 'timeout_seconds': 500}
    if providers == {'toapis'}:
        batch['provider'] = 'toapis'
    batch['path'] = f'_state/jobs/batch-{batch_id}.json'
    state.write_json(state.resolve(project, batch['path']), batch)
    return batch
