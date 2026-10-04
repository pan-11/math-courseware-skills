# D1：整课自动推进的两次创作采用与最终检查

本协议仅在新 run 明确选择 `review_policy: "grouped_creative_v1"`、保存实际 `review_policy_evidence`、自动模式且项目/当前任务均为 `full_course` 时生效。当前范围必须等于 run 的范围；真实范围改变先按原 `run-reconcile` 登记。旧 run 不静默升级，不新增迁移入口；无策略、无 run、切手动或 `selected_modules` 全沿原门槛。模式选择本身不是任何作品的采用。

沿用 [队列协议](queue-contract.md) 的既有命令、图片授权/计数、版本化文件与独立审核。新增的是分组范围，不是工作流步骤；没有 `creative-draft`。以下规则只在上述条件生效时替代专业入口内相应的小节点，其余专业制作与验收要求继续适用。

## 一次视频创作定调：H06＋H07＋H09

按当前采用蓝图的**全部视频清单**交一组可实际打开的材料：

- 每段运镜视频的完整剧本、逐字对白/声音和真实25格剧情预览；共同角色、场景、必要道具都已有本轮实图。预览不是正式导演板。
- 首次需要选风格时展示四张有实质区别的真实封面，清楚标出这整组采用会选中的具体方向及对应共享角色/场景/道具。方向在用户实际采用前只是待选提案；用户选另一方向时补齐相应真实资产、更新整组后再采用，不把未生成素材预先算采用。四张均展示、绑定来源，只将最终明确选中的一张放入采用 targets。已有有效母版直接复用，不重做四张。
- 每段固定讲话视频的实际彩色首帧、完整台词/声音、完整提示词及该片实际准备/课堂交接文件。同一连续任务内做好后一起展示，不加导演或黑白板，不单独再问首帧。
- 若全课都是固定讲话，本组同时展示并采用实际全课 `video-preparation` 汇总。若混有运镜，本组只含已经实际完成的讲话准备；全课汇总在第二组展示。

现有 `video-assets` 与 cover/asset 生图准备允许在此策略下先做本地待审候选。仍须蓝图实际采用、所有真实输入/hash/来源和否决核查；数学与故事教学核心的原采用不放宽。图片 job 的 `creative_candidate` 绑定当次 run、范围、蓝图及权威资产定义版本；API 请求前、内置结果首次登记时重新核对。已有提交/unknown仍按原查询、回收规则，不盲目重提。内置依然由宿主在调用前核授权和软额度；登记不是生成授权。

只有需要 canonical assets 尚未采用这一特例的新 job 才保存 `creative_candidate`；它独立约束执行，不进入实际媒体输入的 `input_digest`。原已采用输入的 pending/submitted/unknown job 按A原规则原字节复用，不因启用策略改标或要求新版本。候选所用文件后来仅被采用、字节不变时也复用原 job；保留其原候选上下文，pending 重复 prepare、提交及首次登记仍核原 run/scope/蓝图/来源，不能借复用跨范围执行。

## 一次导演方案与正式板采用：H08

第一组真实采用后，按当前**全部运镜视频**一次交导演双表、正式黑白故事板，同时展示由这些候选版实际形成的风格段落、完整提示词、逐片准备/课堂交接文件和全课 `video-preparation` 汇总。固定讲话不被强加导演板，也不重复制作已采用首组内容。

为避免“板采用→词/准备→又采用”的第三轮，原 `video-board`、`video-style`、`video-prompts` 可先制作这组本地待审候选；尚不能提交正式视频生成。`video-upload` 对运镜必须等第二组真实采用，对讲话必须等第一组真实采用。两组相互独立，审核 pass 不能替代任何一组的人工决定。

全课/逐片 preparation 的原 `approved=True` 检查、实际文件角色及依赖绑定全部保留：组采用 targets 直接覆盖当次已展示的真实文件，从而沿用采用。全课汇总不是未来授权。两组后不再出现隐藏的第三轮准备采用；补做或换版造成的新实际内容仍需按受影响组展示。

## 记录和宿主队列

在 `run-start` 计划显式保存 policy 与选择原话。只有上述策略可使用两种 `kind:human` 任务：

| review_group | step | 范围 |
|---|---|---|
| `video-creative` | `video-assets` | 当前全课视频＋真实共享视觉资产及适用准备 |
| `video-direction` | `video-board` | 当前全部运镜导演/板/词/准备＋全课汇总 |

组任务不填单个 `video_id`。`inputs`、`outputs` 仍是具体实际文件路径和唯一角色；返回 artifacts 必须逐一覆盖整组 targets，不能只返回一份“已通过”说明。可在产物齐备后 `run-extend` 加入本组具体任务。用实际 producer 依赖中的 packet，或 `review_packets` 指向实际保存的独立报告；派发前其合并 artifacts 必须覆盖每个整组 target 且审核通过。制作方自检不能充作独立报告。

分组与H23人工任务都继续执行原公共声明检查：显式 `requires_preferences`、图片数量/实际请求、授权与适用额度必须满足才派发。不为未声明的人工采用新增默认参数依赖；额度用尽仍可采用已完成的实际材料。

