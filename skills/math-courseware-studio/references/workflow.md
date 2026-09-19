# 整课流程与独立模块的共同检查

本文件是十二Skill共同遵循的有效顺序。专业创作要求仍在各自Skill。执行器只核查范围、实际文件、版本、已记录检查和采用，不能凭JSON证明教学质量、图片效果或WPS播放。

## 先记录两层范围

`project_mode`保存项目总目标，`current_task`保存这一次做什么。模式为`full_course`或`selected_modules`。首次明确意图就登记真实依据；不根据当前调用的Skill、文件夹名、已有部分页或换对话缩小范围。只有意图确实不清才问一次。

- 用别人课件作参考重做整课：项目是full_course。只有“先看一下”时，本次限定selected_modules/analyze，先交可见原课分析。
- 整课中说“现在做V001”是focus变化，整课目标及其他视频/PPT/文稿待办保留。
- 已有成品只改某页或回填文字，本次selected_modules；即使父项目是整课，也不以无关视频待办阻断已授权局部维护。
- 用户明确独立视频、文稿、页面或可编辑，只检查选定模块必需输入；没做过的上游不登记完成。

独立调用不要求用户填写JSON。AI保存输入副本、来源、核查和最小索引。独立视频不必初始化完整课程；原素材目录的`manifest.json.workflow`也可承载范围索引。

## 整课依赖与必需产物

| 阶段 | 必需交付 | 下一步条件 |
|---|---|---|
| C1 原课分析 | [可见分析模板](../../math-courseware-analyze/references/source-report-template.md)、数学核查、重要图示；原页数、逐页流程、好在哪里/如何借鉴、问题/如何优化、每段视频页码/内容/作用与实际读取证据 | 报告已真实核查；用户只要分析时到此交付 |
| C2 整课蓝图 | whole-course-plan，完整教学主线/活动/评价、故事数学、来源内容去向、课时/总页数/视频页预算、全部视频数量及功能 | 当前具体方案及共同核心真实采用；只选故事不等于蓝图采用 |
| C3 全部视频准备 | 覆盖蓝图全部V ID的具体剧本、声音、镜头/画面、提示词、制作流程、实际或待取得素材、课堂衔接 | 全部计划视频准备齐备并沿既有审阅采用；单个V完成不代表全课通过 |
| C4 逐页内容 | 每页教学任务、可见文字、数学、引用、播放区域和衔接；视频页计入已定总页数 | 当前逐页稿采用，页数/顺序及所有视频映射齐全 |
| C5 图片课件 | 规定格式提示词、带字试样、全套真实页面图和逐页核查、PPTX/PDF | 真实采用参考；沿原试样及整套审阅，不把工具成功当效果采用 |
| C6 可编辑 | 明确A/B、所需交接、真实回传、页序映射、整套文字回填及对象/显示检查 | 全流程B覆盖全部页面去字并有序汇成完整PPT；回传后直接全套回填 |
| C7 文稿 | 教师逐字稿、说课稿、教学设计，与采用课件及视频衔接一致 | 图片课件锁定后与C6并行；内容/页序变化只同步相关稿件 |
| C8 汇合 | 实际必做成片、实际PPT播放区域与回填/播放方式、WPS检查、最终文稿和交付清单 | 真正完成才声明整课完成；视频待到可交静态阶段稿 |

整课视频内部仍走剧本/25格预览→实际图片资产→导演双表→正式黑白板→固定风格→完整视频词。封面候选和共享风格/资产在视频第二步由plan与video-assets协同；已有采用资产复用。讲话简路是完整台词→实际彩色首帧→数字人交接，不生成不适用的导演表或黑白板。

C3具体内容完整且已列明缺图、取得办法及受影响工作时，可以记录“方案完整、实图待制作”继续符合条件的课件工作。不能缺剧本/声音/镜头而只列工序；不能说六步实物完成。页面生图仍需真实引用资产。C3通过后实际成片生产与PPT并行，不删成片待办。动画由用户手动设置。

## 每次执行怎样用检查

先读AGENTS/HANDOFF，核验当前输入和采用版本。现有`status/validate`继续负责记录和引用；`workflow-check`负责某个动作开始前的前置。它是只读检查，不自动批准或升级阶段。

