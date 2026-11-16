"""Resolve explicit API asset/view references; builtin image preparation is unchanged."""
import json


def select(assets, canonical, additional):
    """Keep required assets/versions while allowing explicit views instead of defaults."""
    ordered = {}
    for refs in (canonical, additional):
        if not isinstance(refs, list):
            raise ValueError('API reference_assets must be a list')
        for ref in refs:
            if (not isinstance(ref, dict) or not isinstance(ref.get('asset_id'), str)
                    or not isinstance(ref.get('version'), str)):
                raise ValueError('API reference requires asset_id and version')
            views = ref.get('views')
            if 'views' in ref and (not isinstance(views, list) or not views
                    or any(not isinstance(view, str) or not view.strip() for view in views)
                    or len(set(views)) != len(views)):
                raise ValueError('API views must be a nonempty list of unique view names')
            asset_id = ref['asset_id']
            if asset_id in ordered:
                previous = ordered[asset_id]
                if previous['version'] != ref['version']:
                    raise ValueError('Conflicting reference asset version: ' + asset_id)
                if views is not None:
                    previous['views'] = list(dict.fromkeys(previous.get('views', []) + views))
            else:
                ordered[asset_id] = {**ref, **({'views': list(views)} if views is not None else {})}
    result = []
    for ref in ordered.values():
        asset_id = ref['asset_id']
        asset = assets.get(asset_id)
        if not asset or asset.get('version') != ref['version']:
            raise ValueError('Missing matching reference asset version: ' + asset_id)
        files = asset.get('files', [])
        if not files:
            raise ValueError('Missing generated reference asset: ' + asset_id)
        if 'views' in ref:
            selected = []
            for view in ref['views']:
                matches = [file for file in files if file.get('view') == view]
                if not matches:
                    raise ValueError('Unknown or ungenerated reference view: ' + asset_id + '/' + view)
                selected.extend(matches)
            files = selected
        result.extend((asset, file) for file in files)
    return result


def instructions(entries, start=1):
    roles = {'character': ('角色', '沿用角色身份、脸型、发型、服装、比例与配色'),
             'scene': ('场景', '沿用地点外观、主要设施和空间关系'),
             'location': ('场景', '沿用地点外观、主要设施和空间关系'),
             'prop': ('道具', '沿用道具形状、颜色和标志特征，数量按本任务要求'),
             'style': ('画风', '只参考画风、材质、光影与亮度'),
             'style_reference': ('画风', '只参考画风、材质、光影与亮度')}
    lines = []
    for index, (asset, file) in enumerate(entries, start):
        label, purpose = roles.get(asset.get('kind'), ('资产', '沿用已采用的外观和设定'))
        view = '；视角：' + str(file['view']) if file.get('view') else ''
        fixed = asset.get('fixed_features', '')
        if not isinstance(fixed, str):
            fixed = json.dumps(fixed, ensure_ascii=False)
        lines.append(f'图{index}：{asset["asset_id"]}（{asset["version"]}，{label}{view}）。'
                     f'用途：{purpose}。' + ('固定特征：' + fixed + '。' if fixed else ''))
    if lines:
        lines.append('附件编号严格对应实际上传顺序。只绘制本任务明确登场的对象，动作、机位、教学内容及版式按本任务正文执行；'
                     '不直接复制参考图中的题目、文字、版式或无关人物。')
    return '\n'.join(lines)
