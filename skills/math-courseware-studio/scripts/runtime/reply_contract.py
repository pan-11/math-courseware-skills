"""Read-only checks for a reply draft and an optional actual delivery inventory.

This is a bounded Markdown check, not an interceptor or a semantic acceptance gate.
"""
import argparse
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


SECTIONS = ('本步做什么及产出', '需要你检查', '需要你操作', '下一步')
IMAGE_COLUMNS = ('编号', '用途', '实际图片文件')
GENERATION_COLUMNS = ('视频／次数', '内容', '计划时长', '建议上传顺序', '完整提示词')
LINK = re.compile(r'(!?)\[([^\]\n]+)\]\((<[^>\n]+>|[^)\n]+)\)')


def _visible(text):
    """Ignore fenced examples/prompts; they are not actual rendered delivery links."""
    lines, fence = [], None
    for line in text.splitlines():
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            lines.append('')
        else:
            lines.append('' if fence else line)
    return '\n'.join(lines)


def _links(text):
    return [{'image': bool(m[1]), 'label': m[2], 'target': m[3].strip('<>'),
             'position': m.start()} for m in LINK.finditer(text)]


def _local(target, base_dir=None):
    target = unquote(target)
    if target.startswith('#') or re.match(r'^https?://', target, re.I):
        return None
    target = target.split('#', 1)[0]
    target = re.sub(r':\d+$', '', target)
    path = Path(target)
    if not path.is_absolute():
        if base_dir is None:
            return None
        path = Path(base_dir) / path
    return path.resolve()


def _key(path):
    return os.path.normcase(str(path))


def _tables(text):
    lines = text.splitlines(keepends=True)
    tables, offset, current = [], 0, None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [cell.strip() for cell in stripped[1:-1].split('|')]
            if current is None:
                current = {'columns': tuple(cells), 'rows': [], 'position': offset,
                           'separator': None}
                tables.append(current)
            elif current['separator'] is None:
                current['separator'] = len(cells) == len(current['columns']) and all(
                    re.fullmatch(r':?-{3,}:?', cell) for cell in cells)
                if not current['separator']:
                    current['rows'].append(cells)
            else:
                current['rows'].append(cells)
            current['end'] = offset + len(line)
        else:
            current = None
        offset += len(line)
    return tables


