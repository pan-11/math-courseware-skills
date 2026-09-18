---
name: math-courseware-plan
description: Design teaching-aligned stories and shared assets for primary-school math AI courseware. Use with a rough scenario that has no story yet, after source analysis, or when shared story and math need confirmation before video or slide production.
---

# 情境方案和共享资产

读取[故事与资产](references/story-and-assets.md)、[项目协议](../math-courseware-studio/references/project-contract.md)；实际生图时读[线路规则](../math-courseware-studio/references/image-routing.md)。控制器在相邻总入口`scripts/courseware.py`。

默认提出3套可比较的情境，说明任务链、教学收益、角色地点和制作负担。已有情境时给同一情境的少量故事走向，已有故事时直接补缺口；不要求用户先交故事。推荐一稿，写明人物、目标、困难、因果事件、数学问题和学生行动，供用户审阅。用户选定后把每个事件与数学问题绑定；缺教材数据明确标注自拟示例或待补信息，不能伪装成原题。优先确认事件、条件和核心数据，视频表演与镜头由[视频模块](../math-courseware-video/SKILL.md)细化。

从头整课必须在方案中安排情景视频，至少一段，明确教学节点、学生观看任务及所需视频页数。共同故事/数学明确后交video，由其编剧完善可观看事件并按六步准备；按[课程侧前置清单](../math-courseware-studio/references/video-integration.md#ppt开工前的视频方案检查)核对全部计划视频后再交pages。教师接话/教学活动由本模块与documents安排，不要求video补写，不把简要video_nodes当作完整视频方案。

设计封面前读取[封面设计](references/cover-design.md)，从用户已说明的用途区分公开课、日常教学等目标。围绕课题和故事制作4张有实质设计差异的封面候选；明确参考风格时在该风格内比较构图与叙事，不机械套用四种固定画风。公开课封面重点建立课题形象和故事入口，不能把知识页的背景元素上限直接套入封面。用户选风格后再批量生产共享角色/场景/道具。保存真实三视图图片、固定设定、原提示词、实际参考图和版本。不能用文本描述充当已经完成的资产。

视频的图片资产放在剧本/25格预览之后、导演之前；本模块的风格选择/封面参考可在该资产阶段协同进行，已定图直接复用。不要求预览前做全套三视图，也不能等导演/正式板完成才给它们生成参考。视频所需实图由[video-assets](../math-courseware-video-assets/SKILL.md)制作并交回同一共享索引；其他PPT资产按需要继续制作，不重复生成两套版本。

角色默认正侧背；地点默认主视角、侧向视角、整体布局/俯视关系，必须是同一个地点。进入视频素材制作时与video共用这些三视图，已有同版图直接复用，缺图由AI实际生成并交付副本。固定镜头讲话交video生成单首帧和完整台词用于即梦数字人，不添加运镜切镜；运镜切镜由video生成黑白故事板和对应分镜词，不预设每镜还需彩色单帧。每个视频节点保存教学用途、事件、台词简稿、资产和视频结束后的教师行动；不锁定视频模型、九宫格或故事板格数。

按当前阶段产出`planning/scenario-options.md`、`planning/story-bible.md`、`planning/video-handoff.md`、`assets/asset-prompts.md`、实际图片及`_state/story.json/math.json/assets.json`。故事先交视频模块；视频方案与流程通过且实际资产可用后，才一起交页面模块。视频若改变共同事件、数学或台词含义，回到本模块同步共同记录，不另建一份互相矛盾的故事。
