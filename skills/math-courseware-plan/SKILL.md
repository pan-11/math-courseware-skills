---
name: math-courseware-plan
description: Design teaching-aligned stories and shared assets for primary-school math AI courseware. Use with a rough scenario that has no story yet, after source analysis, or when shared story and math need confirmation before video or slide production.
---

# 情境方案和共享资产

读取[故事与资产](references/story-and-assets.md)、[项目协议](../math-courseware-studio/references/project-contract.md)；实际生图时读[线路规则](../math-courseware-studio/references/image-routing.md)。控制器在相邻总入口`scripts/courseware.py`。

默认提出3套可比较的情境，说明任务链、教学收益、角色地点和制作负担。已有情境时给同一情境的少量故事走向，已有故事时直接补缺口；不要求用户先交故事。推荐一稿，写明人物、目标、困难、因果事件、数学问题和学生行动，供用户审阅。用户选定后把每个事件与数学问题绑定；缺教材数据明确标注自拟示例或待补信息，不能伪装成原题。优先确认事件、条件和核心数据，视频表演与镜头由[视频模块](../math-courseware-video/SKILL.md)细化。

设计封面前读取[封面设计](references/cover-design.md)，从用户已说明的用途区分公开课、日常教学等目标。围绕课题和故事制作4张有实质设计差异的封面候选；明确参考风格时在该风格内比较构图与叙事，不机械套用四种固定画风。公开课封面重点建立课题形象和故事入口，不能把知识页的背景元素上限直接套入封面。用户选风格后再批量生产共享角色/场景/道具。保存真实三视图图片、固定设定、原提示词、实际参考图和版本。不能用文本描述充当已经完成的资产。

上述封面与批量资产适用于推进整套课件。用户先做视频时，先交共享故事与数学，允许video写剧本；已有风格沿用，未定则先给文字建议，再做当前小样需要的代表资产。无需等待所有三视图或PPT完成，后续整套课件继续补其需要的资产。

角色默认正侧背；地点默认主视角、侧向视角、整体布局/俯视关系，必须是同一个地点。视频先行只补镜头实际需要的视角。每个视频节点保存教学用途、事件、台词简稿、资产和视频结束后的教师行动；不锁定视频模型、九宫格或故事板技术。

按当前阶段产出`planning/scenario-options.md`、`planning/story-bible.md`、`planning/video-handoff.md`、`assets/asset-prompts.md`、实际图片及`_state/story.json/math.json/assets.json`。成组核对并记录确认后，故事可先交视频模块，实际资产可交页面模块。视频若改变共同事件、数学或台词含义，回到本模块同步共同记录，不另建一份互相矛盾的故事。
