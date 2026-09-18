# 项目协议

## 执行与目录

整个十二Skill源码集合放在同一父目录，专业Skill通过相邻`math-courseware-studio/scripts/courseware.py`定位执行器。路径相对于当前课件项目，调用时传项目绝对路径；包内不写某台机器的Python、字体或用户名路径。

先用运行时发现工具找到已有Python及文档库，执行`courseware.py doctor`。普通用户以自然语言工作，JSON与命令由Codex维护。

项目初始化先写AGENTS.md和HANDOFF.md，再创建：

| 目录 | 内容 |
|---|---|
| inputs | 原课件、教材及补充材料的原样副本 |
| planning | 教学分析、数学核查、故事、页面方案、可见文字稿 |
| assets/characters、scenes、props | 实际设定图、版本与提示词 |
| slides | 页面提示词、图及版本化图片课件 |
| editable/handoff、returned、output | 可画交接、原始回传副本、修改结果 |
| documents | 三类文稿的版本化输出 |
| _state | 权威记录、确认、变更、任务、坐标、文稿源和检查 |
| deliveries | 当前有效交付物的副本与清单 |

不自动清理旧版。原稿不覆盖，发布与全局安装另按实际授权处理。

从头整课的视频为必做，进入方案与制作流程阶段就按实际需要扩展`videos/<video_id>/<version>/`，交付时用`deliveries/video-delivery-vNNN/`；先补当前课AGENTS再创建，现有init不自动建立这些目录。具体文件、manifest和回传约定见[视频交接](../../math-courseware-video/references/handoff.md)。复用story.video_nodes及通用artifacts，保持现有schema；视频技术状态放视频manifest，避免每次生成导致共同故事失效。

## 权威数据

初始化生成`schema_version=1.0`，`revision=v001`。项目元数据含`project_id/title/image_route/font/branches/artifacts/stale_targets`。内容记录使用：

| 文件 | 主要字段 |
|---|---|
| materials.json | materials:[{material_id,path,sha256,type,pages_read,notes}] |
| math.json | problems:[{math_id,question,givens,answer,reasoning,source_refs}] |
| story.json | events:[{event_id,place,characters,math_ids,description}], visual_style:完整字符串, video_nodes:[…] |
| assets.json | assets:[{asset_id,kind,version,fixed_features,view_definitions,files,prompt_path}] |
| pages.json | pages:[页面记录] |

教学分析由Codex写，执行器检查记录与引用，不自动推断教材或证明数学推理。`source_refs`至少可定位原文件/页码；来源不足的内容保留不确定性，不填假来源。

每条资产`files`为`[{path,sha256,width_px,height_px,view}]`，记录真实字节。`fixed_features`写可直接展开到提示词的完整外观或地点关系。设定图与单独视角可以共存，后续任务选择实际所需参考。

页面最小结构：

```json
{
  "page_id": "P007",
  "order": 7,
  "title": "一共有多少个？",
  "teaching_goal": "理解相同加数与乘法的联系",
  "student_activity": "先分组数，再解释算式",
  "teacher_question": "为什么能用乘法？",
  "math_ids": ["M001"],
  "asset_refs": [{"asset_id": "CHAR001", "version": "v001"}],
  "story_ids": ["E001"],
  "video_ids": [],
  "layout": "左侧分组图，右侧题干与独立答案卡",
  "visual_description": "五组苹果，每组恰有三个；组与组间距明显",
  "visual_requirements": {"group_count": 5, "items_per_group": 3, "total_count": 15},
  "text_units": [
    {"unit_id": "P007-T01", "role": "title", "text": "一共有多少个？"},
    {"unit_id": "P007-T02", "role": "question", "text": "5组，每组3个"},
    {"unit_id": "P007-T03", "role": "answer", "text": "3×5＝15（个）"}
  ],
  "native_objects": [
    {"object_id": "group-1", "required": true},
    {"object_id": "group-2", "required": true},
    {"object_id": "group-3", "required": true},
    {"object_id": "group-4", "required": true},
    {"object_id": "group-5", "required": true}
  ]
}
```

示例不指定首课课题。算式顺序按实际教材。所有真正显示的标题、按钮、标签都进入`text_units`，辅助教师提示不自动上屏。需要分别操作的数学对象逐个给ID，不能用一个含糊“全部物体”代替。

