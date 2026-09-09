# M5 / M7 导出契约与离线证据

更新时间：2026-09-09。实现范围只有 `runtime/exports.py`、`tests/test_exports.py` 及本文；采用现有 Python 运行时的 python-pptx、python-docx、Pillow、ReportLab、pypdf，没有安装依赖或生成真实课件图片。

补充实施约定：每类文稿同目录增加同源 `.md`；`editable/handoff/handoff-vNNN/` 保存 A/B 独立交接 PPTX、PDF、按选择顺序命名的 `page-NNN.<图片扩展名>` 与 manifest，不覆盖旧版。交接只使用已确认的实际输入，B 去字图保存在自己的原路径；不会替换 pages.json 中的带字确认图。交付按当前记录/生成清单逐文件复制，不遍历目录搜集素材。

## 入口与前置状态

`from runtime import exports`；各入口接收课件项目路径，返回可 JSON 序列化的报告；失败抛出 `ValueError` 或文件/格式读取错误。

| API | 实际输出 | 返回重点 |
|---|---|---|
| `export_slides(project)` | `slides/export-vNNN/lesson-images.pptx`、同名 PDF、manifest.json | artifacts、source_versions、page_order、image_layout、manifest |
| `export_documents(project)` | `documents/export-vNNN/<kind>/<kind>.docx`、同名 PDF/MD、各 manifest 及总 manifest | documents[kind] 报告、output |
| `export_handoff(project, selection)` | `editable/handoff/handoff-vNNN/` 的 PPTX/PDF、图片副本及 manifest | route、review_status、page_mapping、files、artifacts、manifest |
| `collect(project)` | `deliveries/delivery-vNNN/` 下保留原相对目录的交付副本及 manifest | artifacts 含 delivery_path、manifest |

导出前，当前 `_state/pages.json`、story.json、math.json、assets.json 以及每页真实图片必须经 `state.require_approved` 验证。按 pages 中正整数 `order` 排序，`page_id` 与 `order` 均须唯一。每页必须有 `image: {path: 项目内相对路径, sha256: 当前文件哈希}`。不生成缺失图片、不凭文件名假定已确认。输出基于完整确认的图片课件；视频尚未产出不阻断文稿，WPS 视觉验收另行记录。

图片 PPTX 为 960×540 pt，PDF 同尺寸。保持原像素比例，以白色留边居中放入，manifest 记录原尺寸和左上原点的 `content_rect_pt=[x,y,width,height]`；PPTX 图片对象名称保留 page_id。没有拉伸，不宣称图片 PPTX 为分层可编辑稿。

## 可画 A/B 独立交接

```json
{"route":"B","pages":[{"page_id":"page-002","image":{"path":"slides/textless/page-002.png","sha256":"实际SHA256"}}]}
```

selection 必须包含 A/B 路线和有序、非空的真实页面子集。A 的每个 image 必须与对应 canonical page.image 的路径和哈希一致；B 必须选择另一路径的已确认去字图。均检查核心四份记录已确认、所选页面的带字确认图和选中图片已确认及哈希匹配。子集试样不要求尚未制作的其他页面已有图片；完整课件导出与最终 collect 仍检查全部页图。

不编辑 pages.json、不改带字图、不生成去字图。已有的独立确认去字图用于 B；图片内容是否符合去字要求仍由该图确认环节负责。交接状态统一为 `waiting_manual_canva`，不宣称已拆层或已回传。

每个包包含 `canva-handoff.pptx`、`canva-handoff.pdf`、`page-NNN.<原图片扩展名>` 和 `manifest.json`。报告 `page_mapping` 逐项含 page_id、handoff_slide_number、canonical_image、selected_image、image_copy；`files` 逐项含 path/sha256；记录 source_versions、image_layout、route。注册 ID 为 `canva-handoff-a-pptx/pdf/manifest` 或 `canva-handoff-b-pptx/pdf/manifest`，manifest 注册元数据含 `handoff_manifest:true`，使 collect 只读取经注册且哈希匹配的实际交接清单。

## 文稿规范化输入

三个 JSON 分别位于 `_state/documents/classroom-script.json`、`lesson-presentation.json`、`lesson-plan.json`。由写作模块形成完整内容；导出器只校验和排版，不生成教学事实。