def check(text, *, manifest=None, base_dir=None):
    """Return {ok, issues, warnings}; never change files or production state.

    Optional manifest: task_name; video_delivery containing entry, images
    [{number, path, display?}], generations [{label, path}], directories
    [{video_id, path}]. Relative manifest paths use base_dir; chat links are absolute.
    """
    issues, warnings = [], []
    if not isinstance(text, str):
        return {'ok': False, 'issues': ['回复草稿必须是文本。'], 'warnings': []}
    if manifest is None:
        manifest = {}
    if not isinstance(manifest, dict):
        return {'ok': False, 'issues': ['交付清单必须是JSON对象。'], 'warnings': []}
    visible = _visible(text)
    content = [line.strip().replace('**', '') for line in visible.splitlines() if line.strip()]
    header = re.compile(r'^(?:课件|任务)：(.+?)｜当前步骤：(.+?)｜状态：(.+)$')
    heading = header.fullmatch(content[1]) if len(content) > 1 else None
    if not heading or not content[0].endswith(('，', ',')):
        issues.append('称呼后须先写“课件/任务：真实名｜当前步骤：步骤／子步｜状态：实际状态”。')
    elif any(not value.strip() for value in heading.groups()):
        issues.append('任务名、步骤和状态均不能为空。')
    elif manifest.get('task_name') and heading[1].strip() != manifest['task_name']:
        issues.append('开头任务名与外部清单的task_name不一致。')
    section_pattern = re.compile(r'^(' + '|'.join(SECTIONS) + r')：\s*(.*)$')
    markers = [(i, m[1], m[2]) for i, line in enumerate(content)
               if (m := section_pattern.fullmatch(line))]
    if tuple(item[1] for item in markers) != SECTIONS:
        issues.append('开头须依次且各一次列出：' + '、'.join(SECTIONS) + '。')
    else:
        if markers[0][0] != 2:
            issues.append('本步做什么及产出须紧接任务状态行。')
        for n, (index, label, inline) in enumerate(markers):
            if label == '下一步':
                if not inline:
                    issues.append('下一步须写明具体工作或等待输入。')
                continue
            end = markers[n + 1][0]
            body = ([inline] if inline else []) + content[index + 1:end]
            no_action = label != SECTIONS[0] and len(body) == 1 and re.fullmatch(
                r'(?:本步)?无需(?:检查|操作)?[。.]?', body[0])
            numbered = [int(match[1]) for line in body
                        if (match := re.match(r'^(\d+)\.\s+\S', line))]
            if not no_action and (not numbered or numbered != list(range(1, len(numbered) + 1))):
                issues.append(label + '须使用从1开始的编号清单；无检查/操作时明确写本步无需。')

    links = _links(visible)
    for link in links:
        target = link['target']
        if re.match(r'^https?://', target, re.I):
            if not urlsplit(target).netloc:
                issues.append('网页链接缺少有效主机：' + target)
            else:
                warnings.append('网页可访问性未联网核验：' + target)
        elif not target.startswith('#'):
            path = _local(target)
            if path is None:
                issues.append('本地交付链接须用绝对路径：' + target)
            elif not path.exists():
                issues.append('本地链接不存在：' + str(path))

    tables = _tables(visible)
    delivery = manifest.get('video_delivery')
    if delivery is not None or any(table['columns'] in (IMAGE_COLUMNS, GENERATION_COLUMNS) for table in tables):
        next_step = re.search(r'(?m)^(?:\*\*)?下一步(?:\*\*)?：[^\n]+(?:\n|$)', visible)
        body = visible[next_step.end():].lstrip() if next_step else ''
        if not re.match(r'平台[／/]模型：\s*\S', body):
            issues.append('视频交付在共同开头之后须先写“平台／模型：实际选择或尚未确定”。')
        image_tables = [table for table in tables if table['columns'] == IMAGE_COLUMNS]
        generation_tables = [table for table in tables if table['columns'] == GENERATION_COLUMNS]
        if len(image_tables) != 1 or len(generation_tables) != 1:
            issues.append('视频交付须有唯一的编号图片三列表和逐次生成五列表，列名必须完整。')
        elif image_tables[0]['position'] >= generation_tables[0]['position']:
            issues.append('编号图片表必须先于逐次生成表。')
        for table in image_tables + generation_tables:
            if not table['separator']:
                issues.append('视频表头后必须紧接列数一致的Markdown分隔行。')
            if any(len(row) != len(table['columns']) for row in table['rows']):
                issues.append('视频表格的每一行都必须与表头列数一致。')
        actual_status = re.search(r'(?m)^操作与真实状态：[ \t]*\S[^\n]*', visible)
        if actual_status is None:
            issues.append('视频交付末段须包含非空的“操作与真实状态”。')
        elif generation_tables and actual_status.start() < generation_tables[0]['end']:
            issues.append('操作与真实状态必须在逐次生成表和各片目录之后。')
        if delivery is None:
            warnings.append('未提供实际视频交付清单，无法核对遗漏图片、生成次数或独立TXT。')
        elif not isinstance(delivery, dict):
            issues.append('video_delivery必须是对象。')
        else:
            _check_delivery(visible, links, delivery, image_tables, generation_tables,
                            base_dir, issues, actual_status)
        warnings.append('未核验提示词语义完整性、图片内容、真实采用、媒体生成或成片播放。')
    return {'ok': not issues, 'issues': list(dict.fromkeys(issues)),
            'warnings': list(dict.fromkeys(warnings))}


