"""Expand approved content into independent full-slide prompts and immutable jobs."""
import hashlib
import json
from pathlib import Path
import re
from PIL import Image
from . import state, checks

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


def page_prompt(page, data):
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
    texts = [unit['text'] for unit in page.get('text_units', [])]
    if not texts or not page.get('layout') or not page.get('visual_description'):
        raise ValueError('Page needs exact text_units, layout and visual_description')
    restrictions = page.get('restrictions', '避免画面杂乱、文字过密、背景抢主体；避免数学关系、物体数量与人物设定错误。')
    visual = page['visual_description']
    if page.get('visual_requirements'):
        visual += '；必须准确满足：' + json.dumps(page['visual_requirements'], ensure_ascii=False)
    body = (f'16:9横版PPT最终完整静态成品页，包含真实文字，不是单独背景图。{style}。'
            f'页面名称：{page["title"]}。构图与版式：{page["layout"]}。'
            f'场景、核心插画与教学画面：{visual}。'
            f'固定角色/地点/道具：{"；".join(character) if character else "本页无指定共享角色"}。'
            '按页面布局清晰呈现以下真实文案，逐字准确，不增删题目条件：\n' +
            '\n'.join('「' + text + '」' for text in texts) + '\n' + LESS + '\n本页限制：' + restrictions)
    if any(phrase in body for phrase in ('同上', '延续上一页风格')):
        raise ValueError('Prompts must expand every page independently')
    formatted = (f'【页面编号】{page["page_id"]}\n【页面名称】{page["title"]}\n'
                 f'【生图提示词】\n{body}\n【画面核心文字】\n' + '\n'.join(texts) +
                 '\n【关键画面元素】\n' + visual + ('；' + '；'.join(character) if character else ''))
    return body, formatted


def render_pages(project):
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
        _, full = page_prompt(page, data)
        formatted.append(full)
        visible.append(f'## {page["page_id"]} {page["title"]}\n\n' +
                       '\n'.join(unit['text'] for unit in page['text_units']))
    for relative, body in [('slides/image-prompts.md', '\n\n'.join(formatted)),
                           ('planning/visible-text.md', '\n\n'.join(visible))]:
        state.resolve(project, relative).write_text(body + '\n', encoding='utf-8')
    versions = {f'_state/{name}.json': state.sha256(state.resolve(project, f'_state/{name}.json'))
                for name in ('pages', 'story', 'math', 'assets')}
    manifest_path = state.resolve(project, '_state/prompt-exports.json')
    prior = state.read_json(manifest_path) if manifest_path.exists() else {}
    retained = []
    if all(prior.get('source_versions', {}).get(k) == v for k, v in versions.items() if k != '_state/pages.json'):
        for file in prior.get('files', []):
            if file['path'].startswith('assets/'):
                target = state.resolve(project, file['path'])
                if target.is_file() and state.sha256(target) == file['sha256']:
                    retained.append(file)
    state.write_json(manifest_path, {'source_versions': versions, 'files': retained + [
        {'path': relative, 'sha256': state.sha256(state.resolve(project, relative))}
        for relative in ('slides/image-prompts.md', 'planning/visible-text.md')]})
    return {'prompts': 'slides/image-prompts.md', 'visible_text': 'planning/visible-text.md', 'pages': len(pages)}


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
    route = project_data.get('image_route')
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
        version = task.get('version', 'v001')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', target) or not re.fullmatch(r'v\d{3,}', version):
            raise ValueError('Unsafe task ID or version')
        required = [] if purpose == 'test' else ['_state/story.json', '_state/math.json']
        if purpose in ('page', 'erase', 'repair'):
            required += ['_state/pages.json', '_state/assets.json']
        state.require_approved(project, *required)
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
            state.require_approved(project, '_state/assets.json')
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
            state.require_approved(project, '_state/assets.json')
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
            prompt, _ = page_prompt(page, data)
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
        job = {'job_id': job_id, 'target_id': target, 'purpose': purpose, 'version': version,
               'route': route, 'provider': 'grsai' if route == 'openai_image_api' else 'codex',
               'prompt_path': prompt_path, 'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
               'references': files, 'input_versions': snapshots,
               'resolution_tier': 'high' if high else 'default',
               'image_api_input': {'endpoint': '/v1/draw/completions',
                                   'model': 'gpt-image-2-vip' if high else 'gpt-image-2.5',
                                   'aspectRatio': size, 'size': size, 'shutProgress': True},
               'status': 'pending', 'output_path': f'{directory}/image.png'}
        if purpose == 'page':
            job['semantic_fingerprint'] = page_fingerprint(data, target)
        job['input_digest'] = state.digest(job)
        path = state.resolve(project, directory + '/job.json')
        if path.exists():
            old = state.read_json(path)
            equivalent = purpose == 'page' and all(old.get(k) == job.get(k) for k in
                ('semantic_fingerprint', 'prompt_sha256', 'references', 'route', 'image_api_input'))
            if old.get('input_digest') != job['input_digest'] and not equivalent:
                raise ValueError('Task ID already has different inputs; create a new version')
        pending.append((job, prompt, directory))
    # Validate whole selection before creating any jobs.
    if len({j['job_id'] for j, _, _ in pending}) != len(pending):
        raise ValueError('Duplicate tasks in selection')
    jobs = []
    for job, prompt, directory in pending:
        path = state.resolve(project, directory + '/job.json')
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            state.resolve(project, job['prompt_path']).write_text(prompt, encoding='utf-8', newline='\n')
            state.write_json(path, job)
        jobs.append(directory + '/job.json')
    batch_id = state.digest(jobs)[:16]
    batch = {'batch_id': batch_id, 'jobs': jobs, 'route': route,
             'authorization_evidence': selection.get('authorization_evidence', ''),
             'concurrency': min(6, len(jobs)), 'timeout_seconds': 500}
    batch['path'] = f'_state/jobs/batch-{batch_id}.json'
    state.write_json(state.resolve(project, batch['path']), batch)
    return batch