```text
courseware.py workflow-check --project <当前项目绝对路径> --step blueprint
courseware.py workflow-check --project <当前项目绝对路径> --step video-director --video-id V001
courseware.py workflow-check --project <当前项目绝对路径> --step editable-build
```

| 动作step | 检查什么 |
|---|---|
| analysis | 实际任务范围；允许先分析，不要求先有分析成果 |
| blueprint | 已完成且可见的C1原课/需求分析 |
| video-script | 整课必须先有C2采用及目标视频ID；独立视频核粗情境等真实输入 |
| video-assets | 当前剧本；运镜新制作还需真实25格预览；讲话不需要25格 |
| video-director / video-board | 前者核剧本/声音/实际资产，后者核导演及实际资产 |
| video-style / video-prompts | 实际采用彩色参考/正式板或相应讲话材料；完整词引用当前版本 |
| video-upload | 核已有完整词及真实来源；只改上传映射不倒退补预览 |
| cover / asset | 整课蓝图或所选独立模块输入；仍遵守视频第二步协同及专业素材规范 |
| pages | 整课C1/C2及全部C3；独立页面核教学内容等输入 |
| page-image | 整课另查C4采用和共享资产；实际提示词/生图器继续核引用 |
| image-export | 图片采用及实际导出检查 |
| editable-handoff / editable-import / editable-build | 整课前置或外部输入；实际A/B选择；回填需真实PPT及准确文字 |
| documents | 整课已锁定图片或独立文稿的可靠来源 |
| collect | 只收集本次范围内有效阶段成果，不代表整课完成 |
| complete | 整课检查所有成片、播放及交付；独立任务仅能声明本次模块交付 |

结束当前步骤时，登记真实成果和核查，检查下一个动作的前置。例如分析完成后检查blueprint，逐页稿完成后检查page-image。再次运行analysis只核允许开始分析，不能用它证明分析成果完成。

检查失败返回具体`issues`，先处理相应缺口或继续无依赖的已授权分支。不要凭“继续”跨过未满足的前置，不要以技术检查代替必要创作采用。同版已有采用复用，不新增逐表/逐页确认。

新项目可以用`init --mode full_course --scope-evidence <真实制作意图>`；初次只分析时随后把current_task限定为analyze。未给模式的初始化保持unclassified；旧项目无索引仍可status/validate，但正式下游制作须按真实历史补范围和有效成果。无需重做有效旧稿，也不能把未知历史写为已完成。

## 流程索引：只保存依据，不另写一套课程内容

课程默认`_state/workflow.json`，独立视频也可用原manifest中的workflow。结构如下；文字是字段含义，不是可冒用的确认记录。

```json
{
  "schema_version": "1.0",
  "project_mode": "full_course",
  "scope_evidence": "实际用户整课制作要求及定位",
  "current_task": {
    "mode": "full_course", "modules": ["studio"],
    "evidence": "本次真实任务指令及定位", "focus": "blueprint"
  },
  "stages": {}, "inputs": {}, "videos": {},
  "route_choice": {"route": "B", "user_evidence": "实际明确B或无字回填的要求；未选时不要填此对象"}
}
```

`stages`使用analysis、blueprint、video-preparation、shared-assets、pages、images、editable、documents、delivery。空对象表示尚未登记，不表示已通过。`inputs`按所选模块存外部输入；`videos`按V ID存真实manifest的`{path,sha256}`。路径相对于当前工作项目，不越出项目引用源文件，先保存原字节副本。

每项成果/输入的共同依据格式：

```text
files: {职责名: {path: 实际相对文件路径, sha256: 实际哈希}, ...}
source_versions: {实际用过的源路径: 实际源哈希, ...}
review: {path: 实际内部核查JSON, sha256: 实际哈希}
approval: {path: 必要时指向真实用户采用记录JSON, sha256: 实际哈希}
```

内部核查JSON含`passed`及`source_versions`，后者覆盖本项files和实际使用来源；判断未做或不通过不能写true。具体检查与发现写notes/报告。采用记录沿现有`decision/user_evidence/targets:[{path,sha256}]`格式，复用已有decisions登记也可。没有当前文件的真实采用不能借用别页、别课或制作授权。不会自动采信`status: complete/not_applicable`。