def _check_delivery(text, links, delivery, image_tables, generation_tables, base_dir, issues,
                    actual_status):
    def linked(path, subset=links):
        return [link for link in subset if (local := _local(link['target'])) is not None
                and _key(local) == _key(path)]

    def actual(value, role, directory=False):
        if not isinstance(value, str) or not value.strip():
            issues.append(role + '缺少真实路径。')
            return None
        path = _local(value, base_dir)
        if path is None or not (path.is_dir() if directory else path.is_file()):
            issues.append(role + '不是实际' + ('目录：' if directory else '文件：') + value)
            return None
        if not linked(path):
            issues.append(role + '未在正文直链：' + str(path))
        return path

    entry = delivery.get('entry')
    if not isinstance(entry, str) or not entry.strip():
        issues.append('视频交付清单缺少总入口entry。')
    else:
        path = _local(entry, base_dir)
        platform = re.search(r'(?m)^平台[／/]模型：\s*\S', text)
        if path is None or not path.exists() or not linked(path):
            issues.append('视频总入口不存在或未直链：' + entry)
        elif image_tables and not any(
                (platform is None or link['position'] > platform.end())
                and link['position'] < image_tables[0]['position'] for link in linked(path)):
            issues.append('视频总入口必须在平台/模型之后、编号图片表之前。')
    seen_numbers, seen_prompts, seen_labels = set(), set(), set()
    for key in ('images', 'generations', 'directories'):
        items = delivery.get(key)
        if not isinstance(items, list):
            issues.append('视频交付清单缺少列表：' + key)
            continue
        for item in items:
            if not isinstance(item, dict):
                issues.append(key + '条目必须是对象。')
                continue
            path = actual(item.get('path'), key, directory=key == 'directories')
            if path is None:
                continue
            if key == 'directories':
                if generation_tables and not any(
                        link['position'] >= generation_tables[0]['end']
                        and (actual_status is None or link['position'] < actual_status.start())
                        for link in linked(path)):
                    issues.append('各片普通目录必须列在逐次生成表结束后、操作与真实状态之前：' + str(path))
                continue
            table = image_tables if key == 'images' else generation_tables
            rows = table[0]['rows'] if table else []
            matches = [row for row in rows if linked(path, _links(row[-1]))]
            if len(matches) != 1:
                issues.append(key + '必须在对应表内恰有一行直链：' + str(path))
                continue
            row = matches[0]
            columns = IMAGE_COLUMNS if key == 'images' else GENERATION_COLUMNS
            if len(row) != len(columns) or any(not cell for cell in row):
                issues.append('表格列数或必填内容不完整：' + str(path))
            if not any(link['label'] == path.name for link in linked(path, _links(row[-1]))):
                issues.append('文件链接显示名必须为实际完整文件名：' + str(path))
            if key == 'images':
                number = item.get('number')
                if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                    issues.append('图片编号必须是正整数：' + str(path))
                    continue
                if number in seen_numbers or not path.name.startswith(f'{number:02d}-'):
                    issues.append('图片编号重复或与实际文件名前缀不符：' + str(path))
                seen_numbers.add(number)
                labels = {str(number), f'{number:02d}'}
                if number <= 20:
                    labels.add(chr(0x2460 + number - 1))
                if row[0] not in labels:
                    issues.append('图片表编号与清单不一致：' + str(path))
                if item.get('display') and not any(link['image'] for link in linked(path)):
                    issues.append('实际正式板/首帧需在本次正文展示：' + str(path))
            else:
                label = item.get('label')
                if not isinstance(label, str) or not label or row[0] != label:
                    issues.append('生成次数标识与清单不一致：' + str(path))
                if _key(path) in seen_prompts or str(label) in seen_labels:
                    issues.append('每次生成须有不同的次数标识和独立TXT：' + str(path))
                seen_prompts.add(_key(path))
                seen_labels.add(str(label))
                if path.suffix.lower() != '.txt' or path.stat().st_size == 0:
                    issues.append('每次生成须链接非空独立TXT：' + str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', type=Path, required=True)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig')) if args.manifest else None
    result = check(args.draft.read_text(encoding='utf-8-sig'), manifest=manifest,
                   base_dir=args.manifest.parent if args.manifest else None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
