---
name: math-courseware-editable
description: Prepare manual Canva layer-splitting handoffs and edit returned layered PPTX files for primary-school math courseware. Correct existing native text or refill text-free slides with OfficeCLI while preserving original layers.
---

# 可画拆层与可编辑PPT

读取[可画交接](references/canva-handoff.md)和[文字与几何](references/text-and-geometry.md)。控制器位于相邻`math-courseware-studio/scripts/courseware.py`；先运行`doctor`确认OfficeCLI。

保留两条路线：A带字拆层后校正；B确认图去字、拆层后回填。B优先试用，真实同页A/B比较后决定采用路线。用户已验证可画能拆层，不重复要求证明功能存在。

由用户手动导入可画、逐页AI拆层、导出PPTX。用交接清单、页标题和实际预览核对映射，不按文件出现顺序猜页码。接收原稿后执行`canva-import`保存副本和对象清单。

正确文字来自已确认`pages.json`，带字图提供几何与视觉参考，提示词补充设计意图。分别建立文字单元、原生/图片归属、坐标计划；标题、题干、答案、步骤、关键数学标签分开。默认KaiTi，显式中文字体槽、逐单元字号及段落设置，不自动缩小塞字。

先做一页原生文本试样，给用户看坐标和效果并记录真实确认，再执行`editable-build`。编辑器只处理回传副本，不清空课件、不以整页图片覆盖图层。不支持的对象先记录具体限制，不能静默扁平化。

回读每个文字单元和原图层；检查WPS显示、手动动画所需的独立对象。当前本地结构验证与真实WPS/可画验证分开记录。文案或题目有改动需同步上游及文稿，纯动画不改文稿。