整课`source_versions`必须绑定当前直接前置的files：蓝图绑定analysis；全课视频准备绑定蓝图及每段preparation；每段preparation绑定蓝图和已有当前视频products；pages绑定蓝图/全课视频准备；images绑定pages/shared-assets；editable和documents绑定pages/images；delivery绑定editable/documents。即使旧版本文件保留且哈希未变，切换当前前置后也不能继续把旧版本当作当前依据。重新核对确实未受影响的内容可以复用原采用，不需再次创作；受影响的内容先修订和审阅，不能只刷新哈希。

- **analysis**：files指向可见报告及核查文件；额外source_review为实际摘要JSON的文件引用，详见下一节。
- **blueprint**：完整蓝图文件及采用，额外`video_ids`（全课非空不重复清单）、`total_pages`（含视频页正整数）、`coverage`列`teaching_flow/activities/assessment/story_math/timing/page_budget/video_inventory/source_mapping`。这些字段是核查索引，正文仍必须具体完整。
- **video-preparation**：全课交接报告及采用，video_ids与蓝图完全一致。逐一引用videos下的实际manifest，不用一个小样代替其余视频。
- **pages**：files中的`pages`指向实际权威pages.json，须有采用；检查总页数、完整页序和全部video_ids，播放区域以native_objects中的`video-frame-<V ID>`明确登记。实物对象另由editable检查。
- **shared-assets**：files包含实际采用风格/资产图，style_choice记录kind为existing（复用既有采用图）或candidates（新选四封面）；selected为采用图的文件引用且包含在files中。新选四封面另记candidates四份真实且不同的图片引用，selected必须在其中。候选的实质设计差异由视觉检查，不因凑四个文件就通过。
- **images**：files覆盖权威pages.json每页的实际image引用，图像可解码、覆盖全部页；采用与核查绑定当前pages及shared-assets。图片导出仍生成PPTX/PDF并核对页序。
- **editable**：files中的pptx指向实际可读取且页数符合蓝图的PPTX；图层、文字和视觉效果另有真实逐页检查，不用“可打开”代替可编辑性验收。
- **documents**：files中的classroom-script、lesson-presentation、lesson-plan分别指向真实三文稿，可以是MD/DOCX/PDF；其余导出格式可另列，内容职责与完整性仍按文稿规范核查。
- **delivery**：files含manifest及wps，后者指向实际显示/播放检查JSON。该JSON含passed、inspection（actual或user_report）、basis（实际检查依据/用户回报及定位）、source_versions（覆盖当前交付所用的全部来源版本）；未实际检查不得填通过。

## 第一阶段的可见报告及source-review摘要

严格按[分析规范](../../math-courseware-analyze/references/analysis.md)和[可见模板](../../math-courseware-analyze/references/source-report-template.md)交付。用户先看到对原课的评价、流程和视频说明，再讨论改编。不能只留下内部JSON或仅给一个新故事。

source_review引用JSON至少包含：

| 字段 | 内容 |
|---|---|
| kind | uploaded_courseware；无原课才是requirements，后者写basis与limitations |
| page_count / page_map | 本次实际分析载体的总页数及逐页`{page,role}`；拿到原PPT时覆盖原全部页，隐藏页保留原号。仅有PDF/部分截图时绑定实际材料页序，另在报告标注原PPT总页数/隐藏页未知，不冒称完整原课 |
| overall_quality | 对原课制作质量的具体总体评价 |
| strengths / improvements | 具体原页/环节的优点与借鉴、问题与可执行优化；无问题时写核查范围和实际判断，不凑缺点 |
| teaching_flow | 从导入到结束的实际教学活动链，区分原课事实与改编建议 |
| video_inventory | items、complete、unique_count、occurrence_count、limitations |

每个视频项含video_id、pages（实际播放位置对应原页）、inspection、content、function、basis。inspection为viewed（明确实际看听范围）、partial、document_only或unavailable；content对未知内容明确未知，文稿推测注明依据。原片复用用同一video_id，不把重复关系拆成多个片；同页确有多个独立播放对象可在位置表逐一列出。

`complete`仅指可以确认全课视频身份及去重数量，不表示都已完整看听。true时unique_count与视频条目去重数一致；存在身份未知外链等则false，unique_count为null，并在limitations及可见报告给出已核实下限、未知范围。occurrence_count是已列位置总数，不把未核对象冒充实际播放位置。报告另区分候选位置，不能通过少登记来隐去未读部分。无视频且已完整核查时明确0；只有PDF无法证明原PPT没有视频。

