# 项目协议

仅显式 `grouped_creative_v1` 的full_course自动run，另按[D1记录协议](../../math-courseware-autopilot/references/grouped-creative-review.md)保存两组实际文件、来源与同一次采用identity/decision事件链接；权威assets必须包含在真实采用范围。原preparation/pages/shared-assets批准与依赖绑定保留；C6登记实际editable.files.pptx/limitations，H23报告按同版完整清单实核。没有该策略的原项目记录不迁移。

## 执行与目录

先读[每课四目录规范](workspace-layout.md)。新课根目录由用户开工提供，Skill初始化显式使用`--layout four-folders`；根保留AGENTS/HANDOFF，原始资料、过程文件、教学产品、笔记分别归01_source/02_work/03_final/04_notes。旧课保留旧结构。以下表格、JSON和专业参考中的inputs/planning/_state等均为逻辑路径，实际文件操作与点击链接按四目录映射展开；所有命令的--project仍是课程根。

整个十二Skill源码集合放在同一父目录，专业Skill通过相邻`math-courseware-studio/scripts/courseware.py`定位执行器。路径相对于当前课件项目，调用时传项目绝对路径；包内不写某台机器的Python、字体或用户名路径。

先用运行时发现工具找到已有Python及文档库，执行`courseware.py doctor`。普通用户以自然语言工作，JSON与命令由Codex维护。

先读[共用流程](workflow.md)，将项目长期目标与本次任务范围分别记录。课程用`_state/workflow.json`；独立视频允许原manifest.workflow及普通素材目录，无需初始化整课。可靠外部成果按核验输入接入，不补造上游制作记录。

项目初始化先写AGENTS.md和HANDOFF.md，再创建：

| 目录（逻辑路径） | 内容 |
|---|---|
| inputs | 原课件、教材及补充材料的原样副本 |
| planning | 教学分析、数学核查、故事、页面方案、可见文字稿 |
| assets/characters、scenes、props | 实际设定图、版本与提示词 |
| assets/blackboard-plan-vNNN、blackboard-vNNN | 按[黑板贴规范](../../math-courseware-documents/references/blackboard-stickers.md)先存来源/设计/spec，再存全新版本的透明素材、整板、PPT/PDF及检查；内部版本不覆盖，对外交付用中文普通文件夹 |
| slides | 页面提示词、图及版本化图片课件 |
| editable/handoff、returned、output | 可画交接、原始回传副本、修改结果 |
| documents | 三类教师文稿的版本化输出；worksheet-vNNN保存[学生学习单](../../math-courseware-documents/references/student-worksheet.md)来源/任务对应、源稿、实际DOCX、分页检查和manifest，旧版本不覆盖 |
| _state | 权威记录、确认、变更、任务、坐标、文稿源和检查 |
| deliveries | 控制器收集的副本与清单；新课实际为02_work/deliveries暂存，教学最终产品与笔记另按清单分别交03_final、04_notes |

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

