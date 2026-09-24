---
name: math-courseware-pages
description: Plan exact per-slide teaching content and generate complete text-bearing slide images for primary-school math AI courseware using approved stories and shared assets. Use for page planning, image prompts, sample slides and image decks.
---

# 页面内容、提示词与图片课件

**每次用户可见回复**（含进度、等待/提问和最终交付）都先在称呼后写“当前步骤”和“本步最终产物”，再写正文；按[回复说明规则](../math-courseware-studio/references/workflow.md#每次回复先说明步骤与产物)填写实际范围、子步骤和具体交付，不把预期写成已完成。

读取[页面规范](references/page-design.md)、[项目协议](../math-courseware-studio/references/project-contract.md)，生图时读[线路规则](../math-courseware-studio/references/image-routing.md)。控制器位于相邻总入口`scripts/courseware.py`。

先读[共用流程](../math-courseware-studio/references/workflow.md)，保留项目目标并核本次任务范围。逐页内容、页面生图、图片课件导出开始前分别执行`workflow-check --project <目录> --step pages`、`--step page-image`、`--step image-export`；结束后登记实际产物/来源、检查及必要采用依据，再核下一动作：逐页稿交生图查`page-image`，整套图交导出查`image-export`，导出交可编辑或文稿查其对应步骤。

整课推进先核已采用的whole-course-plan及全部视频清单，再读planning/video-handoff.md和其引用的完整剧本、声音、分镜/讲话画面及制作步骤，按[视频前置清单](../math-courseware-studio/references/video-integration.md#ppt开工前的视频方案检查)核对全部计划视频。只完成V001不能替代其他计划视频；缺项交studio定位到plan/video或课程衔接。独立页面任务或明确局部修改只核本次内容、数学及实际参考，不用整课其他视频待办阻断；外部成果登记为输入接入，不伪造上游已完成。

先安排每页教学目的、学生活动、教师关键提问、可见文字、数学画面、资产和需要独立编辑的对象。每页一个重点，先减装饰和重复UI。短句化在文案定稿前完成；生成时不得擅自删题目条件。

整课按照已采用蓝图和完整视频方案，为每个独立课堂播放节点明确安排视频页，计入已定总页数；页面方案标明页ID/页码、video_ids、观察问题、播放区域、片尾接话与下一活动。落实[视频页版式与对象要求](references/page-design.md#视频播放页)，不能只加video_ids或在讲稿中写“播放视频”。例如总计22页含2个视频页，其他页面应为20页；不在22页外悄悄追加。独立任务只保留本次实际要求的播放节点。

方案与流程通过后可在成片未回传时制作视频预留页；使用已确认场景静帧/干净区域承载，预计时长和计划片尾注明依据，不编实际文件或实测数据。成片回传后读[课程回填记录](../math-courseware-studio/references/video-integration.md)，核对真实画面、台词和课程侧教师接话，更新对应页面与文稿。文件关联、播放按钮图片均不表示已插入视频；实际媒体回填及课堂播放检查另记。

从`pages.json`执行`render-prompts`，得到可见文字稿和固定五段式提示词。每页独立展开完整风格、角色和真实内容；生成的是带字完整PPT成品页。不要把用户另一段“85%留白底图”要求套给全部成品页。

默认第1—3页试样，默认最多5页；必要时加关键复杂页并说明。确认试样后复用已通过图片，生成余页。参考资产以实际图片进入任务，不只在文字中提名。

逐页查看真实图片，核对文字、组数/每组数量、图形/数轴/统计关系、角色连续性和投屏层级；另逐项核对全部必做视频的预留页、页序和播放区域未缺失或被遮挡。发现问题局部修复，不把API成功当成页面通过。

登记`page.image={path,sha256}`与检查证据，整套确认后登记当前页面记录和图片的批准；执行`export-slides`输出图片PPTX/PDF，再交给可编辑或文稿模块。进入可编辑制作时按[路线节点](../math-courseware-editable/SKILL.md)核明确A/B方向，缺选择才说明区别、询问并等待；整套图片采用或“继续”不是路线选择。已有同范围选择及明确无字分层PPT回填请求沿用。正式带字图片版导出和独立文稿不依赖路线选择。

前面的带字页试样安排不适用于B去字交接。用户选B后，交editable完成全部页面去字，再按原课件页序一页一图生成完整PPTX；不得把带字页试样数量当作去字制作范围，具体按[全页交接规范](../math-courseware-editable/references/canva-handoff.md)执行。

可画真实回传后的文字回填也不沿用带字图片试样节点：直接整套回填，完成后统一检查，不先做一页等待采用。
