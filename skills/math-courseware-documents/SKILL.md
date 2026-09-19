---
name: math-courseware-documents
description: Write and export classroom speaking scripts, public-lesson presentation scripts and lesson plans aligned with a locked primary-school math AI courseware deck. Produces editable DOCX and selectable-text PDF without changing the slides.
---

# 配套教学文稿

读取[课堂逐字稿](references/classroom-script.md)、[说课稿](references/lesson-presentation.md)、[教学设计](references/lesson-plan.md)及[项目协议](../math-courseware-studio/references/project-contract.md)。控制器在相邻总入口`scripts/courseware.py`。

先读[共用流程](../math-courseware-studio/references/workflow.md)，在本次范围内执行`workflow-check --project <目录> --step documents`；完成后登记实际文件、来源版本、内部检查和已有采用依据，交付前检查`collect`或对应范围的`complete`。整课C7可与可编辑C6并行。独立文稿只核用户指定的课件/教案等真实来源与用途，不补故事、视频、图片或可编辑流程；输入接入不登记为上游制作完成。

基于已确认图片课件即可开始，不必等可画。三份正文各有职责：逐字稿按PPT页口播；说课稿说明为什么这样设计；教学设计写教师如何组织、学生如何行动和怎样评价。页面可见文字稿属于页面模块，不混同教师口语。

使用本次已核对的有效课件、教学方案和真实资料，整课采用当前锁定版本，独立任务保存实际输入的来源对应。发现明确版本冲突先记录并指出，再按有效依据处理；不能在写稿时偷偷改题目、页序或知识结论。没有逐页课件时按实际用途写文稿，不编造PPT页码。

从头整课读取已通过的视频方案与制作流程，三文稿按PPT中明确的视频页逐一对应：观看前问题、视频对白/旁白、片尾教师接话及下一活动。视频未成片时依据已确认完整剧本写教学预案，在交接说明中保留必做视频待回填状态，不编实测时长或已播放情节。教师代读仅作课堂备用方案，不能据此省略视频页或宣布整课完成。没有真实授课反馈时，把反思写成课前预判、观察重点和改进预案，不伪称“学生均已掌握”等已发生结果。

已有视频时按[课程衔接](../math-courseware-studio/references/video-integration.md)读取视频交来的实际采用版、最终声音稿及结束状态，由本模块撰写或沿用课程侧教师接话；不要求视频编剧/导演为此加台词。对白/旁白引用与教师现场口语分开，三种文稿按当前页面及相同视频内容同步。视频改了数学或事件含义，先修共同记录再更新稿；只有文件名不视为已检查。视频先行而页面未定时可以写相关教学段落草稿，不编页码或交付逐页最终稿。

整课由Codex撰写三份同源JSON后执行`export-documents`；独立任务按用户指定文稿种类与现有接口能力交付，来源索引只登记实际输入，不伪造空故事/数学的采用来满足接口。实际输出DOCX与可选择文字的PDF，轻量检查内容、版式、跨页表格和教师正文清洁度；普通质量问题直接修订，不增加独立最终审批。

整课三种必交文稿完成后整理交付；独立任务完成其指定范围。学习单、板书成品等额外产物按用户需要增加；教学设计中的简明板书方案属于教案内容。
