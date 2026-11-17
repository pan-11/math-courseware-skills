# 完整课堂动画计划

用户明确启用 `课堂动画试用V1` 时，先按[试用V1入口](classroom-trial-v1.md)接入回填稿、准备答案组件及全页教学合同，并使用其检查/构建/登记/收集命令。有指定终稿时，目标是初态、每击内容/顺序/同步关系/效果及最终状态相符，不是只增加或凑齐点击数；测试仅用回填稿和终稿的独立副本。本文继续提供统一教学计划及基础动画接口。未给口令的新任务仍按本文已有的按需范围执行，不自动切换交付版本。

仅在用户明确要求教学动画、逐步讲解或完整课堂点击设计的范围使用。本次已有同范围指令直接沿用，不要求用户再逐页指定对象、次数和效果。普通回填仍执行[忠实复原＋原位答案](refill-modes.md)；明确纯复原、保留空白或学生版时按真实要求处理。`classroom`是独立动画计划模式，不新增或替代`refill_mode`。已采用课件不会因规则更新自动重做。

AI读取本课实际教学设计、页稿、前后页关系及当前制作指令，完成教学判断；确定性运行代码负责检查对象、状态和时序并生成PPT，不把关键词分类器称为教学理解。所有计划和结果沿课程现有目录保存；保留原件、旧版及未通过证据。

## 从课堂任务规划九类模式

先确定本页学生要观察、比较、操作、推理、计算还是表达，再选可组合的策略。下表是候选模式，不是每页必选一种的模板，不设统一点击数，也不要求每页都有动画。

| 页面任务 | 初始画面与通常顺序 | 逻辑分组 |
|---|---|---|
| 观察与提问 | 给足观察材料和当前任务；聚焦位置→证据→解释 | 标记、对应图形与短标签配对 |
| 概念建立 | 具体材料可见；操作/观察证据→关系→名称或定义 | 一条完整意思一组，保留学生发现的机会 |
| 图形/数量推导 | 已知图形和当前问题可见；过程→对应数量→关系→公式 | 图形和对应标记同步，推理步骤分别停顿 |
| 规则和结构解读 | 先看完整数、编码或表格；定位→字段含义→完整读法→归纳 | 分段及解释配对，可同次短接续 |
| 原位填空 | 题干、空位与必要条件可见；逐个逻辑答案→必要理由 | 分数、完整编码、结果及单位通常整体出现 |
| 例题与多步应用 | 保留题目和独立思考机会；思路→列式→计算→答案→方法 | 同一步的结果与单位同步，不同推理分开 |
| 比较与辨错 | 可比对象尽量同时呈现；差异→判断→依据 | 同一差异两端同步强调，降低来回记忆负担 |
| 操作过程与状态切换 | 起始状态清楚；动作→观察结果→数学解释 | 必要动作同次自动接续，旧状态和临时探针及时退出 |
| 复习、操作指令、比较总览 | 根据回忆任务分模块揭示，或整页静态 | 知识组完整，操作时要反复查看的指令保持可见 |

每次点击必须对应一次有意义的课堂停顿，写清下一次点击前学生要看、算、说或做什么。附属箭头、标签、单位、底板若没有独立任务，与主体同步或在同次点击内自动接续；不能仅因它们是独立对象就增加点击。

上述分组是候选，不覆盖用户指定终稿的实际安排。V1逐项核对终稿，直条/数字、箭头/步骤、多个知识点是否分击不能先套同次模板；已有回填稿初显的讲解也须纳入管理，按目标改为后显。没有终稿时由AI把教学内容拆成可停顿的部分；保留静态须有本页活动依据，不允许大量讲解因未纳入计划而默认留在首屏。背景和装饰无需为凑次数加动画。

初始画面应足以开始当前任务。背景、标题和角色通常常显；题目、条件和图示按进入顺序安排，不强制所有题干初显，也不凭“正文”“答案”等角色自动隐藏。后续情节、待发现规律和解答按教学需要后显。

默认按数学含义分组：一个分数的分子/横线/分母、完整编码、结果及必要单位作为完整逻辑单元。分数和编码用`logical_id`标识所属数学整体；普通答案的同一`logical_id`不拆成多个单元。教分数写法时可按分数线→分母→分子分步，所有组件保留同一`logical_id`，各自标为`purpose: notation_instruction`并在`objective`写明真实教学目标；分析编码结构时同样依据目标分段。一个文本框的多条完整特征可按真实段落揭示；同一题的独立空可分别作答。不能按对象数、组名或题号机械确定粒度。

