---
name: math-courseware-studio
description: Coordinate a primary-school math courseware project with AI story scenarios, shared visual assets, image slides, Canva-layered editable PPTX and teaching documents. Use for starting, resuming or changing this complete production workflow.
---

# 小学数学AI赋能课件总入口

把原课件转为教学一致、视觉连续、能继续修改的一套课件。此包含五个工作Skill；本入口只管理流程、版本和交接，不代替专业模块。

## 启动与恢复

1. 先读工作目录AGENTS.md、HANDOFF.md；已存在项目执行`status`和`validate`，不因换对话另建项目。
2. 新课项目使用`scripts/courseware.py init --project <绝对路径> --title <课题>`，目录规则由初始化器先写入。可同时指定`--route builtin`或`--route openai_image_api`；已明确选择的线路直接记录，无需重问。
3. 读取[项目协议](references/project-contract.md)，只在需要生图时读[生图线路](references/image-routing.md)，发生修改、中断或等待回传时读[恢复规则](references/recovery.md)。
4. 脚本依赖Python、Pillow、python-pptx、python-docx、pypdf、ReportLab；先用Codex的运行时发现工具定位现有环境，再运行`doctor`。缺依赖先报告，不自动安装全局依赖。

## 按实际进度调用

| 工作 | 相邻Skill入口 | 开始条件 |
|---|---|---|
| 原材料分析 | [analyze](../math-courseware-analyze/SKILL.md) | 有原课件或用户明确的制作资料 |
| 情境和共享图片资产 | [plan](../math-courseware-plan/SKILL.md) | 数学任务、改编边界已分析 |
| 逐页内容和图片 | [pages](../math-courseware-pages/SKILL.md) | 故事数学核心、风格及实际资产可用 |
| 可画与原生文字 | [editable](../math-courseware-editable/SKILL.md) | 确认图片课件；人工拆层后回传PPTX |
| 配套教学文稿 | [documents](../math-courseware-documents/SKILL.md) | 已锁定图片课件或最终课件 |

已有可靠中间成果可以从相应模块接入，先登记来源和版本。不得伪造跳过阶段的完成记录。

## 确认与持续执行

按组呈现：情境方向→故事/数学核心→封面风格→共享资产→逐页文案→试样→整套图片→文字坐标与效果→可编辑稿。沿用用户在本项目已给的确认，不为同版重复提问。文稿自审后交付，不新增文稿最终审批。

保存文件、自检通过、API返回成功都不等于用户定稿。确认绑定具体内容和文件哈希，记录真实用户依据；不要以自己的总结冒充用户原话。用户明确的纠错可执行并登记，无须重复申请同一修改。

主控串行写共用记录；独立生图任务最多并发6路。每完成一个模块或改变方案，更新课件HANDOFF：目标、产物、检查、未完成事项、下一步。

视频Skill以后单独设计；当前保存事件、台词简稿和实际资产。不强制九宫格或视频成片。PPT动画由用户在WPS手动设置。等待可画回传时可以生成配套文稿。

## 交付

执行`collect`整理当前有效产物；按实测说明“已生成”“可编辑结构已检查”“WPS已检查”等不同状态。只有真实课程贯穿流程且相关人工检查完成才称首课验收完成。发布、安装全局依赖、密钥配置和删除按用户授权处理。