共有字段：

```json
{
  "title": "合成示例标题",
  "source_versions": {"_state/pages.json": "实际SHA256"},
  "page_order": ["page-001", "page-002"],
  "content": []
}
```

上述 source_versions 是简化展示，实际必须包含当前 pages/story/math/assets 四份文件及全部已确认页图的哈希；允许添加其余实际依据文件，所有路径都必须在项目内并逐一匹配真实哈希。page_order 必须与当前页面稳定 ID 顺序完全一致。导出器另记录自身规范化 JSON 的哈希；对文稿 JSON 不追加用户最终确认门禁。

课堂逐字稿 content：

```json
[
  {"page_id":"page-001","title":"认识数量","paragraphs":["同学们，请观察这组图形。"]},
  {"page_id":"page-002","title":"比较数量","paragraphs":["请说一说你的比较依据。"]}
]
```

必须逐页一次覆盖，不接受额外、缺失或乱序 ID。可见内容仅显示题头、页码/标题及正文；内部 ID、哈希等不印入正文。

说课稿 content：

```json
[
  {"heading":"教材分析","paragraphs":["依据实际课件填写完整分析。"],"page_ids":["page-001"]},
  {"heading":"教学过程","paragraphs":["依据定稿解释活动设计理由。"],"page_ids":["page-002"]}
]
```

此为数据结构示例，不代表完整说课稿；完整章节按 Skill 中的用户规范写作。每个章节含内部 `page_ids` 列表；通用开场等可为空，所有章节关联的并集必须覆盖全部当前页面，不接受未知 ID。

教学设计 content：

```json
{
  "metadata":[{"heading":"教学目标","paragraphs":["依据定稿填写目标。"]}],
  "rows":[{"page_ids":["page-001","page-002"],"cells":["探究","教师活动","学生活动","任务与评价","设计意图"]}],
  "afterword":[{"heading":"教学反思","paragraphs":["课后填写：观察学生表达依据，记录需调整的支持。"]}]
}
```

metadata 与 rows 必填且非空，afterword 可选。metadata/afterword 的每个元素含 heading 与非空 paragraphs；rows 每行严格五个非空字符串，换行用 `\n` 表达。五列为“环节、教师活动、学生活动、任务与评价、设计意图/二次备课”。rows 的 page_ids 并集覆盖当前页面。作业、板书、反思等完整性由写作模块依据用户材料检查，不使用关键词禁令假装完成教学自审。

## 排版与证据边界

- 三份 DOCX/PDF/Markdown 都由同一规范化数据及同一块序列生成；原文 `<`、`>`、`&` 会正确转义，保留数学表达。Markdown 表格使用固定五列，文本里的管道符、反斜线及 Markdown 标点以字符实体保留，换行用 `<br/>`；字面 `<br/>` 单独转义，不混同真实换行。新增 `<kind>-md` 注册 ID。
- A4 纵向，左右23 mm、上下22 mm；无独立封面。正文11 pt、1.4倍行距；教学表10.5 pt、紧凑行距、固定总宽164 mm。DOCX 设置 eastAsia 字体与 zh-CN，表格列宽和单元格宽同时写入，重复表头，允许行跨页。
- PDF 使用本机实际安装的 TrueType 中文字体，依次查找华文宋体/仿宋/楷体；当前实测 STSONG.TTF / 华文宋体。逐字核查字符是否在字体中，缺字直接失败。仅 PDF 嵌入使用到的字体子集；不将原字体文件打入 Skill 或发布包。
- ReportLab LongTable 支持页内拆长行；已修复标题 keepWithNext 把整个长表推到下一页、产生首大段留白的问题。教学过程标题不套整表 KeepTogether。
- DOCX 回读全部正文和表格单元格；PDF 段落按去空白原文回读，跨页表格因列阅读顺序交错，内部校验使用全量字符覆盖，并通过测试核对中文关键句与末尾步骤。字符覆盖不能证明每个表格单元格的视觉排版；另有 PDF 实际渲染检查。
- WPS 原生显示未验证；Python 结构与 PDF 渲染不能替代 WPS 实测。完整首课教学内容、实际图片质量与可画回传不属于合成夹具验收。

