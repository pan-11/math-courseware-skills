# 小学数学 AI 赋能课件 Skills

当前源码包含十二个Skill：课程总入口、五个课程专业模块，以及视频总入口＋五个视频专业Skill，共用现有执行脚本。支持从原课件或大致教学情境开始，形成共享故事与资产，再制作课堂视频、完整页面图、可画拆层后的可编辑PPT及配套文稿。

当前源码的整课制作顺序：**向用户展示原课分析**→**整课教学蓝图与故事/数学采用**→**全部计划视频的创作与制作准备（内含风格和实际资产制作）**→**含视频预留页的逐页文案**→页面图片→可编辑PPT与三文稿→成片回填和课堂播放检查。从头使用整套Skill制作时，情景视频必做，至少一段；选定故事不等于采用整课方案，完成第一段视频准备不等于完成全部视频准备。

2026-09-19源码新增整课/按模块范围记录、共用流程检查及可见原课分析模板，保留十二Skill及六步视频流程。使用这些新规则请获取当前仓库完整源码；已发布的0.2.1（七模块）及20260918完整源码包均不包含这次流程检查，安装旧包不会自动获得新规则。真实课件、服务商出图、视频效果、可画往返和WPS显示仍需实测；测试夹具不能代替首课验收。

## 开始使用

在Codex中打开此项目，提供原课件PPT/PDF或逐页图片，并发送：

> 读取当前项目 skills/math-courseware-studio/SKILL.md，按这套Skill制作我上传的小学数学AI赋能课件。先分析资料，沿用项目已确认的规范和偏好。

继续已有课程时说明课件项目路径：

> 继续 projects/我的课件项目，先读取AGENTS和HANDOFF，核对状态后从未完成的步骤继续。

首次生图选Codex内置或Grsai一次。默认PPT楷体、WPS检查。不要把密钥粘贴进聊天；Grsai执行器可读取已有环境变量、stdin或项目外secret文件。

可直接转发的安装提示词与整课、独立回填、两路视频使用示例见[朋友安装与使用说明](docs/friend-install-and-use.md)，另附[离线阅读版](docs/friend-install-and-use.html)。

十二个Skill应成套保存，不能只取一个专业目录而遗漏共用脚本。当前包不自动安装到全局Skill目录；在本项目中按上述文件入口即可试用。迁移到其他电脑先运行doctor定位依赖，不直接照抄这台电脑路径。项目级安装提示词：[Codex](docs/install-codex-prompt.md)、[WorkBuddy](docs/install-workbuddy-prompt.md)；使用包含五个新视频专业目录的当前源码，不能用旧0.2.1包代替；其他项目安装副本需在取得新源码后按提示词更新。

公开课封面按[封面设计规则](skills/math-courseware-plan/references/cover-design.md)组织完整故事场景、角色动作、标题和视觉层次，不机械套用知识页的背景元素上限或固定大片留白。规则适用于后续新课，具体画风服从当前课题和用户参考；不固定为3D、科技风或四种模板。知识与练习页继续保证题目、数量关系和操作区清楚。

## 模块

| 入口 | 用途 |
|---|---|
| [总入口](skills/math-courseware-studio/SKILL.md) | 新建、继续、修改和交付 |
| [分析](skills/math-courseware-analyze/SKILL.md) | 原课质量、优点与优化、全页流程、视频清单、数学与读取证据 |
| [方案与资产](skills/math-courseware-plan/SKILL.md) | 整课蓝图、情境、故事与数学定稿、风格和共享资产 |
| [视频总入口](skills/math-courseware-video/SKILL.md) | 自动调度下列五个专业Skill、管理版本和素材文件夹；支持粗情境起步及固定讲话简路 |
| [视频编剧](skills/math-courseware-video-writer/SKILL.md) | 可观看剧本、完整台词、5×5关键画面剧情预览 |
| [视频资产](skills/math-courseware-video-assets/SKILL.md) | 实际三视图/多角度/道具/讲话首帧；从采用彩色图冻结风格 |
| [视频导演](skills/math-courseware-video-director/SKILL.md) | 节拍、专业调度与运镜，八部分静态/动态双表 |
| [黑白故事板](skills/math-courseware-video-storyboard/SKILL.md) | 按正式镜号和实际参考生成黑白板并逐格检查 |
| [视频提示词](skills/math-courseware-video-prompts/SKILL.md) | 每段完整五部分视频词、真实上传映射与数字人用法 |
| [页面](skills/math-courseware-pages/SKILL.md) | 逐页内容、准确文字、完整成品页提示词和图片 |
| [可编辑](skills/math-courseware-editable/SKILL.md) | 可画交接、已有PPTX文字校正/回填、图层检查 |
| [文稿](skills/math-courseware-documents/SKILL.md) | 教师课堂逐字稿、公开课说课稿、教学设计 |