视频页使用同一页面结构：video_ids引用实际计划视频，layout/visual_description明确独立播放区域、画幅和外围文字，native_objects登记`video-frame-<video_id>`等必需对象。播放前观察任务写入student_activity/teacher_question，片尾接话与前后页关联写planning/video-handoff.md。视频页计入pages.order和课件总页数，具体见[页面规范](../../math-courseware-pages/references/page-design.md#视频播放页)；不新增虚构媒体字段或把计划ID当成真实PPT对象。

实际图生成后补`image:{path,sha256}`，先核对实际图片再将它作为正式采用版。图片文件及当前页面记录的批准可以随整套图片确认一起登记，不重复要求相同用户意图。

## 确认与变更

从头整课在AGENTS/HANDOFF记录视频必做范围；视频方案与制作流程先于PPT逐页制作；共享图片资产在视频剧本/预览之后、导演之前准备，plan协同风格与封面参考。按[视频前置清单](video-integration.md#ppt开工前的视频方案检查)核对全部计划视频，实际确认绑定已写好的方案文件/哈希。全课总表记录检查结论、缺项及下一步；这些是Skill执行检查，现有CLI不会自动判定方案语义完整、是否有视频页或媒体可播放，不能把validate退出0当作前置通过。

草稿可直接写入；已经定稿的记录用`record-change`保留前版并分析影响。数字、故事与资产改变时追踪引用，纯调序更新导出和讲稿对应，不重做未改内容的图片。

确认JSON：

```json
{
  "targets": [{"path": "_state/math.json", "sha256": "实际文件SHA256"}],
  "decision": "approved",
  "user_evidence": "用户对该具体版本的真实确认原话及可取得的会话定位"
}
```

`record-approval --record FILE`校验哈希并写入`decisions.jsonl`。同一记录不重复写入。脚本不能鉴定聊天来源，调用者必须使用实际证据；不得复制示例作为批准。

可编辑路线须先按[editable强制询问节点](../../math-courseware-editable/SKILL.md)取得用户明确选择，再用现有确认记录保存路线、适用范围和真实原话，并在HANDOFF交接。页面图片采用不包含A/B选择；selection里的route仅是执行参数，不构成批准。缺选择时不得先生成路线交接、去字、拆层或回填，已确认带字图片课件导出和独立文稿可继续。

B路线固定覆盖当前`pages.json`全部页面：去字图完成、检查并确认后，selection按`pages.order`升序包含每个page_id恰好一次。导出完整PPTX时一页一张对应去字图，PPT/PDF总页数等于课件总页数，映射及图片哈希逐页核对。不能用少量页交接或图片目录替代完整PPT，也不能等待局部可画回传才生成余页。

变更JSON：`path`、`expected_sha256`、`replacement`（完整新记录）、`reason`、`user_evidence`。先执行`impact --change FILE`看影响，再用`record-change --change FILE`应用已授权修改。执行器自动递增revision并保留旧文件。不是只有最后修改时间最新就算已确认。

产物注册使用`state.register_artifact(project,id,path,dependencies,metadata)`：依赖填写实际使用的数学ID、页面ID及相关权威记录路径，metadata记录`source_versions`（路径到哈希）及审查状态。仅坐标改变不使故事和数学记录失效。不要在生成期间修改全局权威数据。

真实回传核对后直接整套回填；制作授权独立记录，不以单页样页采用或坐标批准作为前置。`editable-build`的authorization绑定真实用户指令、源文件和全部页ID；text-refill范围严格覆盖全页全文，图形粒度缺口单列，不能将文字成功混同全部图形验收。

## 命令接口

所有命令除doctor外均有`--project PATH`。JSON文件参数可用绝对路径，内容内的课件路径保持相对项目。

| 命令 | 参数 | 用途 |
|---|---|---|
| init | --title TEXT [--route builtin/openai_image_api] | 不覆盖已有项目 |
| status / validate | 无额外参数 | 读取进度/检查引用和哈希 |
| record-approval | --record FILE | 记录实际用户批准 |
| impact / record-change | --change FILE | 预览/应用授权变更 |
| render-prompts | 无额外参数 | 从页面数据展开五段提示词与可见文字 |
| image-prepare | --selection FILE | 派发任务，不生图 |
| image-run / image-resume | --batch FILE [--key-file FILE或--key-stdin] | Grsai执行/恢复 |
| image-register | --result FILE | 登记内置工具真实输出 |
| export-slides | 无额外参数 | 确认图片导出PPTX/PDF |
| canva-handoff | --selection FILE | A按授权页交接；B全页有序去字PPTX/PDF交接，不改正式带字页 |
| canva-import | --deck FILE --mapping FILE | 原样保存可画回传并列出对象 |
| editable-build | --plan FILE | 校验正确文案后处理PPTX副本 |
| export-documents | 无额外参数 | 三种文稿DOCX/PDF |
| collect | 无额外参数 | 复制当前有效课件产物；不包含视频，且依赖锁定页面 |

`validate`检查通过不表示教学、视觉和WPS都通过。原材料图文冲突、生成画面计数、课程推理与实际投屏仍由Codex/教师检查。

视频资料/成片可以登记为通用artifacts，但validate只查登记文件哈希，不会验证媒体内容或其全部来源版本；视频模块另外比较来源哈希并查看实际输出。控制器没有视频生成、配音、剪辑或视频打包命令，不能把image-run用于生成视频。

提示词交付依据`_state/prompt-exports.json`中的`source_versions`与`files:[{path,sha256}]`。render-prompts自动登记逐页提示词和可见文字稿；Codex完成assets下的资产提示词时，核对其确由当前资产/故事/数学记录生成，再将真实文件及哈希补入同一manifest。资产prompt_path默认指向assets内实际md/txt；kind=style_reference时也允许slides/covers内、与其已登记封面图片同目录的实际提示词，仍须核对原文件和清单哈希。不指向任意外部资料或密钥。源内容变化先修提示词再更新依据，不仅重写哈希来掩盖过期内容。