## 版本、依赖与交付

所有导出目录递增，不覆盖旧版。产物通过 `state.register_artifact` 注册固定逻辑 ID，例如 `image-slides-pptx`、`classroom-script-docx`；后续导出更新当前指针，旧版文件保留。metadata 包含 source_versions 与 page_order，依赖包括全部来源路径和页 ID。导出注册前再次核对来源，避免直接接受执行期间变更。

collect 按以下明确清单收集，任何候选 stale、内容哈希变化、来源版本变化或缺少 source_versions 均拒绝，不现场重新生成提示词来掩盖过期状态：

- 当前注册的 `.pptx/.pdf/.docx/.md`，位置限定 `slides/export-v*`、`documents/export-v*`、`editable/output/`、`editable/handoff/handoff-v*`。可编辑模块注册产物时也必须提供 source_versions。
- 当前 pages 的每页真实确认图，交付到 `slides/page-images/page-NNN.ext`；当前已确认 assets 记录的 files 逐项核对真实图片与哈希，交付到 `assets/shared/asset-NNN-file-NNN.ext`。原图可来自生成任务输出，但只复制明确引用的图片，不复制任务目录、缓存或其他文件。
- `slides/image-prompts.md`、`planning/visible-text.md`、`assets/asset-prompts.md` 以及 assets 中明确给出的 prompt_path。后者必须位于 assets/ 内，扩展名 `.md/.txt`，不得有隐藏路径段。文件存在时，必须在 `_state/prompt-exports.json` 的 files 中有匹配路径/哈希，其 source_versions 必须匹配当前四份核心记录。没有清单、缺条目或过期均拒绝；不得仅因为存在就复制。
- 已注册 `handoff_manifest:true` 且路径/哈希/source_versions 匹配的交接 manifest；只复制其 files 明确列出的同目录 PPTX/PDF/图片，拒绝越出交接包的成员，不遍历交接文件夹。

`_state/prompt-exports.json` 格式为 `{"source_versions":{"_state/pages.json":"实际哈希", "其余三个核心路径":"实际哈希"},"files":[{"path":"slides/image-prompts.md","sha256":"实际哈希"}]}`。每个需交付的生成提示词必须有条目；清单也可列其他文件，但 collect 不会复制允许清单之外的条目。主执行器的 render_pages 已提供两个页面文字文件的生成清单。

交付 manifest 每项保留原 path、sha256、source_versions 及实际 delivery_path；显式媒体映射另有 destination。旧导出保留而不默认收集。最终写交付 manifest 前再次检查全部来源。不会复制整个项目、原始课程输入、凭据、无关缓存或未被明确引用的文件。

## 验证记录

运行命令：

```powershell
& 'C:/Users/sansh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -m unittest discover -s tests -p test_exports.py -v
```

最新7项行为测试全部通过（4.605秒）：真实格式/已确认图像字节、稳定页序、4:3留边和16:9尺寸、版本保留；三份中文同源 DOCX/PDF/MD、数学符号、11 pt与eastAsia、跨页长表及重复表头；错页/过期来源/未确认图片拒绝；交付范围、stale及产物哈希漂移拒绝；Markdown 五列表内管道符、字面 HTML、真实换行和反斜线回读；A/B 子集图源字节一致及 pages.json 哈希不变，未制作其他页图不阻断试样；共享资产/明确提示词/可画交接清单收集和未注册私有文件排除。

合成夹具全部保留于 `tests/runs/exports-*`。已实际用现有 pypdfium2 渲染三类 PDF，并查看拼图；发现并修复长表首页留白后，再次查看 `tests/runs/exports-20260909-214351-03e80dbd/documents/export-v001/lesson-plan/pdf-review-first.png`，首个探究长行已在首页正常开始。此前渲染拼图位于 `exports-20260909-214228-7ec0863a/documents/export-v001/pdf-review.png`，包含修复前问题，作为过程证据保留，不用作最终示例。

主执行器现已接入四个 API、同步 Skill 输入说明，全项目47项测试通过。真实首课仍需内容审查、可画拆层与 WPS 显示检查。此导出模块未删除文件、改全局配置、安装依赖或公开发布；项目内格式校验依赖另见实施检查记录。
