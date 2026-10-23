"""Reply checks use retained synthetic files, never a real course or media API."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/math-courseware-studio/scripts'))
try:
    from runtime import reply_contract
except ImportError:
    reply_contract = None


def opening(status='进行中', work='计划：核对回传文件，产出接收清单。'):
    return f'''鹿鸣，

课件：《合成课》｜当前步骤：独立回填／接收检查｜状态：{status}

本步做什么及产出：

1. {work}

需要你检查：本步无需检查。

需要你操作：本步无需操作。

下一步：核对现有文件后继续已授权回填。
'''


class ReplyContractTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(reply_contract, 'The shared draft checker is required')

    def check(self, text, manifest=None):
        return reply_contract.check(text, manifest=manifest)

    def video_fixture(self):
        root = ROOT / 'tests/runs' / ('reply-contract-' + uuid.uuid4().hex)
        root.mkdir(parents=True)
        (root / 'AGENTS.md').write_text(
            '# Synthetic reply validation\n\nRetain all fixtures. No real lessons, media APIs or credentials.\n',
            encoding='utf-8')
        (root / 'start-here.md').write_text('Synthetic delivery index', encoding='utf-8')
        video = root / 'V001'
        video.mkdir()
        # Valid tiny PNG; the checker only promises existence, naming and coverage.
        import base64
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWZ0AAAAASUVORK5CYII=')
        for name in ('01-first-frame.png', '02-character.png'):
            (video / name).write_bytes(png)
        for name in ('V001-C01.txt', 'V001-C02.txt'):
            (video / name).write_text('完整合成提示词：固定画面，角色说出测试对白。', encoding='utf-8')
        paths = {p.name: p.as_posix() for p in video.iterdir()}
        manifest = {'task_name': '《合成课》', 'video_delivery': {
            'entry': (root / 'start-here.md').as_posix(),
            'images': [
                {'number': 1, 'path': paths['01-first-frame.png'], 'display': True},
                {'number': 2, 'path': paths['02-character.png']}],
            'generations': [
                {'label': '第1段·V001·C01', 'path': paths['V001-C01.txt']},
                {'label': '第1段·V001·C02', 'path': paths['V001-C02.txt']}],
            'directories': [{'video_id': 'V001', 'path': video.as_posix()}]}}
        text = opening('本步已完成', '已完成：两张实图与两份完整TXT，产物如下。') + f'''
平台／模型：沿用本课已确认设置；本合成测试不调用服务。

[打开全部素材与提示词总表](<{manifest['video_delivery']['entry']}>)

![实际首帧](<{paths['01-first-frame.png']}>)

| 编号 | 用途 | 实际图片文件 |
|---|---|---|
| ① | 首帧 | [01-first-frame.png](<{paths['01-first-frame.png']}>) |
| ② | 角色 | [02-character.png](<{paths['02-character.png']}>) |

每份TXT包含完整提示词。

| 视频／次数 | 内容 | 计划时长 | 建议上传顺序 | 完整提示词 |
|---|---|---|---|---|
| 第1段·V001·C01 | 开场 | 计划5秒，待核 | ①② | [V001-C01.txt](<{paths['V001-C01.txt']}>) |
| 第1段·V001·C02 | 收束 | 计划5秒，待核 | ① | [V001-C02.txt](<{paths['V001-C02.txt']}>) |

[第1段·V001素材文件夹](<{video.as_posix()}>)

操作与真实状态：部分准备稿；未调用生成服务，无实际成片。
'''
        (root / 'draft.md').write_text(text, encoding='utf-8')
        (root / 'delivery-inventory.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return text, manifest

    def test_progress_waiting_question_and_delivery_share_opening(self):
        for status in ('进行中', '等待回传', '待核查', '本步已完成'):
            with self.subTest(status=status):
                self.assertTrue(self.check(opening(status))['ok'])

    def test_missing_or_misordered_sections_are_reported(self):
        self.assertFalse(self.check(opening().replace('需要你检查：本步无需检查。', ''))['ok'])
        swapped = opening().replace('需要你检查', 'TEMP').replace('需要你操作', '需要你检查').replace('TEMP', '需要你操作')
        self.assertFalse(self.check(swapped)['ok'])
        self.assertFalse(self.check(opening().replace('1. 计划', '- 计划'))['ok'])

    def test_empty_task_status_and_wrong_expected_course_fail(self):
        self.assertFalse(self.check(opening().replace('《合成课》', ''))['ok'])
        self.assertFalse(self.check(opening().replace('｜状态：进行中', '｜状态：'))['ok'])
        self.assertFalse(self.check(opening(), {'task_name': '《另一课》'})['ok'])

    def test_numbered_actions_and_explicit_none_are_supported(self):
        text = opening().replace('需要你操作：本步无需操作。', '需要你操作：\n\n1. 回传当前拆层PPTX。')
        self.assertTrue(self.check(text)['ok'])
        self.assertFalse(self.check(text.replace('1. 回传', '2. 回传'))['ok'])

    def test_valid_video_has_both_tables_all_files_and_display(self):
        text, manifest = self.video_fixture()
        self.assertTrue(self.check(text, manifest)['ok'])

    def test_summary_link_cannot_replace_video_tables(self):
        text, manifest = self.video_fixture()
        summary_only = opening() + '[总入口](<' + manifest['video_delivery']['entry'] + '>)'
        self.assertFalse(self.check(summary_only, manifest)['ok'])

    def test_platform_is_first_body_item_and_can_be_unknown(self):
        text, manifest = self.video_fixture()
        platform = '平台／模型：沿用本课已确认设置；本合成测试不调用服务。'
        self.assertTrue(self.check(text.replace(platform, '平台／模型：尚未确定。'), manifest)['ok'])
        self.assertFalse(self.check(text.replace(platform, ''), manifest)['ok'])
        self.assertFalse(self.check(text.replace(platform, '') + '\n' + platform, manifest)['ok'])

    def test_omitted_image_or_generation_is_found_from_external_manifest(self):
        text, manifest = self.video_fixture()
        for marker in ('| ② |', '| 第1段·V001·C02 |'):
            with self.subTest(marker=marker):
                incomplete = '\n'.join(line for line in text.splitlines() if marker not in line)
                self.assertFalse(self.check(incomplete, manifest)['ok'])

    def test_swapped_tables_wrong_columns_or_image_number_fail(self):
        text, manifest = self.video_fixture()
        self.assertFalse(self.check(text.replace('实际图片文件', '参考图'), manifest)['ok'])
        self.assertFalse(self.check(text.replace('| ② |', '| ③ |'), manifest)['ok'])
        blocks = text.split('\n\n')
        indices = [n for n, block in enumerate(blocks) if block.startswith('| 编号') or block.startswith('| 视频／')]
        blocks[indices[0]], blocks[indices[1]] = blocks[indices[1]], blocks[indices[0]]
        self.assertFalse(self.check('\n\n'.join(blocks), manifest)['ok'])

    def test_video_tables_require_immediate_matching_separator_rows(self):
        text, manifest = self.video_fixture()
        missing = '\n'.join(line for line in text.splitlines()
                            if line not in ('|---|---|---|', '|---|---|---|---|---|'))
        self.assertFalse(self.check(missing, manifest)['ok'])
        mismatched = text.replace('|---|---|---|\n', '|---|---|\n')
        self.assertFalse(self.check(mismatched, manifest)['ok'])

    def test_all_video_table_rows_must_match_column_count(self):
        text, manifest = self.video_fixture()
        for separator in ('|---|---|---|\n', '|---|---|---|---|---|\n'):
            with self.subTest(separator=separator):
                malformed = text.replace(separator, separator + '| 只有一列 |\n')
                self.assertFalse(self.check(malformed, manifest)['ok'])

    def test_video_directory_link_inside_generation_cell_is_not_after_table(self):
        text, manifest = self.video_fixture()
        directory = next(line for line in text.splitlines() if line.startswith('[第1段·V001素材文件夹]'))
        misplaced = text.replace(directory + '\n', '').replace('| 收束 |', '| 收束 ' + directory + ' |')
        self.assertFalse(self.check(misplaced, manifest)['ok'])

    def test_operations_and_actual_status_are_required_after_directories(self):
        text, manifest = self.video_fixture()
        status = '操作与真实状态：部分准备稿；未调用生成服务，无实际成片。'
        self.assertFalse(self.check(text.replace(status, ''), manifest)['ok'])
        self.assertFalse(self.check(text.replace(status, '操作与真实状态：'), manifest)['ok'])
        early = text.replace(status, '').replace('| 编号 |', status + '\n\n| 编号 |')
        self.assertFalse(self.check(early, manifest)['ok'])
        directory = next(line for line in text.splitlines() if line.startswith('[第1段·V001素材文件夹]'))
        late_directory = text.replace(directory, '').rstrip() + '\n\n' + directory + '\n'
        self.assertFalse(self.check(late_directory, manifest)['ok'])

    def test_wrong_label_or_same_txt_for_two_generations_fails(self):
        text, manifest = self.video_fixture()
        self.assertFalse(self.check(text.replace('第1段·V001·C02', '第1段·V001·C99'), manifest)['ok'])
        repeated = deepcopy(manifest)
        repeated['video_delivery']['generations'][1]['path'] = repeated['video_delivery']['generations'][0]['path']
        self.assertFalse(self.check(text, repeated)['ok'])

    def test_missing_inline_frame_or_video_directory_fails(self):
        text, manifest = self.video_fixture()
        for marker in ('![实际首帧]', '[第1段·V001素材文件夹]'):
            incomplete = '\n'.join(line for line in text.splitlines() if marker not in line)
            self.assertFalse(self.check(incomplete, manifest)['ok'])

    def test_broken_local_links_fail_and_remote_links_are_not_claimed_verified(self):
        text, manifest = self.video_fixture()
        missing = manifest['video_delivery']['entry'] + '.missing'
        self.assertFalse(self.check(opening() + f'\n[缺失](<{missing}>)')['ok'])
        result = self.check(opening() + '\n[官方说明](https://example.com/guide)')
        self.assertTrue(result['ok'])
        self.assertTrue(result['warnings'])

    def test_fenced_prompt_contents_do_not_count_as_actual_links_or_sections(self):
        text = opening() + '\n```markdown\n[不要发送的示例](missing.txt)\n需要你操作：示例\n```\n'
        self.assertTrue(self.check(text)['ok'])


if __name__ == '__main__':
    unittest.main()
