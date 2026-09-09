# 小学数学 AI 赋能课件 Skills

首版包含一个总入口、五个工作Skill和共用执行脚本。面向“原课件→教学情境→共享资产→完整页面图→可画拆层后的可编辑PPT→配套文稿”的制作过程。

当前版本：0.1.0，本地试用版。真实课件、服务商出图、可画往返和WPS显示需要首课实测；测试夹具不能代替首课验收。

## 开始使用

在Codex中打开此项目，提供原课件PPT/PDF或逐页图片，并发送：

> 读取当前项目 skills/math-courseware-studio/SKILL.md，按这套Skill制作我上传的小学数学AI赋能课件。先分析资料，沿用项目已确认的规范和偏好。

继续已有课程时说明课件项目路径：

> 继续 projects/我的课件项目，先读取AGENTS和HANDOFF，核对状态后从未完成的步骤继续。

首次生图选Codex内置或Grsai一次。默认PPT楷体、WPS检查。不要把密钥粘贴进聊天；Grsai执行器可读取已有环境变量、stdin或项目外secret文件。

六个Skill应成套保存，不能只取一个专业目录而遗漏共用脚本。当前包不自动安装到全局Skill目录；在本项目中按上述文件入口即可试用。迁移到其他电脑先运行doctor定位依赖，不直接照抄这台电脑路径。

## 模块

| 入口 | 用途 |
|---|---|
| [总入口](skills/math-courseware-studio/SKILL.md) | 新建、继续、修改和交付 |
| [分析](skills/math-courseware-analyze/SKILL.md) | 教学任务、数学事实、关键原图 |
| [方案与资产](skills/math-courseware-plan/SKILL.md) | 情境、故事与数学定稿、角色场景三视图 |
| [页面](skills/math-courseware-pages/SKILL.md) | 逐页内容、准确文字、完整成品页提示词和图片 |
| [可编辑](skills/math-courseware-editable/SKILL.md) | 可画交接、已有PPTX文字校正/回填、图层检查 |
| [文稿](skills/math-courseware-documents/SKILL.md) | 教师课堂逐字稿、公开课说课稿、教学设计 |

文稿在图片课件锁定后即可开始，不必等可画。视频Skill暂不包含；故事、台词简稿和实际资产保留给未来视频使用。动画由你在WPS手动设置。

## 你参与的节点

选择情境和风格，成组确认故事/数学、共享资产、页面内容、试样及整套图片；可画导入、逐页拆层、导出PPTX由你完成。文字坐标与效果确认后由Codex处理副本，最后在WPS检查并设置动画。已确认的同版内容不重复确认；文稿不增加最终审批。

可画A路线带字拆层后校正；B路线去字拆层后回填。B先试，首课约3张代表页同页对比后选择，不预先承诺哪条更好。

## 本地工具

Python 3.12+，Pillow、python-pptx、python-docx、pypdf、ReportLab及OfficeCLI。Windows中文PDF使用实际已安装字体，字体文件不随包分发。建议优先使用Codex已提供的文档运行时。

```powershell
# 先通过Codex运行时发现工具确定Python绝对路径，再设置$python。
$controller = (Resolve-Path 'skills/math-courseware-studio/scripts/courseware.py').Path
& $python -X utf8 $controller doctor
& $python -X utf8 $controller --help
```

完整数据与命令说明见[项目协议](skills/math-courseware-studio/references/project-contract.md)。脚本处理记录、格式和文件，Codex负责教学内容、数学推理与视觉判断；不能仅以脚本退出0宣称图片数学正确。

## 验证与当前边界

检查记录见[实施与验证](docs/implementation-checks.md)。开发目录的行为测试：

```powershell
& $python -X utf8 -m unittest discover -s tests -p 'test_*.py' -v
& $python -X utf8 tests/validate_skills.py --validator '<系统skill-creator目录>/scripts/quick_validate.py'
```

格式校验器的PyYAML依赖只放在开发项目tests/vendor，当前进程加载，不是Skill运行依赖、不进入交付包。发布包只包含Skills、说明、来源致谢和验证摘要，不含测试、原始资料、课程私有输入或凭据。

需首课继续验证：真实参考图一致性、2.5模型与实际像素、去字保真、可画图层与文字、WPS换行/字号以及A/B总返工时间。组合内文字等当前不支持的对象会明确拒绝，不能用静默扁平化替代。

## 参考与适配

参考[原PPT Skill固定版本](https://github.com/yinsheng508-byte/ppt-skill-v3-codex-editable/tree/ca7ae6de097be9b99b50033857e22cfa023cfd67)的成熟流程、文字拆分、字体与坐标校准、试样复用和执行证据方法，并结合用户提供的课件聊天、逐页生图模板及教学文稿规范重新适配。新增共享故事资产、版本影响分析、可画已有PPTX保层处理及三种文稿分工。

Grsai按用户指定的[旧接口](https://grsai.ai/dashboard/documents/gpt-image)接入，默认模型覆盖为gpt-image-2.5。没有调用或改动被禁用的k12-courseware系列Skills。
