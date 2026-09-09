---
name: math-courseware-plan
description: Design and freeze a teaching-aligned story and shared character, scene and prop assets for primary-school math AI courseware. Use after source analysis and before producing final slide pages.
---

# 情境方案和共享资产

读取[故事与资产](references/story-and-assets.md)、[项目协议](../math-courseware-studio/references/project-contract.md)；实际生图时读[线路规则](../math-courseware-studio/references/image-routing.md)。控制器在相邻总入口`scripts/courseware.py`。

默认提出3套可比较的情境，说明任务链、教学收益、角色地点和制作负担。用户选定后写简明故事，把每个事件与数学问题绑定。优先确认故事事件、条件和核心数据；视频镜头留到后续。

围绕课题和故事制作4张封面风格候选，用户选风格后再批量生产共享角色/场景/道具。保存真实三视图图片、固定设定、原提示词、实际参考图和版本。不能用文本描述充当已经完成的资产。

角色默认正侧背；地点默认主视角、侧向视角、整体布局/俯视关系，必须是同一个地点。每个未来视频节点保存教学用途、事件、台词简稿、资产和视频结束后的教师行动；不锁定视频模型、九宫格或故事板技术。

产出`scenario-options.md`、`story-bible.md`、`video-handoff.md`、`assets/asset-prompts.md`、实际图片及`story.json/math.json/assets.json`。成组核对并记录确认后交给页面模块。
