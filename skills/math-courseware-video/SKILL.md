---
name: math-courseware-video
description: Use when starting, continuing, or revising a children's scenario video from a rough idea, script, or existing assets, including fixed-camera talking characters and videos with camera movement or cuts.
---

# 情景视频总入口

当前先按[完整故事文字先审](../math-courseware-video-writer/references/story-text-review.md)交全部具体故事，再做相关素材。新自动run可用grouped_creative_v2的文字→视觉→运镜导演组；旧v1历史不重写，同版全文采用复用，后续新生成仍核当前故事。手动/独立讲话也遵守文字先审；详见[分组协议](../math-courseware-autopilot/references/grouped-creative-review.md)。

先按[每课五目录规范](../math-courseware-studio/references/workspace-layout.md)读取用户已给定的课程根与实际布局。本入口的文件操作和交付链接使用映射后的实际路径，记录沿用逻辑路径；新课工作产物进入中间文件，已有课不自动迁移。

**每次用户可见回复**（含进度、等待、提问、恢复、交付和独立调用）先按[共同回复合同](../math-courseware-studio/references/reply-contract.md)填写唯一开头：真实课件/任务、步骤/状态，本步工作及产出、用户检查、用户操作、下一步；编号列项，无检查/操作写明无需，计划与完成分开，不新增批准节点。

把大致情境推进为有具体事件、吸引儿童观看的剧本、实际图片和可复制的视频提示词。总入口安排专业模块、版本和交付，用户不必逐个调用Skill或先写故事。课堂接话、教学活动和PPT插入由课程总入口安排，不作为本视频流程的写作要求。

先读当前项目AGENTS/HANDOFF、[共用流程](../math-courseware-studio/references/workflow.md)及[文件与恢复](references/handoff.md)，核对实际文件、来源版本和已有确认。整课推进须有具体教学蓝图及共同核心的真实采用，当前视频属于已定全课清单；只选故事或已有V001想法时先回plan补蓝图。进入视频模块不改变整课项目目标。明确的局部维护按本次current_task范围检查，保留全课待办。

独立视频可以直接开始，不要求PPT、教学蓝图、完整课程JSON或视频平台；范围索引可保存在原manifest.workflow。中途取得的剧本、实图、导演或板记录为核验输入，只补当前步骤真实缺口，不把未做上游登记为完成。已有课程共同故事、角色和数学仍是输入约束。

专业步骤开始前执行相邻studio的`courseware.py workflow-check --project <目录> --step <当前步骤> --video-id <视频ID>`；步骤名见下表。结束后记录实际产物、来源、内部核查和必要采用依据，再检查下一适用步骤；整课全部视频准备交PPT时查`pages`，独立交付查本次范围的`complete`。只改上传顺序/标签使用`video-upload`，不倒退重做编剧、导演或正式板。