仍参与推理的内容累计保留。已显示证据需要强调时使用原对象；问号、旧图或临时标记完成任务后退出。互斥状态的退出与进入绑定同一次点击，避免把旧新状态无限叠加。原位填空延续原空位、题干及清晰区分的答案色，不加额外白底框。

## 页稿草案与实际对象绑定

逐页稿阶段先记录教学目标、学生动作、初显理由、每次点击及停顿理由、同步/接续关系、最终保留状态和需要独立控制的对象；放在现有教学/页面记录中，不把内部计划写进生图文字。完整结果预览与课堂顺序分别保留；需要分开进入、退出、标记或运动的图形提前登记`native_objects`，沿原A/B路线准备素材与拆层。

可编辑文字、图形和页序确定后，再运行`animation-inspect`读实际PPT。将草案绑定到1开始的实际页序、`shape_id`、真实组或0开始的文本段落；对象名称仅辅助辨认。核对象内容、图示位置、图层及媒体依赖；段落目标的`expected_text`匹配该段完整文字，整框目标匹配全部文字（多段以换行连接），非文字/整组目标用`null`。不能凭对象名称或历史页码猜目标。

完整计划可以操作已真实存在的对象；本阶段不替代回填或拆层。目标仍烧在背景图里、缺少独立对象或正确文字时，报告具体页和对象缺口，沿本课已授权路线补齐后再绑定。不要用新增白框遮挡、整页图片或虚构ID冒充原生动画目标。

先查原主时间线、媒体/交互动画及已采用顺序。相同目标、祖先/子对象、整框/段落相交都算冲突，不能重复叠加或整页清空。完整计划已覆盖的答案不再另跑一次`editable-answers`；已有答案动画则作为真实既有时序检查。仅当目标无冲突且教学顺序合适时，才能用`append_after_existing`并写明理由，把新步骤接在原序列之后。需要重编既有教学步骤时可显式使用下述 `replace_managed`，逐组核清可替换范围；不能安全处理时明确待办，不改用户原件。

## 计划字段与执行接口

模块为`runtime.classroom_animation`：`inspect(source_path)`读取对象、段落和时间线；`check(project, plan)`只检查；`build(project, plan)`创建独立输出与不可覆盖的计划/manifest；`validate_final(project, manifest_ref)`从绑定计划和源文件重新核验。可选`snapshot(project, manifest_ref, output, stage='final')`创建另存的静态状态副本，支持`initial`/`final`，范围限制见下文。控制器位于`math-courseware-studio/scripts/courseware.py`：

```text
python -X utf8 -B <controller> animation-inspect --project <project> --deck <project-relative-source.pptx>
python -X utf8 -B <controller> animation-check --project <project> --plan <plan.json>
python -X utf8 -B <controller> animation-build --project <project> --plan <plan.json>
python -X utf8 -B <controller> animation-validate --project <project> --manifest <project-relative-manifest.json>
python -X utf8 -B <controller> animation-snapshot --project <project> --manifest <project-relative-manifest.json> --output <new-project-relative-static.pptx> --stage final
```

`animation-snapshot`的`--stage`只选`initial`或`final`；静态副本尚须实际渲染检查，不是原生放映或截图证明。

独立动画任务只核实际授权范围、项目内输入和真实指令证据，不伪造蓝图、故事或整课采用。源PPT、教案/页稿依据和指令证据在`source_versions`绑定当前哈希；输出使用新的项目相对路径，不覆盖已有文件。源版本或输出发生变化时重新检查并另存版本，不能只改manifest的通过标记。

