---
name: math-courseware-analyze
description: Analyze source PPTX, PDF, textbook pages and images for a primary-school math AI-scenario courseware project. Extract teaching structure, exact math problems and essential visuals before story and page production.
---

# 课件与教学材料分析

读取[分析规范](references/analysis.md)和[共用项目协议](../math-courseware-studio/references/project-contract.md)。共用控制器位于相邻`math-courseware-studio/scripts/courseware.py`。

从原资料识别课题、年级、课时、教材、目标、重难点和例题链。仅对确实无法识别、会影响教学判断的信息提问。文字提取和图像阅读结合；扫描识别出来的关键数字必须回看原图。

先核数学问题是否成立，再考虑故事包装。用户允许方案阶段调整情境、顺序和练习，但保留核心知识、数量关系、难度及目标，列明改动。不要为凑戏剧冲突发明不成立的推理。

输出`planning/analysis.md`、`math-review.md`、`key-visuals.md`及`_state/materials.json`、`math.json`。给每个核心题目和重要图示标原文件及页码；没有完整读取的附件明确记为未读。

先解决明确数学错误和来源冲突，再将可用分析交给方案模块。可确定的算术用精确计算复核，不能拿字段齐全代替教学判断。