从头整课先完成可见原课/需求分析，再形成并实际采用`planning/whole-course-plan.md`或其当前版本，随后按蓝图的全部视频清单创作准备。故事方向选择不等于接受教学活动、页数或视频数量。共享图片资产在剧本/预览之后、导演之前准备，plan协同四张封面候选及风格选择。按[视频前置清单](video-integration.md#ppt开工前的视频方案检查)核全部计划视频，再交PPT逐页制作。

流程索引只引用实际产物、来源版本、内部核查和必要采用依据，不复制故事/数学正文；生产完成、内部检查、用户采用各自记录。专业步骤开始前运行只读`workflow-check`，结束后登记真实成果并检查下一动作的前置；返回允许执行不能证明当前动作已完成、内容质量或用户已采用。`status`展示流程与记录状态，`validate`仍检查数据/引用；教学语义、真实图片、WPS显示与播放由实际检查补充。

缺流程索引的旧项目保持未分类，先按真实历史与文件建立适用范围，已有效内容继续复用。独立模块/局部维护按`current_task.mode`及实际所选范围检查；项目`project_mode`不随当前模块改变。外部PPT回填只建立必要页序/文字/来源与对象记录，不为接口批准空story/math；没执行的上游保持未执行。

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

可编辑路线按[editable路线节点](../../math-courseware-editable/SKILL.md)核用户明确方向，再保存路线、适用范围与真实原话并在HANDOFF交接。明确无字分层PPT直接回填已给出B后半段方向；明确带字PPT文字校正已给出A后半段方向。同范围选择沿用，缺选择才询问。页面采用不包含路线选择，selection.route也只是执行参数；等待选择时带字图片导出和独立文稿可继续。

从本套带字图片开始的B交接固定覆盖当前`pages.json`全部页面：去字图完成、检查并确认后，selection按`pages.order`升序包含每个page_id恰好一次。导出完整PPTX时一页一张对应去字图，PPT/PDF总页数等于课件总页数，映射及图片哈希逐页核对。不能用少量页交接或图片目录替代完整PPT。外部已拆层PPT接回填后半段，不要求补造此前的去字交接。

变更JSON：`path`、`expected_sha256`、`replacement`（完整新记录）、`reason`、`user_evidence`。先执行`impact --change FILE`看影响，再用`record-change --change FILE`应用已授权修改。执行器自动递增revision并保留旧文件。不是只有最后修改时间最新就算已确认。

产物注册使用`state.register_artifact(project,id,path,dependencies,metadata)`：依赖填写实际使用的数学ID、页面ID及相关权威记录路径，metadata记录`source_versions`（路径到哈希）及审查状态。仅坐标改变不使故事和数学记录失效。不要在生成期间修改全局权威数据。

真实回传核对后直接整套回填；制作授权独立记录，不以单页样页采用或坐标批准作为前置。`editable-build`的authorization绑定真实用户指令、源文件和全部页ID；text-refill范围严格覆盖全页全文，图形粒度缺口单列，不能将文字成功混同全部图形验收。

## 命令接口

所有命令除doctor外均有`--project PATH`。JSON文件参数可用绝对路径，内容内的课件路径保持相对项目。

| 命令 | 参数 | 用途 |
|---|---|---|
| init | --title TEXT --layout four-folders [--route builtin/openai_image_api] | 新课四目录；不覆盖/迁移已有项目，省略layout仅保留旧脚本兼容 |
| status / validate | 无额外参数 | 读取进度/检查引用和哈希 |
| workflow-check | --step STEP [--video-id ID] | 只读检查本次范围的实际依赖，返回允许项、缺失/过期产物及可继续步骤；步骤名见共用流程 |
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

## 自动运行启动偏好

可选run的preferences保存本课image/video/editable设置及真实依据，详见[队列协议](../../math-courseware-autopilot/references/queue-contract.md)。run-configure接受同形部分JSON；run-status只读返回有效值、缺项与冲突。不创建第二份课程或采用记录。共享读取先用有效run偏好，缺项回退project.image_route和有user_evidence的workflow.route_choice；后续规范记录改选与run相冲突时须显式协调。模式切换不清空偏好，未提交工作用新选择，已提交任务保持原线路。

run.json的limits.max_images默认60；image_budget保存记账起点、旧用量是否未知及按实际job/input累计的API尝试/内置成功登记。run-configure接受limits:{max_images,evidence}并保留历史账；run-status只读显示image_budget_status。旧run未配置不能开始新生成，不推算基线；API预占在共享锁内，内置为登记后软计数。回收旧任务不受新增额度拦截，无run不创建预算或自动队列。

旧待办缺未来生图数量时，run-configure接受image_declarations:[{task_id,image_count,evidence}]。仅从未派发/尝试且无既有声明的pending任务可补；声明另存task.image_declaration，原spec、依赖及计划身份不改。有效派发任务带补充后的image_count，授权、额度和外部重试门槛共用它；不修改旧图片账或接受任务内容重写。

## 人工决定与独立审核校准

有active run时，record-approval仍按真实targets/SHA256和user_evidence写采用或否决；可附stage/human_node/task_id/video_id、实际human_reason或null，以及本次实际展示的review_packet或review_packets。只核指定报告，必须同版本、同来源且完整覆盖决定的产物整组；无审核、未验证、范围或版本不符均未配对，不新增等待。先在共享锁内冻结审核快照，再写人工决定，避免否决使当时有效报告丢失。

`decisions.jsonl`条目的calibration_event或run的保留revision先保存原快照，再追加本run的`calibration.jsonl`。新课物理位置为`02_work/_state/automation/runs/<run-id>/calibration.jsonl`，旧课沿原布局；哈希清单保持逻辑路径。恢复只补缺失event_id，run-status只读显示缺口与分阶段统计，不按新文件或晚到报告改写历史。

事件ID表示一次实际发生；旧decision_id可能在approve→reject→approve时复用，不能当唯一发生次数。event_seq在共享锁内按全部持久快照最大序号递增（包括run指针中断前已落盘的revision），恢复沿用原序号；时间戳只展示，不用时钟先后判断旧链接是否失效。人工回执用decision_id及必要的decision_event_id关联同一次同版决定；反向顺序可显式human_event_id关联首次实际回执。后续改口保留新事件；同版、同实际意见/原话仅补审核引用、阶段节点或理由注释时，保留原事件及原配对状态。显式来源链接先验证，不能借补注吞掉旧/错链接。详见[队列协议](../../math-courseware-autopilot/references/queue-contract.md#human-calibration-records)。

有run时，期间处理无关文件或同意见的组内子项不使原批准重放变成新票；任一同版组员被否决、或真实人工回执要求修改后重新采用，保留新发生记录。上游因否决失效时，已等待的人工任务保留原claim接收returned，并明确显示上游阻塞；不能据此完成任务、重派生产或接受换版回执。

calibration日志半行/UTF-8断字只在原字节确为下一缺失事件的序列化前缀时追加缺失后缀，完整JSON缺换行只补行终止；不删除、截断或覆盖旧字节。未知尾部/中间损坏明确阻塞写恢复。只读status通过log_complete、incomplete_tail和log_issues说明不完整统计，不因日志尾部中断而崩溃，也不自动修复。

一致率只算可比二元样本，零分母为null/暂无可比样本；pass被打回（误放）及changes_required仍采用分别统计。配置/操作/部分采用保留原话但不强算一致率；真实配置的version_hash等于settings_hash，默认60与主持人补张数不伪造人工选择。无run走原手动路径，同run切手动仍记真实事件。reviewer没有采用、扩额或阈值放行权。
