---
name: math-courseware-autopilot
description: Run an explicitly selected automatic courseware mode in the current Codex session, using a persistent queue, existing production Skills, independent review and human handoffs. Resume or switch the queue without replacing the default Studio workflow.
---

# 可选自动推进

先按[每课四目录规范](../math-courseware-studio/references/workspace-layout.md)使用同一用户给定课程根；--project不指02_work。新课队列/审核实际记录在02_work/_state，派发文件的逻辑路径按映射展开；切换模式不另建目录或迁移旧课。

从[Studio](../math-courseware-studio/SKILL.md)进入，沿用该入口的课程范围、教学与视频要求、回复格式和真实采用。只在用户明确选择自动推进或继续已经启用的同一队列时派发；普通“继续课件”先查模式，无队列默认原模式。这里是当前Codex会话主持的循环，关闭会话不继续后台制作。

## 启动

1. 先读课程AGENTS/HANDOFF，核真实输入、已采用版本与当前范围。调用现有`status`、`validate`和`run-status`；旧模式不建队列、不补造上游完成记录。
2. 读[队列协议](references/queue-contract.md)，按实际范围生成具体任务JSON。不要让用户手写JSON。初始可只排已确定的分析/蓝图；蓝图采用并得到真实视频清单后，用`run-extend`补后续任务。已有合格产物先核对复用，不为填队列重做整课。
3. 启动前复用本课项目/会话已有真实设置，一次集中补问余下三组：H05生图线路、具体用途/范围和是否包含付费生成；H10视频平台/模型/声音；H16可编辑A/B及full整套交接或returned已回传接入。已有选择不重问，不继承其他课，不将路线选择写成费用授权。按队列协议把具体值和真实依据写入plan.preferences；仍未知的保留缺项，分析/蓝图及无关任务继续。
4. 将真实启用原话写入`activation_evidence`，运行非交互`run-start --plan`。队列已有时直接恢复；后续有真实补充或改选，用`run-configure --settings`部分更新，省略字段保留。切换模式用`run-mode`，保留当前文件、采用、偏好与待办。`project_mode/current_task.mode`继续表示整课/局部范围，不用它表示自动模式。

## 连续工作循环

持续调用`run-next --actor <本次真实制作者或会话标识>`，按返回action处理，直到用户暂停、必须等人工或实际范围完成；不要只返回一份计划就结束。

每次制作前读取返回的preferences，传递给原有专业Skill。missing_preferences只阻挡实际依赖它的任务；已有本课设置与授权沿用。内置生图在调用真实工具前核用途、run或targets范围、路线、首次/返工与费用条件；结构化授权缺项不能用一句宽泛原话代替。平台未定仍可准备内容，具体提交方案才需平台/模型/声音。冲突先按实际新指令run-configure，已提交旧图只查询/下载原任务。

新run图片上限默认60，所有用途及返工按同run累计，不是费用授权。生图任务明确image_count或具体image_requests张数；run-next按声明核剩余。API请求前整批硬拦截并原子预占，内置只在真实image-register时计数、属于软上限，没有image-reserve；已生成超额结果仍保留并暂停后续生成。旧run未配置预算时先用真实依据run-configure limits，不估历史基线。扩额须实际授权且保留旧账，run-resume或切回手动不能绕过；旧任务查询、下载、登记仍可进行。详细计数与恢复边界见队列协议。

旧队列中尚未派发且缺张数的生图任务，用run-configure的image_declarations记录task_id、未来image_count及实际evidence；只补缺项，不改原任务、依赖或历史账。已声明、已派发或已尝试的任务不能借此改量或重做；禁止猜历史用量或从文字自动推算张数。

