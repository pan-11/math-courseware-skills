---
name: math-courseware-analyze
description: Use when a primary-school math courseware task starts from an uploaded PPTX, PDF, textbook page, image or teaching requirement, or when the user asks to inspect an existing lesson before redesigning it.
---

# 课件与教学材料分析

读取[分析规范](references/analysis.md)、[可见报告模板](references/source-report-template.md)、[共用流程](../math-courseware-studio/references/workflow.md)和[共用项目协议](../math-courseware-studio/references/project-contract.md)。共用控制器位于相邻`math-courseware-studio/scripts/courseware.py`。

先核项目总目标与本次范围。上传别人课件用于整课重做时，原课分析是第一步，不能把已有PPT当作新版方案已采用。用户只说“先看一下”，本轮止于读取和分析，不开展故事、视频或页面制作；没有原课件才写教学需求分析，原页数、原流程和原视频标为不适用，不编造。

从原资料识别课题、年级、课时、教材、目标、重难点和例题链。仅对确实无法识别、会影响教学判断的信息提问。文字提取和图像阅读结合；扫描识别出来的关键数字必须回看原图。

先核数学问题是否成立，再考虑故事包装。用户允许方案阶段调整情境、顺序和练习，但保留核心知识、数量关系、难度及目标，列明改动。不要为凑戏剧冲突发明不成立的推理。

先向用户交付可阅读的`planning/analysis.md`：总体质量评价、具体原页的优点与借鉴方法、问题与优化方向、准确总页数及隐藏页范围、完整教学流程和逐页功能表、原课视频清单。视频去重片数与播放位置数分别统计，每个位置列原页、内容、教学作用、前后衔接及实际看听状态与依据；仅有海报、播放图标或文稿设想不算实片，未取得/未完整看听的内容如实标未知。

同时保留`planning/math-review.md`、`key-visuals.md`及`_state/materials.json`、`math.json`。给每个核心题目和重要图示标原文件及页码；没有完整读取的附件明确记为未读。已有分析复核时保留旧版，沿本课版本约定保存修订和当前阅读入口，不靠覆盖原件推进。

先指出明确数学错误和来源冲突及其影响，再将可用分析交给方案模块。可确定的算术用精确计算复核，不能拿字段齐全代替教学判断。结束时按共用流程核对C1实际证据；分析完成不代表C2整课蓝图已经采用，后续蓝图及全课视频安排须独立形成并定稿。