摘要只是检查索引。实际看听、数学推理、优点/优化判断仍须有真实检查记录，不能填齐字段后自动宣称内容通过。

## 视频manifest的检查区

保留原manifest与旧字段，按需在其workflow中补当前成果引用。manifest的video_id沿用原编号；route为shots或talking（旧camera_movement_and_cut亦可识别）。

```text
workflow.products: {script/voice/preview/assets/director/storyboard/style/prompts/first-frame: 共同依据格式}
workflow.preparation: 共同依据格式，加missing_assets（有缺项时）
workflow.final: 共同依据格式
```

新运镜assets开始前核实际preview；director核实际资产图，不接受仅资产清单；正式板、首帧等须有真实可解码图片。已有导演/板的中途续作按当前必要依赖，不倒退补25格。两组创作采用和固定讲话审阅按视频入口执行。

已登记视频产品之间须绑定当前依赖：preview/voice绑定script，director绑定script/voice/assets，storyboard绑定director/assets，style绑定assets/storyboard；运镜prompts绑定script/voice/director/storyboard/style，讲话first-frame绑定script、prompts绑定script/first-frame。整课script还绑定当前蓝图。直接接入后期时只核实际提供的上游产品，不凭空补完整制作史；但已登记的当前产品不能被忽略。只修改上传表仍需复核完整词所引用的当前版本。导演与正式板成组审阅，同一采用记录targets同时覆盖两者的当前实际文件（或复用各自已有采用），不增加导演单独审批；仅把导演哈希写进内部核查不等于用户采用导演。

preparation.files必须含script、voice、frame_plan、prompts、production、classroom；运镜另含director、board_plan。classroom由课程模块写，视频专业模块不承担教师接话。missing_assets逐项含asset_id/reason/acquire/blocks，明确取得办法及影响，不能用笼统“以后再做”代替。平台未知可以如实写在操作包，不能宣称可直接提交。

final.files必须引用实际media和playback检查，另有真实采用。media核对受支持MP4/M4V/MOV、WebM/MKV或AVI的扩展名与容器标记；这仅能拒绝文字方案、错格式文件，不能证明编码完整、内容或声音正确。playback是实际检查JSON，含passed、inspection（actual或user_report）、basis和source_versions，绑定当前media与最终可编辑PPTX；只有图片/剧本/估时不能登记实际成片。完整看听及WPS实际播放仍须真实操作或明确用户回报。没有课程JSON的单视频，原manifest.workflow可直接放项目范围、inputs及products；检查当前V ID时读取同一manifest，无需自哈希。

## 外部输入与局部交付

| 所选模块 | inputs中的真实依据 |
|---|---|
| analyze/plan/pages/documents | 对应source（资料或已保存的真实用户需求），以及实际读取/核查；保留必要数学与页面索引 |
| editable-handoff | source为本次要交接的实际页面依据；已有明确A/B |
| editable-import | deck为实际回传PPTX，可以先检查结构 |
| editable-build | deck＋text（可靠逐页文字来源），实际核对页序/图层；带字版与提示词可作附加参考 |
| video或视频专业模块 | source为粗情境/相关真实输入；已做专业步骤复用当前manifest产品及版本 |

无字分层PPT明确要求回填，直接使用B后半段；带字分层PPT明确校正，使用A后半段。输入通过无需重做封面、去字、拆层等历史步骤，不批准空故事凑流程。外部文字仍需核准，模糊数学符号只集中补问真正缺项。独立模块不能因缺全课视频而被阻断。

已授权独立B去字背景返工时，repair沿editable-handoff的当前输入与B选择检查，不要求临时加入pages模块或补整课；实际修图仍核采用源图和提示词。单纯文字回填不因此自动扩大为重新生图。

上游实质更改沿impact/source_versions定位相关成果，未受影响内容复用；重新检查后才更新依据，不仅刷新哈希。旧异步任务已提交的可按原版本取回，新的未提交任务必须重新检查前置，旧图不得冒充新版采用。

交接写当前范围、实际成果、检查/采用、缺口及可执行下一步。完整总目标一直保留。只有complete检查及实际专业验收都满足，才说整课完成；普通collect、独立模块交付和静态阶段稿各按真实范围说明。