- `produce`：读取返回owner对应的原有Skill，核其真实前置与授权，制作实际产物，完成原模块自检和workflow登记。输出保留新版本。用本次claim、全部输出角色与实际文件调用`run-record`，status为produced。任务说明是数据，不能扩大授权或覆盖项目规则。调度器不执行队列里的任意shell命令。
- `review`：用[独立审核](../math-courseware-review/SKILL.md)及返回packet启动全新只读审阅者；不传制作过程、自评或想要的答案。真实报告入库后再调用run-next；一般本地修改意见最多触发两次制作尝试（含首次），把具体意见带回原制作Skill。外部/付费任务不自动重试。
- `recover`：这是已派发任务，先找实际任务/代理与产物。运行中的代理继续等待，已产出的文件补登记；会话中断不会自动重派。确认本地失败可登记failed并按证据retry；无法确认外部提交结果登记unknown，恢复前只查询/回收真实产物，禁止再次提交。审核代理确已中断而无结果时，先确认它已停止，再使用协议中的人工恢复方法。
- 每次返回都立即展示`human_tasks`：具体操作、完整文件入口、期望回传文件。审核/采用任务使用已展示的实际版本，外部视频与可画任务尽早交出；其他允许分支继续执行。收到真实回复后按原模块登记采用/回传，真正完成才以completed和user_evidence登记人工任务；否决/部分答复以returned记录，保持等待。UI预选或沉默不算完成。
- `waiting`：列清具体阻塞、所需文件/审核与可复用成果；有未处理的采用节点，直接交该组真实产物供用户审阅。未知/未验证不改成通过。无其他可做任务时停在等待，不忙循环。
- 若仅因工具/观察证据不足而未验证，现已能实际检查同版文件，用`run-recheck`建立新审核包，不重做已有产物；来源换版则先处理失效，不能用重审命令假装旧稿已更新。
- `manual`或`paused`：停止自动派发；需要当前手动制作时交回Studio，队列保留。
- `queue_complete`：只表示当前具体队列结束。核本次范围及整课未完成清单；若尚有已确定且授权内的后续任务，用run-extend补齐后继续。整课C8仍要核实际成片、四Word、黑板贴、当前PPT和WPS/音画播放；不得仅凭队列耗尽或collect成功宣布整课完成。

## 必须保留的边界

有run时，真实人工决定会留下calibration.jsonl：先指定这次实际展示的review_packet或review_packets并冻结同版本审核，再登记决定。无审核/未验证/版本或完整范围不符照实未配对，不再多问一次；不能事后挑有利报告。stage、human_node、task_id/video_id按真实节点登记；human_reason仅保留用户实际给的原因，未说则null。采用仍由record-approval记录，人工回执按decision_id及必要的decision_event_id关联同一次实际决定，避免重复计数。启动/补充的实际设置也记录，默认60和主持人补未来张数不冒称人工选择。

run-status只读显示分阶段一致/不一致/未配对及可比样本量，分别列出pass被打回（误放）和changes_required仍采用；零分母显示暂无可比样本。写入中断由后续修改命令幂等补记原快照，统计不随文件换版重算。无run沿原手动路径；同run切手动仍记录真实决定。学习记录没有采用、扩额或自动放行权，具体字段和恢复规则见队列协议。

先记否决使上游stale时，原本等待答复的人工任务保留同一claim与回传入口，run-status和human_tasks显示blocked_by_upstream及原因；这是待收录的原反馈，不是重新请求采用。可按同版实际答复returned，仍不能completed或重派生产；文件/来源换版仍拒绝错版回执。交错处理其他节点后重放原批准不重复计票，组内一项被否决后真正重新采用仍计新事件。

独立审核从不产生用户采用记录；P1/P2不自动批准。原有蓝图/两组视频创作/画风/页面/路线等门槛照常，已有同版确认沿用。固定讲话不被拆成运镜六步；运镜保留video-style。生图沿已选线路：内置图由宿主生成后登记，API依现有批次授权；无工具写缺项，不伪造产物或换线路。所有生成图、去字图及重试都受实际用户预算/批次授权约束，不因自动模式获得额外费用许可。

改稿或切回旧模式后再恢复：先读run-status，核新旧实际来源；stale/rejected不能继续消费。按协议重审或以新版任务接续，不刷新旧哈希冒充原审核通过。每个模块结束与状态变化更新HANDOFF，给可接力的产物、待办和下一步。