`run-next` 的 `human_tasks[].review_group` 给出当前 `identity`、全部 `targets`、`source_versions` 和真实 `video_ids`；宿主必须把这些文件实际展示。第一组的待选封面也必须展示，不能只复制 JSON 标记。准备齐备后即可派发，不要求这个待办先采用自己。

真实答复后，用既有 `record-approval` 保存原话、完整 targets 和原样 `review_group: <identity对象>`。identity 包含 `name/run_id/fingerprint`，由当前真实依赖得出；不能自己拼接。可附实际展示的 `review_packet(s)` 用于C校准。然后 `run-record` 的 completed/returned 回传包含同一 identity、同组 artifacts、原决定的 `decision_id` 与 `decision_event_id`；只有全组实际 approved 能 completed，拒绝用 returned 保持等待。两条记录链接同一事件，只计一票；旧泛化或逐项批准不能拼成新组采用。

每段 manifest 的 workflow.products 沿原文件/内部 review/source_versions 结构，补实际核查事实：`script.complete:true` 与实际全部 `asset_ids`；`voice.verbatim:true`；运镜 `preview.panel_count:25`；讲话 `first-frame.color:true`；正式板 `formal:true, black_white:true`；完整词 `prompts.complete:true`。这些是已核事实的索引，不替代打开文字/图片逐项检查。逐片 preparation 的角色仍为 script/voice/frame_plan/prompts/production/classroom，运镜再有 director/board_plan；源绑定该片全部当前 products 及蓝图。

shared-assets.files 必须包含本轮真实选中图、实际共享资产及权威 `_state/assets.json`；script.asset_ids 指到其中当前 canonical 资产，每个必要实际图均在 files 中。style_choice 沿原 existing/candidates 格式；未选封面仅在 candidates 中，不进 files/采用 targets。不能批准一个副本后另改权威 assets。权威记录、蓝图清单、路线、当前指针、相关成员/来源实质换版或成员被拒绝会失效；在同一 manifest 正常登记后续 products 不使首组自相失效。未受影响内容复用，不因此重做全部媒体。

成员收到后续否决或部分意见后，单独重新批准该成员不能恢复旧整组采用；须对当前完整组记录新的实际人工意见。失效按C的持久事件顺序判定，不依赖墙上时间或当前逐文件 approved 状态；同次整组意见重复回传仍只记一票。

## C6展示、H23实机验收

C6仍实际完成整套可编辑课件，展示真实 PPTX 和具体限制；在 `stages.editable.files` 保存 `pptx` 与 `limitations` 真实文件。本策略不另排 H19 人工任务，原代码本来也没有独立 H19 approved 门槛可删。A/B路线、全套去字H17、可画操作与回传H18照旧。

H23是 `kind:human, step:complete` 的最终实机任务。它在整套文件及前置采用齐备后展示 `final_checklist` 和 `input_versions`，此时可以还没有本次实机报告；只能说“待检查”。收到同版真实报告后，completed 和 workflow complete 仍完整执行原成片/播放/来源/可编辑/documents/delivery门槛。

同版 WPS/实际检查报告的 `checks` 逐项记录实际核查为 true，并由原 `inspection:actual|user_report`、basis和 source_versions绑定实际文件：

| key | 必须真正检查 |
|---|---|
| editable_text | 文字是否独立、可编辑，不能只有整页图片 |
| teaching_graphics | 必要教学图形是否独立对象及可操作 |
| video_regions_layers | 视频独立播放区、分层与遮挡 |
| fonts_wrapping_overlap | 字体、换行、溢出和遮挡 |
| all_pages_animations | 全部页面与需要的动画，不能只看封面 |
| all_video_playback_audio | 所有实际成片在最终课件中播放与听音 |
| interactive_worksheet_blackboard | 实际互动、学习单及黑板贴的课堂使用效果；无某类互动时具体说明范围，默认学习单/黑板贴照常交 |

source_versions覆盖当前 pages、editable、documents 中全部文件、全部最终视频以及 delivery.files 中实际交付成品；将实际学习单、黑板贴及本课选用互动入口/依赖放入文稿或交付的真实清单后逐项实查，不以三篇教师稿代替。delivery.files 的 wps/manifest 角色及其文件路径是本次检查报告/清单元数据，不进入待验实物输入，避免报告采用自己；其他交付文件在派发前须真实存在且版本匹配，完成时须被同版报告覆盖。结构/文件检查不能证明这些人机实测已经发生。每段final仍需实际media＋playback并绑定最终PPT。queue_complete一直不等于整课完成。

## 保持的节点和边界

H11/H12实际视频制作、回传与验收，H13正式逐页内容，H15整套图片，H17 B去字，H18可画，条件H20/H21/H22继续保留。H14依旧在C5正式逐页内容采用后做1—3页试样（默认最多5）；不得提前做正式 page-image，也不把视觉候选当逐页内容采用。D2只保留旧设计文档，没有实施前置试样。图片预算、真实费用授权和所有红线均不因合并而变化。
