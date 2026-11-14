# 完整课堂动画计划

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

初始画面应足以开始当前任务。背景、标题和角色通常常显；题目、条件和图示按进入顺序安排，不强制所有题干初显，也不凭“正文”“答案”等角色自动隐藏。后续情节、待发现规律和解答按教学需要后显。

默认按数学含义分组：一个分数的分子/横线/分母、完整编码、结果及必要单位作为完整逻辑单元。分数和编码用`logical_id`标识所属数学整体；普通答案的同一`logical_id`不拆成多个单元。教分数写法时可按分数线→分母→分子分步，所有组件保留同一`logical_id`，各自标为`purpose: notation_instruction`并在`objective`写明真实教学目标；分析编码结构时同样依据目标分段。一个文本框的多条完整特征可按真实段落揭示；同一题的独立空可分别作答。不能按对象数、组名或题号机械确定粒度。

仍参与推理的内容累计保留。已显示证据需要强调时使用原对象；问号、旧图或临时标记完成任务后退出。互斥状态的退出与进入绑定同一次点击，避免把旧新状态无限叠加。原位填空延续原空位、题干及清晰区分的答案色，不加额外白底框。

## 页稿草案与实际对象绑定

逐页稿阶段先记录教学目标、学生动作、初显理由、每次点击及停顿理由、同步/接续关系、最终保留状态和需要独立控制的对象；放在现有教学/页面记录中，不把内部计划写进生图文字。完整结果预览与课堂顺序分别保留；需要分开进入、退出、标记或运动的图形提前登记`native_objects`，沿原A/B路线准备素材与拆层。

可编辑文字、图形和页序确定后，再运行`animation-inspect`读实际PPT。将草案绑定到1开始的实际页序、`shape_id`、真实组或0开始的文本段落；对象名称仅辅助辨认。核对象内容、图示位置、图层及媒体依赖；段落目标的`expected_text`匹配该段完整文字，整框目标匹配全部文字（多段以换行连接），非文字/整组目标用`null`。不能凭对象名称或历史页码猜目标。

完整计划可以操作已真实存在的对象；本阶段不替代回填或拆层。目标仍烧在背景图里、缺少独立对象或正确文字时，报告具体页和对象缺口，沿本课已授权路线补齐后再绑定。不要用新增白框遮挡、整页图片或虚构ID冒充原生动画目标。

先查原主时间线、媒体/交互动画及已采用顺序。相同目标、祖先/子对象、整框/段落相交都算冲突，不能重复叠加或整页清空。完整计划已覆盖的答案不再另跑一次`editable-answers`；已有答案动画则作为真实既有时序检查。仅当目标无冲突且教学顺序合适时，才能用`append_after_existing`并写明理由，把新步骤接在原序列之后。不能安全保留时明确待办，不改用户原件。

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
| 顶层 | `schema_version: classroom_animation_v1`、`mode: classroom`、`source_deck`、`source_sha256`、`source_versions`、`output`、`request`、`mapping`、`pages` |
| 指令 | `request.user_instruction`为真实本次指令；`request.evidence_ref`含`path`与`sha256`，同时绑定到`source_versions` |
| 页码 | `mapping`将稳定页ID对应到实际1开始页序；`pages`精确覆盖映射，不遗漏无动画页或把局部请求冒充整课 |
| 页面 | `page_id`、`teaching_goal`、`student_action`、`basis: {path, locator}`、`initial_reason`、`units`、`steps`、`existing_policy`；零步骤需`static_reason`；追加既有主序列需`existing_reason` |
| 逻辑单元 | `unit_id`、`role`、`kind`、`purpose`、布尔`initial_visible`、`targets`；`fraction/code`必需`logical_id`，其他kind可选；所有`notation_instruction`单元必需非空`objective`。每个target含整数`shape_id`及`expected_text`（无文字用`null`），可加0开始的`paragraph` |
| 一次点击 | `step_id`、非空`pause_reason`、非空`actions`；每步仅首动作`on_click`，其余`with_previous`或`after_previous` |
| 动作 | `unit_id`、`effect`、`trigger`；可填`duration_ms`、`delay_ms`；擦入用`direction`，文字强调用`scale` |