运镜路线最终默认交付并上传本次片段对应的完整故事板，必要设定参考另列；逐格制作文件不能直接充当最终上传方案。已有单格时由AI完成必要合板并同步完整词/上传表，这属于当前材料缺口；清楚长板复用、限制分板及单镜情形按[整板上传规则](../math-courseware-video-prompts/references/prompt-assembly.md#整板上传默认必须执行)。固定讲话仍用实际彩色首帧。

## 先分两路

| 内容 | 执行路线 | 实际交付 |
|---|---|---|
| 一名角色全程讲话，固定机位，无运镜无切镜 | 先审完整文字，采用后连续做首帧、自检和提示词/操作包 | 一张实际首帧＋含全部台词的完整TXT与操作；无需导演组 |
| 有运镜、切镜、场景切换，或超出持续讲话的独立叙事动作 | 下列六步，从现有成果的缺口继续 | 实际黑白故事板、逐段视频词、必要角色/场景/道具图与完整声音稿 |

明确属于哪路就执行，不再让用户选一次。讲话路线不强制25格、导演八节、多镜头、故事板、分句配音或剪辑；三视图不能代替单画面首帧。数学准确性贯穿两路，不另设第三种视频路线。

讲话路线先完成当前全文文字审查，采用后按[图片＋完整提示词规范](../math-courseware-video-prompts/references/talking-packet.md)一次交付首帧、完整词和操作包；合格同版旧图复用，不因模块切换反复等批准。文字采用、视觉检查、真实成片分别记录。

## 运镜切镜路线：六步与五个专业Skill

| 步骤/检查名 | 专业入口 | 本步成果 |
|---|---|---|
| 1 完整故事文字／采用后剧情预览 / `video-script` | [writer 编剧](../math-courseware-video-writer/SKILL.md) | 完整script/voice/audio先在聊天审查采用，随后才制作实际25格预览和映射 |
| 2 图片资产 / `video-assets` | [assets 资产](../math-courseware-video-assets/SKILL.md) | 复用或实际生成角色三视图、场景多角度、必要道具；style.md初稿；整课plan协同封面与共享资产 |
| 3 导演分镜 / `video-director` | [director 导演](../math-courseware-video-director/SKILL.md) | 节拍、空间和专业运镜；director.md的八部分及静态/动态双表 |
| 4 黑白故事板 / `video-board` | [storyboard 制板](../math-courseware-video-storyboard/SKILL.md) | 按正式镜号生成并查看实图、提示词、映射和检查 |
| 5 固定风格文字 / `video-style` | 再由[assets](../math-courseware-video-assets/SKILL.md)完成 | 从本项目实际采用的彩色图提炼并冻结style.md段落 |
| 6 视频提示词 / `video-prompts` | [prompts 组装](../math-courseware-video-prompts/SKILL.md) | 逐段完整五部分提示词、实际上传映射及start-here.md |

顺序按依赖推进，不把六步变成六次询问。资产在剧本/预览之后、导演之前；预览可用已有或临时形象，不能先要求齐备全部三视图。导演确实需要新视角时返回资产补该项。25格是剧情关键状态，不是25秒或25个正式镜头；正式板格数由导演镜头决定，不固定13格。

只读取当前步骤所需专业规则。用户明确只讨论或只要文字时完成可审阅文字，不调用生图；要求制作素材且工具可用时由AI实际生图、查看、修正并保存，不能用提示词清单代替图片或默认交用户补图。沿用已选[生图线路](../math-courseware-studio/references/image-routing.md)，平台和配音未定不阻断已明确图片。

## 专业检查与审阅

- 写剧本前先把用户意图转换为“观众实际看到什么”。例如游乐园开场要写清孩子在玩哪些设施、动作和反应，环绕空园不能代替这些事件。
- 导演保留构图、景别、调度、节奏和运镜知识，每次运动有观看目标、起止与揭示内容；不为热闹堆技巧，也不把所有镜头简化成静态画面。
- 两路先完整故事文字审查；采用后运镜有视觉预览/共享资产组、导演/正式板完整包组，讲话直接首帧和完整词/操作包，无导演组。同版文字不重问；内容/图片/制作授权与采用分别记录，不能由AI自评替代。
- 已获本轮制作授权可生成供审阅的图，不逐表逐图重新申请。改变已定剧情、人物、数学或风格时列具体差异，依实际授权处理，不偷改共同事实。
- 图片实际生成、自检、用户采用、平台可提交、成片通过分别记录。缺工具时交明确的部分成果与AI待办，不宣称全部步骤已完成。

## 完成与恢复

每次完成视频提示词、参考图等素材准备后，按[主动聊天交付要求](../math-courseware-video-prompts/references/delivery-reply.md#每次完成后主动发到当前聊天)在当轮主动展示实图并发出全部素材/完整TXT及使用顺序，不等待用户追问。首次、修订和恢复补交都适用；自动推进先交付再续作，文件夹、日志或总览链接不能代替聊天正文交付，也不因此增加确认轮次。

视频制作材料的每次交付都套用[唯一固定模板](../math-courseware-video-prompts/references/delivery-reply.md#唯一固定模板)：共同回复开头 → 平台/模型 → 总入口 → 编号图片表 → 逐次完整TXT表 → 各片目录 → 操作与真实状态。顺序、列名和必交项固定，只替换实际内容；两条路线及修订补交共用。多片按实际播放顺序标序号，准备稿保持真实缺项，不另起可开工式开头或只给总链接。

每轮将实际图片、完整台词、提示词、映射和简明使用说明平铺到同一普通素材文件夹，直接给文件夹和关键文件链接，不自动压缩。由总入口执行[目录、依赖和恢复约定](references/handoff.md)，专业模块不各建第二套权威记录。

用户要素材到即梦等平台自行制作时，文件夹齐备是本轮交付终点，视频仍待制作。实际视频生成/声音/剪辑须有当次工具与授权，能力以核实入口为准；本套没有内置视频API。成片回传按[实际媒体检查](references/production.md#实际成片检查)核对。

从头整课按已采用蓝图的全部视频清单完成准备后才交PPT逐页制作，V001完成不代替其他计划视频；范围、观察问题、教师接话、预留页及播放验收由[课程总入口](../math-courseware-studio/references/video-integration.md)统筹。独立视频不扩展这些课程任务。更新HANDOFF并指出当前成果、检查证据、缺项和当前范围内最早可做的下一步。

自动run已记录的视频platform/model/sound及证据须先读取并沿用，仅补当前课真实缺项。平台未定不阻断已授权图片/内容准备；不把平台偏好当付费视频提交授权。后续明确改选由宿主run-configure保留依据。
