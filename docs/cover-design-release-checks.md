# Public-Lesson Cover Design Checks

Date: 2026-09-15
Version: 0.2.1

## Behavior change

公开课封面可以展开完整故事场景，明确角色动作、构图尺度、空间层次、材质光影和标题系统。封面不再机械套用知识页的背景元素数量、固定模块或大片空白要求；教学页继续保证题目、数学数量与操作区清楚。减法用于去除重复标签和无关装饰，不能削弱封面故事主画面。

该规则适用于使用当前七模块源码或0.2.1包的新课，不是某一节课的例外。画风由课题与用户参考决定，不强制3D、科技感或固定四种风格；四候选比较场景组织、视角、动作或标题关系。已有其他项目的安装副本需更新后生效。

## Changed instructions

- [方案入口](../skills/math-courseware-plan/SKILL.md)在封面设计前读取新增[封面规范](../skills/math-courseware-plan/references/cover-design.md)。
- [故事与资产](../skills/math-courseware-plan/references/story-and-assets.md)沿用用户视觉选择，明确半3D不构成通用质量上限。
- [页面设计](../skills/math-courseware-pages/references/page-design.md)区分封面与知识/练习页的密度规则。
- runtime/prompts.py仅调整共用LESS文字，使导出提示词包含页面用途差异；未改变算法、API或数据结构。最初封面具体构图由设计提示词决定，不能将LESS误称为其唯一来源。
- README、Codex与WorkBuddy安装提示词同步0.2.1版本及封面规则入口检查；旧版本包保留。

## Verification evidence

2026-09-15已执行完整单元测试，最终50项全部通过，耗时38.638秒。首次全套有1项原有OfficeCLI测试报告System.Private.Xml程序集缺失；该项单独复查及全套复跑通过，未改编辑器或环境，不声称该环境问题已修复。打包阶段仅改版本/安装说明和验证摘要，复用这次已通过的实现测试。

七个Skill均通过官方quick_validate.py；42处Skill内相对Markdown引用及Python语法检查通过。打包另核对说明文件引用、完整七模块、ZIP完整性、逐文件源码/包SHA256和独立清单；结果记录于dist/release-manifest-0.2.1.json。Git提交使用明确文件清单，并核对暂存字节与包内源码。

此版本没有通过新生成封面验证视觉效果，规则和文字检查不等于成图被用户接受。WPS显示、可画回传及课堂效果仍需实际材料验证。此次不执行全局安装，不包含课程输入、来源原文、测试产物、缓存、字体或凭据。