| 层级 | 必需字段及约束 |
|---|---|
| 顶层 | `schema_version: classroom_animation_v1`、`mode: classroom`、`source_deck`、`source_sha256`、`source_versions`、`output`、`request`、`mapping`、`pages`；可选 `teaching_contract: {path, sha256}`，新V1检查/构建必需且绑定到 `source_versions` |
| 指令 | `request.user_instruction`为真实本次指令；`request.evidence_ref`含`path`与`sha256`，同时绑定到`source_versions`。可选 `activation_ref: {path, sha256}` 只延续已核实的当前V1任务授权，具体记录与输入链规则见[试用入口](classroom-trial-v1.md#入口与生效范围) |
| 页码 | `mapping`将稳定页ID对应到实际1开始页序；`pages`精确覆盖映射，不遗漏无动画页或把局部请求冒充整课 |
| 页面 | `page_id`、`teaching_goal`、`student_action`、`basis: {path, locator}`、`initial_reason`、`units`、`steps`、`existing_policy`；零步骤需`static_reason`；追加既有主序列需`existing_reason`；受控替换需 `retime: {timing_sha256, effect_ids, reason}` |
| 逻辑单元 | `unit_id`、`role`、`kind`、`purpose`、布尔`initial_visible`、`targets`；`fraction/code`必需`logical_id`，其他kind可选；所有`notation_instruction`单元必需非空`objective`。每个target含整数`shape_id`及`expected_text`（无文字用`null`），可加0开始的`paragraph` |
| 一次点击 | `step_id`、非空`pause_reason`、非空`actions`；每步仅首动作`on_click`，其余`with_previous`或`after_previous` |
| 动作 | `unit_id`、`effect`、`trigger`；可填`duration_ms`、`delay_ms`；新V1的自动接续动作另须 `phase_start_ms`；效果专用字段见下表，明确重复入场可用受限 `replay: true` |

`role`取`context/question/evidence/answer/explanation/conclusion/marker`；`kind`取`text/fraction/code/diagram/group`；`purpose`取`answer/notation_instruction/observation/explanation`。实际组可整体绑定；段落目标只能指向真实文字段落，不得把整体组与子对象、整框与段落重复分给重叠单元。源文件本身禁用/隐藏的对象不能用计划冒充可播放目标；`initial_visible: false`指本次动画计划管理的初始后显状态。

`existing_policy`取 `reject_conflicts`、`append_after_existing` 或 `replace_managed`。后者必须使用本次 `animation-inspect` 得到的 `timing_sha256`，并在 `retime.effect_ids` 列出原生教学效果ID字符串、在 `reason` 说明重编原因。只选择完全由本计划单元接管的完整旧点击组；部分组、媒体命令、交互序列、未知行为或留下悬空时序引用均拒绝。仅移除已选效果及对应可安全处理的初态/构建记录，其余时序保留。保留的主序列动作仍在新步骤之前；若要交错，必须把所需完整教学组一并明确接管，不能假设可任意插队。

新V1的 `after_previous` 动作必须明确填写 `phase_start_ms`：这是本次点击后，其独立自动阶段容器开始的毫秒数，须不晚于动作实际开始时间；随后 `with_previous` 动作沿此阶段编排。有终稿时读取实际父阶段，不只把各级延时相加。WPS实播已发现“同阶段内延迟”与“独立后续阶段”即使总偏移相同也会执行不同。旧计划不含此字段时保留原编译布局以便历史产物验证，不能因此声称旧布局已通过本次实播。

动作遵守状态连续性：默认入口作用于当前隐藏单元，退出作用于当前可见单元，强调要求可见文字；不同步骤中同一单元可合法进入、退出、再进入。明确保留终稿重复入场时，可在该入口动作填布尔 `replay: true`，要求单元初始隐藏、已在本计划入场且当前可见；不能用于首入场、初始可见单元或非入口效果。编译保留第二次入口及独立构建组，不新增退出。默认重复仍报错；结构支持不证明重复入场的实际画面。检查应指出缺目标、无效段落、空点击、未声明重复、退出隐藏对象或不支持效果。终稿含重复入场时读完整原生行为并实播对应步骤，不能为通过状态检查擅自添加一次退出或假称效果等价。

| 效果 | 用途与范围 |
|---|---|
| `appear` / `fade` | 出现/淡入；普通答案优先出现，解释可用短淡入 |
| `wipe` | 定向擦入，`direction`为`left/right/up/down`，用于有方向意义的标记 |
| `peek` | 原生peek入场，必填 `direction: left/right/up/down`；方向及画面需与目标实播核对 |
| `stretch` / `random_bars` | 原生伸展/随机线条入场；当前只支持 `orientation: horizontal` |
| `wheel` | 原生轮式入场；当前只支持 `spokes: 1`。辅助显示节点时长默认与主效果相同；原生依据明确不同，可设 `visibility_duration_ms`，取整数 `1..duration_ms`，仅用于轮式效果，不改变主效果时长。 |
| `disappear` / `fade_out` | 退出/淡出；与新状态进入安排在同次点击中 |
| `emphasize` | 可见文字的字号强调，默认`scale: 1.25`；不冒充任意图形变换 |

出现/消失默认1ms，其余默认500ms；`duration_ms`范围1—5000，`delay_ms`范围0—2000且默认0；强调`scale`须大于1且不超过2，擦入/peek必须给方向。只给所属效果支持的专用字段，不把水平或单辐实现解释成任意参数支持。时长与延迟应服务教学。`with_previous`随前动作同步开始，`after_previous`等待前动作及其延迟/时长后自动接续，不多消耗一次教师点击。同次关联仍需检查实际先后与画面，原生XML编译通过和默认时长均不等于已验证投屏节奏。

路径移动、折叠、旋转重合、复杂重排和水位变化属于专项过程，需要真实可控对象、起止位置、几何约束与专项实现/验证。本接口不支持这些动作时，保留具体未完成项；不替换成淡入后宣称已实现，也不把未完成过程标为已通过。

## 全页教学合同

新V1通过 `classroom-trial-check/build` 强制核验全页合同，基础 `animation-check/build` 只做通用计划编译，不能代替这道检查。合同先按指定终稿或实际教学依据制定，再与计划/候选独立核对；不是从一份漏项计划反抄一份相同JSON就算完成。合同文件引用及其 `source`、`basis` 引用均须绑定当前 `source_versions`。

| 层级 | 字段及约束 |
|---|---|
| 合同 | `schema_version: classroom_teaching_contract_v1`、`source: {path, sha256}`、`basis: {path, sha256}`、`mapping`、`pages`；source必须等于课堂计划实际输入，mapping完全一致，全部页恰好一次 |
| 每页 | `page_id`、`page_type`、`managed_units`、`retained_objects`、`expected_steps`；page_type取 `teaching/activity_static/media/cover/preserve_scope`，零步骤需非空 `static_reason`，普通teaching页不能用零步骤蒙混 |
| 管理单元 | `unit_id`、`initial_visible`、`targets`；目标格式同动画计划，逐项匹配实际对象/段落和文本，初显教学内容也明确管理 |
| 保留对象 | `category`、`reason`、`targets`；category取 `background/decoration/media/existing_animation/static_content/out_of_scope`。媒体/既有动画必须确有对应对象；原生教学文字不能登记成背景、装饰或媒体跳过 |
| 预期点击 | `expected_steps` 保存有序动作组，每动作含 `unit_id/effect/trigger` 和适用参数；与计划每击内容、顺序、同次关系、效果、时长/延迟逐项一致 |

管理与保留清单覆盖全部实际叶对象及非空文字段落，不能漏项或重复占有。`static_content` 只用于 `activity_static/cover/preserve_scope`，`out_of_scope` 只用于 `preserve_scope`；活动静态页和媒体页不声明教学点击。背景图里烧录的教学内容仍需人工识别与拆层判断，清单完整不证明图中文字已独立。范围保留和封面手动项如实说明，不扩大制作范围。

合同检查保证清单完整、声明初态和步骤一致；它不能证明声明本身正确、目标图片相同或WPS/PowerPoint实际效果一致。历史V1没有合同的记录保留原身份，不补记通过新合同。

## 分阶段核验与交付

1. **教学语义先核。**宿主实读依据并核数学、任务与信息依赖、初显能否开始学习、每次停顿是否必要、完整分数与写法拆分例外、开放题、互斥状态和上下页衔接。`check`的字段/对象通过不能代替这些判断；关键概念、推导、练习泄题和状态切换页纳入现有审阅，真实歧义集中说明，不增设逐页批准。
2. **再核XML与原生结构。**检查实际对象/段落绑定、全页覆盖、逻辑分组、每步单击及自动接续、进入退出状态、受控重排范围、其余主序列/视频交互和其他ZIP部件保留；用`validate_final`重算并核源、计划、manifest、输出身份。V1另核全页合同及候选与目标的独立差异，不接受仅填写ready标志或重算改坏PPT的哈希作为通过。
3. **静态画面单独检查。**`snapshot`只投影映射内含托管单元的页面，这些源页不能有既有时间线；其余页面原样保留并报告未处理范围，不模拟未知既有动画。含字号强调`emphasize`的最终态投影也须拒绝，不能猜继承字号；初始态不受该限制。输出是独立PPT副本，仍须实际渲染/导出检查，不把结构状态清单称为截图。记录页和所选状态；新旧状态互斥页仅保留该状态，不删除课堂源里的必要退出动作。需要中间状态或未覆盖页面时另记录具体导出与检查结果，不能用所有图层叠加的编辑视图冒充完成图。
4. **目标软件实播单独检查。**在实际WPS/PowerPoint对测试副本逐次播放，核初始画面、每次点击、同步/自动接续、具体效果、最后状态及媒体控制；有终稿时对其副本检查相同步骤，尤其重复入场、退出替换和专项运动。记录实际页/击/观察画面，只有点击计数或COM调用成功不能证明视觉效果。未获得当前文件实际播放证据则保持`playback: unverified`，明确剩余检查；不能用XML、静态图或旧版本播放替代。

构建及验证结果是`ready_for_review`候选，不自动选择为最终产品，也不写用户采用。只有实际检查过的维度可以称通过；缺对象、专项动作或播放证据分别登记，不将结构通过包装为与手调成品等效。首次扩展验证可用未参与规则提炼的新课概念、练习、比较/推导代表页，静态与播放结果分别保留。