`role`取`context/question/evidence/answer/explanation/conclusion/marker`；`kind`取`text/fraction/code/diagram/group`；`purpose`取`answer/notation_instruction/observation/explanation`。实际组可整体绑定；段落目标只能指向真实文字段落，不得把整体组与子对象、整框与段落重复分给重叠单元。源文件本身禁用/隐藏的对象不能用计划冒充可播放目标；`initial_visible: false`指本次动画计划管理的初始后显状态。

`existing_policy`只取`reject_conflicts`或`append_after_existing`。动作遵守状态连续性：入口只能作用于当前隐藏单元，退出只能作用于当前可见单元，强调要求可见文字；不同步骤中同一单元可合法进入、退出、再进入。检查应指出实际页/步骤的缺目标、无效段落、空点击、重复进入、退出隐藏对象或不支持效果。

| 效果 | 用途与范围 |
|---|---|
| `appear` / `fade` | 出现/淡入；普通答案优先出现，解释可用短淡入 |
| `wipe` | 定向擦入，`direction`为`left/right/up/down`，用于有方向意义的标记 |
| `disappear` / `fade_out` | 退出/淡出；与新状态进入安排在同次点击中 |
| `emphasize` | 可见文字的字号强调，默认`scale: 1.25`；不冒充任意图形变换 |

出现/消失默认1ms，其余默认500ms；`duration_ms`范围1—5000，`delay_ms`范围0—2000且默认0；强调`scale`须大于1且不超过2，擦入必须给方向。时长与延迟应服务教学。`with_previous`随前动作同步开始，`after_previous`等待前动作及其延迟/时长后自动接续，不多消耗一次教师点击。同次关联仍需检查实际先后与画面，默认时长不等于已验证投屏节奏。

路径移动、折叠、旋转重合、复杂重排和水位变化属于专项过程，需要真实可控对象、起止位置、几何约束与专项实现/验证。本接口不支持这些动作时，保留具体未完成项；不替换成淡入后宣称已实现，也不把未完成过程标为已通过。

## 分阶段核验与交付

1. **教学语义先核。**宿主实读依据并核数学、任务与信息依赖、初显能否开始学习、每次停顿是否必要、完整分数与写法拆分例外、开放题、互斥状态和上下页衔接。`check`的字段/对象通过不能代替这些判断；关键概念、推导、练习泄题和状态切换页纳入现有审阅，真实歧义集中说明，不增设逐页批准。
2. **再核XML与原生结构。**检查实际对象/段落绑定、逻辑分组、每步单击及自动接续、进入退出状态、原主序列/视频交互和其他ZIP部件保留；用`validate_final`重算并核源、计划、manifest、输出身份。不接受仅填写ready标志或重算改坏PPT的哈希作为通过。
3. **静态画面单独检查。**`snapshot`只投影映射内含托管单元的页面，这些源页不能有既有时间线；其余页面原样保留并报告未处理范围，不模拟未知既有动画。含字号强调`emphasize`的最终态投影也须拒绝，不能猜继承字号；初始态不受该限制。输出是独立PPT副本，仍须实际渲染/导出检查，不把结构状态清单称为截图。记录页和所选状态；新旧状态互斥页仅保留该状态，不删除课堂源里的必要退出动作。需要中间状态或未覆盖页面时另记录具体导出与检查结果，不能用所有图层叠加的编辑视图冒充完成图。
4. **目标软件实播单独检查。**在实际WPS/PowerPoint逐次播放核初始画面、每次点击、同步/自动接续、最后状态及媒体控制。未获得当前文件实际播放证据则保持`playback: unverified`，明确剩余检查；不能用XML、静态图或旧版本播放替代。

构建及验证结果是`ready_for_review`候选，不自动选择为最终产品，也不写用户采用。只有实际检查过的维度可以称通过；缺对象、专项动作或播放证据分别登记，不将结构通过包装为与手调成品等效。首次扩展验证可用未参与规则提炼的新课概念、练习、比较/推导代表页，静态与播放结果分别保留。
