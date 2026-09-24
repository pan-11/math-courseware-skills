---
name: math-courseware-documents
description: Create teaching documents, student worksheets and electronic blackboard stickers from a locked primary-school math courseware deck. Use for classroom scripts, lesson plans, presentation scripts, editable Word activity sheets, board lettering and movable sticker PPTX, including standalone requests.
---

# 配套教学文稿、学习单与电子黑板贴

**每次用户可见回复**（含进度、等待/提问和最终交付）都先在称呼后写“当前步骤”和“本步最终产物”，再写正文；按[回复说明规则](../math-courseware-studio/references/workflow.md#每次回复先说明步骤与产物)填写实际范围、子步骤和具体交付，不把预期写成已完成。

先按真实任务选择分支：整课C7默认制作三份教师文稿、学生课堂学习单和电子黑板贴；独立任务只做用户指定部分。用户明确省略某配套时记录依据，不另问要不要做。

学习单读取[学生版制作规范](references/student-worksheet.md)，依据有效课件与教案自主选核心任务，留足书写/画图空间，默认无答案学生版，交实际可编辑中文DOCX并检查分页。学习单与教师稿分开，不用教案练习摘录代替，也不把视频未给的数据当作观看所得。

黑板贴读取[稳定制作规范](references/blackboard-stickers.md)，由AI决定素材清单和板书组织，沿用已认可字体分工、程序描边及真实字形安全区检查，交实际整套素材，不只交提示词。黑板贴不固定数量、课题或板数，也不改原课件。

教师文稿分支读取[课堂逐字稿](references/classroom-script.md)、[说课稿](references/lesson-presentation.md)、[教学设计](references/lesson-plan.md)及[项目协议](../math-courseware-studio/references/project-contract.md)。控制器在相邻总入口`scripts/courseware.py`。以下教师文稿规则按实际范围执行，单做学习单或黑板贴不要求补三份文稿。

教师文稿分支先读[共用流程](../math-courseware-studio/references/workflow.md)，在本次范围内执行`workflow-check --project <目录> --step documents`；完成后登记实际文件、来源版本、内部检查和已有采用依据，交付前检查`collect`或对应范围的`complete`。学习单、黑板贴按各自专门规范检查来源与成品，不用三文稿完成条件阻断其独立制作。整课C7可与可编辑C6并行。独立文稿只核用户指定的课件/教案等真实来源与用途，不补故事、视频、图片或可编辑流程；输入接入不登记为上游制作完成。

基于已确认图片课件即可开始，不必等可画。三份正文各有职责：逐字稿按PPT页口播；说课稿说明为什么这样设计；教学设计写教师如何组织、学生如何行动和怎样评价。页面可见文字稿属于页面模块，不混同教师口语。

使用本次已核对的有效课件、教学方案和真实资料，整课采用当前锁定版本，独立任务保存实际输入的来源对应。发现明确版本冲突先记录并指出，再按有效依据处理；不能在写稿时偷偷改题目、页序或知识结论。没有逐页课件时按实际用途写文稿，不编造PPT页码。

从头整课读取已通过的视频方案与制作流程，三文稿按PPT中明确的视频页逐一对应：观看前问题、视频对白/旁白、片尾教师接话及下一活动。视频未成片时依据已确认完整剧本写教学预案，在交接说明中保留必做视频待回填状态，不编实测时长或已播放情节。教师代读仅作课堂备用方案，不能据此省略视频页或宣布整课完成。没有真实授课反馈时，把反思写成课前预判、观察重点和改进预案，不伪称“学生均已掌握”等已发生结果。

已有视频时按[课程衔接](../math-courseware-studio/references/video-integration.md)读取视频交来的实际采用版、最终声音稿及结束状态，由本模块撰写或沿用课程侧教师接话；不要求视频编剧/导演为此加台词。对白/旁白引用与教师现场口语分开，三种文稿按当前页面及相同视频内容同步。视频改了数学或事件含义，先修共同记录再更新稿；只有文件名不视为已检查。视频先行而页面未定时可以写相关教学段落草稿，不编页码或交付逐页最终稿。

整课由Codex撰写三份同源JSON后执行`export-documents`；独立任务按用户指定文稿种类与现有接口能力交付，来源索引只登记实际输入，不伪造空故事/数学的采用来满足接口。实际输出DOCX与可选择文字的PDF，轻量检查内容、版式、跨页表格和教师正文清洁度；普通质量问题直接修订，不增加独立最终审批。

整课三种教师文稿、学生学习单和电子黑板贴完成后整理交付；学习单与黑板贴分别按实际manifest核对，不能只用教案里的练习或板书文字代替。学习单DOCX与本套课件配套放同一交付文件夹，中文命名。独立任务完成其指定范围；教学设计中的简明板书方案仍属于教案内容。
