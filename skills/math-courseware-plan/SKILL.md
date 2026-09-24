---
name: math-courseware-plan
description: Use after source analysis when primary-school math courseware needs a whole-course teaching blueprint, story decisions, page and video budgets, or shared visual assets before production.
---

# 整课教学蓝图、情境与共享资产

**每次用户可见回复**（含进度、等待/提问和最终交付）都先在称呼后写“当前步骤”和“本步最终产物”，再写正文；按[回复说明规则](../math-courseware-studio/references/workflow.md#每次回复先说明步骤与产物)填写实际范围、子步骤和具体交付，不把预期写成已完成。

读取[故事与资产](references/story-and-assets.md)、[项目协议](../math-courseware-studio/references/project-contract.md)；实际生图时读[线路规则](../math-courseware-studio/references/image-routing.md)。控制器在相邻总入口`scripts/courseware.py`。

先按[共用流程](../math-courseware-studio/references/workflow.md)核项目目标、本次范围及实际分析成果。制作蓝图、封面、共享资产前，分别执行`workflow-check --project <目录> --step blueprint`、`--step cover`或`--step asset`；结束后登记实际产物、来源、内部核查及必要采用依据，再检查下一实际动作的前置。整课蓝图交视频时检查`video-script`及具体视频ID。独立方案/资产任务只核当前必需输入，不补整课历史。

默认提出3套可比较的情境，说明任务链、教学收益、角色地点和制作负担。已有情境时给同一情境的少量故事走向，已有故事时直接补缺口；不要求用户先交故事。推荐一稿，写明人物、目标、困难、因果事件、数学问题和学生行动，供用户审阅。用户选定后把每个事件与数学问题绑定；缺教材数据明确标注自拟示例或待补信息，不能伪装成原题。优先确认事件、条件和核心数据，视频表演与镜头由[视频模块](../math-courseware-video/SKILL.md)细化。

从头整课必须产出`planning/whole-course-plan.md`（已有版本化同类文件可沿用），把已选故事合入完整教学蓝图：

- 教学目标、重难点与保留/调整边界，每项指向原分析或明确需求。
- 完整教学环节；每环节的教师组织、学生活动、数学任务和可观察评价证据。
- 原例题、练习及关键图示的保留、调整、拓展或不采用去向，并说明原因。
- 课时与各环节时间、固定总页数预算、各环节页数及计入其中的视频页；此处是环节预算，逐页定稿文字留给pages。
- 全部视频的建议数量和稳定ID、功能、播放节点、关联事件/数学、观看任务、估时、结束状态及后续教学行动；不因已有V001就推定全课只有一段。
- 共同故事/核心数学、共享角色场景道具需求、制作顺序和真实缺项。

将具体蓝图与共同核心成组给用户审阅，绑定当前文件/来源版本及真实采用依据；只选故事方向或“继续”不代表已采用后来补写的视频数量、页数或活动安排。整课蓝图尚未采用时先补本阶段，保留已有视频草稿；不得直接把V001创作当作下一正式阶段。已选故事不重选，同版已有采用不重问。

蓝图真实采用后按其全课清单交video，由编剧完善可观看事件并按适用路线准备；再按[课程侧前置清单](../math-courseware-studio/references/video-integration.md#ppt开工前的视频方案检查)核对全部计划视频后交pages。从头整课至少一段视频，教师接话/教学活动由本模块与documents安排，不要求video补写；video_nodes仍是共同内容摘要，不能代替完整蓝图或视频准备。

设计封面前读取[封面设计](references/cover-design.md)，从用户已说明的用途区分公开课、日常教学等目标。围绕课题和故事制作4张有实质设计差异的封面候选；明确参考风格时在该风格内比较构图与叙事，不机械套用四种固定画风。公开课封面重点建立课题形象和故事入口，不能把知识页的背景元素上限直接套入封面。用户选风格后再批量生产共享角色/场景/道具。保存真实三视图图片、固定设定、原提示词、实际参考图和版本。不能用文本描述充当已经完成的资产。

视频的图片资产放在剧本/25格预览之后、导演之前；本模块的风格选择/封面参考可在该资产阶段协同进行，已定图直接复用。不要求预览前做全套三视图，也不能等导演/正式板完成才给它们生成参考。视频所需实图由[video-assets](../math-courseware-video-assets/SKILL.md)制作并交回同一共享索引；其他PPT资产按需要继续制作，不重复生成两套版本。

角色默认正侧背；地点默认主视角、侧向视角、整体布局/俯视关系，必须是同一个地点。进入视频素材制作时与video共用这些三视图，已有同版图直接复用，缺图由AI实际生成并交付副本。固定镜头讲话交video连续完成单首帧和含全部台词的完整视频提示词，同轮展示图片并交完整词用于即梦数字人，不拆步确认，不添加运镜切镜；运镜切镜由video生成黑白故事板和对应分镜词，不预设每镜还需彩色单帧。每个视频节点保存教学用途、事件、台词简稿、资产和视频结束后的教师行动；不锁定视频模型、九宫格或故事板格数。

按当前阶段产出`planning/whole-course-plan.md`、`scenario-options.md`、`story-bible.md`、`video-handoff.md`、`assets/asset-prompts.md`、实际图片及`_state/story.json/math.json/assets.json`，已有有效文件复用。蓝图采用后交视频模块；全部视频准备通过后交页面内容，本页实际采用资产齐备才可生图。视频若改变共同事件、数学或台词含义，回到本模块检查蓝图和共同记录的实际影响，不另建互相矛盾的故事。
