---
name: math-courseware-pages
description: Plan exact per-slide teaching content and generate complete text-bearing slide images for primary-school math AI courseware using approved stories and shared assets. Use for page planning, image prompts, sample slides and image decks.
---

# 页面内容、提示词与图片课件

读取[页面规范](references/page-design.md)、[项目协议](../math-courseware-studio/references/project-contract.md)，生图时读[线路规则](../math-courseware-studio/references/image-routing.md)。控制器位于相邻总入口`scripts/courseware.py`。

先安排每页教学目的、学生活动、教师关键提问、可见文字、数学画面、资产和需要独立编辑的对象。每页一个重点，先减装饰和重复UI。短句化在文案定稿前完成；生成时不得擅自删题目条件。

从`pages.json`执行`render-prompts`，得到可见文字稿和固定五段式提示词。每页独立展开完整风格、角色和真实内容；生成的是带字完整PPT成品页。不要把用户另一段“85%留白底图”要求套给全部成品页。

默认第1—3页试样，默认最多5页；必要时加关键复杂页并说明。确认试样后复用已通过图片，生成余页。参考资产以实际图片进入任务，不只在文字中提名。

逐页查看真实图片，核对文字、组数/每组数量、图形/数轴/统计关系、角色连续性和投屏层级。发现问题局部修复，不把API成功当成页面通过。

登记`page.image={path,sha256}`与检查证据，整套确认后登记当前页面记录和图片的批准；执行`export-slides`输出图片PPTX/PDF，再交给可编辑或文稿模块。