视频先完整交付全部计划视频的剧本、逐字声音、素材方案、分镜、各片段提示词和生成/声音/必要剪辑步骤及课程侧回填安排，按[前置清单](skills/math-courseware-studio/references/video-integration.md#ppt开工前的视频方案检查)检查并确认后再继续PPT制作。只写视频简述或一个小样包不满足前置。实际成片可以随后与PPT并行制作；缺工具时先交具体人工操作包，必做待办保留。

## 第一步会看到什么

上传原课件后，先交付[原课分析报告](skills/math-courseware-analyze/references/source-report-template.md)：原课制作质量和教学逻辑、值得借鉴的具体页及做法、问题与优化建议、总页数与隐藏页、完整教学流程和逐页功能表。另列视频去重片数、播放位置数、所在原页、具体内容、教学作用、播放前后衔接及读取依据；重复播放同一段视频不会误算成多段。

有实际视频时记录看过和听过的范围；只有封面、文稿或外链时说明哪些内容仍不能核实。PDF只能证明提供的PDF页数和可见信息，不能据此认定原PPT没有隐藏页或视频。没有原课件、只有教学要求时交付需求分析，不编造原课页数。你只说“先看一下”时，本次停在分析。

## 整课与单独调用的区别

共用[流程规则](skills/math-courseware-studio/references/workflow.md)分别记录项目总目标和本次范围。整课中临时进入视频或可编辑模块，仍保留整课其他待办；换对话继续也不会自动缩成单模块任务。只有实际用户指令限定本次只做某部分时，才按局部范围执行。

已有无字分层PPT与准确文字，可以直接调用可编辑模块整套回填；已有带字分层PPT可以直接校正；独立视频或文稿只核对当前需要的输入。不要求补跑原课分析、整课蓝图或其他交付物，也不把外部成果登记成虚构的上游制作记录。明确要求“这份无字分层PPT直接回填”已给出B回填方向，不再重复选择路线。

执行器在正式制作入口核对范围、前置产物、版本和必要采用。`validate`检查数据有效性，`workflow-check`检查能否进入指定步骤；`status`列出已登记阶段，但不把登记当作完成。旧项目缺少流程记录时仍可只读检查，由AI依据真实历史补齐记录，保留已有成果。整课最终完成还须核对实际成片与播放证据，导出或归档成功只代表相应操作完成。

每个独立课堂播放节点必须有视频页，计入指定总页数，保留独立可编辑的播放区域、观察问题和教师接话；22页含2个视频页时，其他页面为20页。文稿在图片课件锁定后即可开始，不必等可画。尚无成片可以交“静态阶段稿（视频待回填）”，不能宣称整课完成。PPT动画由你在WPS手动设置。

## 只有大致情境，怎样开始视频

> 读取 skills/math-courseware-video/SKILL.md。我只有“小动物开文具店”的大致情境，还没有故事。按六步帮我完成剧本、25格预览、实际图片资产、导演分镜、黑白故事板、固定风格和完整视频提示词，把实际素材集中到一个普通文件夹。已有角色、场景和数学条件沿用。

不必先自己写故事、准备角色图或做PPT。方案模块负责共享故事与数学，视频模块负责表演与制作；已有内容从当前进度继续。涉及教材原题的关键数据需要真实材料，自拟示例会明确标注。

运镜切镜固定六步：**剧本＋25格关键画面预览→图片资产→导演分镜→正式黑白故事板→固定风格→完整视频词**。图片资产在剧本与导演之间；风格由资产Skill在第五步提炼，用户无需手动切换五个Skill。25格不等于25秒或25镜，正式板也不固定13格。

单角色全程固定讲话直接做完整台词＋实际彩色首帧＋即梦数字人用法，不强制25格或故事板。两路都由AI复用/补齐实际图片，平铺在一个普通文件夹，不自动压缩。主要看两组创作成果：剧本与预览、导演与正式板；同版确认复用。

视频Skill负责片内故事的吸引力和可制作性，教师接话、观看任务和PPT回填由[课程总入口](skills/math-courseware-studio/references/video-integration.md)协调。缺工具时明确实图/媒体待办，准备稿不冒充完成品。

视频模块会调用当前已授权生图工具制作并检查实际图片，提供可复制提示词和文件交接；未内置视频API、配音或剪辑器。实际媒体制作使用当次可用工具或人工平台操作；平台和费用按现有授权处理。课件`collect`尚不收视频，视频按独立文件清单交付，详见[视频交接](skills/math-courseware-video/references/handoff.md)。

## 你参与的节点

选择情境和风格，成组确认整课蓝图与故事/数学、全部视频方案与制作流程、共享资产、页面内容、带字图片试样及整套图片；可画导入、逐页拆层、导出PPTX由你完成。Codex核对真实回传后直接整套回填文字，完成后统一逐页检查；不设置单页文字试样或坐标采用前置。视频小样及成片按实际结果审阅，最终在WPS检查播放并设置动画。已确认的同版内容不重复确认；原课分析与文稿不新增最终审批。

可画A路线带字拆层后校正；B路线去字拆层后回填。当前源码要求在可编辑制作前先说明区别、询问并等待明确选择；B可以推荐但不能默认执行，“继续”不代替选择。只有你明确同意才制作A/B对比试样，同范围已有明确选择则沿用。

选择B后固定执行：全部页面去字（包含视频页）→ 整套图片检查与确认 → 按原课件页序一页一图放入同一个完整PPTX，并输出同序PDF与逐页清单 → 可画拆层与回传 → 直接整套文字回填与逐页检查。课件有多少页，就生成多少页去字图并汇入多少页PPT；不能只交部分样页或图片目录。执行器拒绝B漏页、重复页和错序，交付前逐页核对嵌图。路线询问、B全页交接、直接整套回填以及视频必做/方案先行修订尚未打入既有0.2.1包，使用这些规则应读取当前源码。

## 本地工具

Python 3.12+，Pillow、python-pptx、python-docx、pypdf、ReportLab及OfficeCLI。Windows中文PDF使用实际已安装字体，字体文件不随包分发。建议优先使用Codex已提供的文档运行时。

```powershell
# 先通过Codex运行时发现工具确定Python绝对路径，再设置$python。
$controller = (Resolve-Path 'skills/math-courseware-studio/scripts/courseware.py').Path
& $python -X utf8 $controller doctor
& $python -X utf8 $controller --help
# AI根据真实指令维护范围记录；进入逐页制作前核对整课前置。
& $python -X utf8 $controller workflow-check --project '<实际课程目录>' --step pages
```

完整数据与命令说明见[项目协议](skills/math-courseware-studio/references/project-contract.md)。脚本处理记录、格式和文件，Codex负责教学内容、数学推理与视觉判断；不能仅以脚本退出0宣称图片数学正确。

## 验证与当前边界

首版基线见[实施与验证](docs/implementation-checks.md)，视频能力见[视频扩展检查](docs/video-skill-checks.md)，0.2.1变更见[封面规则检查](docs/cover-design-release-checks.md)，当前拆分接入见[视频模块验证](docs/video-modules-checks.md)。开发目录的行为测试：

```powershell
& $python -X utf8 -m unittest discover -s tests -p 'test_*.py' -v
& $python -X utf8 tests/validate_skills.py --validator '<系统skill-creator目录>/scripts/quick_validate.py'
```

格式校验器的PyYAML依赖只放在开发项目tests/vendor，当前进程加载，不是Skill运行依赖、不进入交付包。发布包只包含Skills、说明、来源致谢和验证摘要，不含测试、原始资料、课程私有输入或凭据。

需首课继续验证：真实参考图一致性、2.5模型与实际像素、去字保真、可画图层与文字、WPS换行/字号以及A/B总返工时间。组合内文字等当前不支持的对象会明确拒绝，不能用静默扁平化替代。

## 参考与适配

参考[原PPT Skill固定版本](https://github.com/yinsheng508-byte/ppt-skill-v3-codex-editable/tree/ca7ae6de097be9b99b50033857e22cfa023cfd67)的成熟流程、文字拆分、字体与坐标校准、试样复用和执行证据方法，并结合用户提供的课件聊天、逐页生图模板及教学文稿规范重新适配。新增共享故事资产、版本影响分析、可画已有PPTX保层处理及三种文稿分工。

Grsai按用户指定的[旧接口](https://grsai.ai/dashboard/documents/gpt-image)接入，默认模型覆盖为gpt-image-2.5。没有调用或改动被禁用的k12-courseware系列Skills。

视频流程根据用户历史反馈与指定故事板资料重新编写，参考[create-storyboard-skill固定版本](https://github.com/TateZhouSiu/create-storyboard-skill/tree/4b8662e2fee51b37488c77952bbfa302bfeaf36c)的镜头连续性和制作交接思路，以及[seedance-storyboard固定版本](https://github.com/zcx960/seedance-storyboard/tree/f87fc97e52e28520d6d59ca77725aa5a30ca5ed0)的分段表达方式。未打包外部Skill或执行参考脚本，未把宣传的稳定出片效果当成已验证事实。
