---
name: math-courseware-documents
description: Write and export classroom speaking scripts, public-lesson presentation scripts and lesson plans aligned with a locked primary-school math AI courseware deck. Produces editable DOCX and selectable-text PDF without changing the slides.
---

# 配套教学文稿

读取[课堂逐字稿](references/classroom-script.md)、[说课稿](references/lesson-presentation.md)、[教学设计](references/lesson-plan.md)及[项目协议](../math-courseware-studio/references/project-contract.md)。控制器在相邻总入口`scripts/courseware.py`。

基于已确认图片课件即可开始，不必等可画。三份正文各有职责：逐字稿按PPT页口播；说课稿说明为什么这样设计；教学设计写教师如何组织、学生如何行动和怎样评价。页面可见文字稿属于页面模块，不混同教师口语。

使用最新锁定课件、教学方案和真实资料。发现明确版本冲突先记录并指出，再按最新有效依据处理；不能在写稿时偷偷改题目、页序或知识结论。

视频未成片时按已确认用途写教学预案，不编造成片细节。没有真实授课反馈时，把反思写成课前预判、观察重点和改进预案，不伪称“学生均已掌握”等已发生结果。

已有视频时读取[成片回填](../math-courseware-video/references/handoff.md)中的实际采用版、最终声音稿和教师接话。对白/旁白引用与教师现场口语分开，三种文稿按当前页面及相同视频内容同步。视频改了数学或事件含义，先修共同记录再更新稿；只有文件名不视为已检查。视频先行而页面未定时可以写相关教学段落草稿，不编页码或交付逐页最终稿。

Codex撰写三份同源JSON后执行`export-documents`。实际输出DOCX与可选择文字的PDF，轻量检查内容、版式、跨页表格和教师正文清洁度；普通质量问题直接修订，不增加独立最终审批。

三种必交文稿完成后整理交付。学习单、板书成品等额外产物按用户需要增加；教学设计中的简明板书方案属于教案内容。
