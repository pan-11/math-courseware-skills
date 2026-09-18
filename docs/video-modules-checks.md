# 视频六步与专业Skill拆分验证

日期：2026-09-18。范围：已批准的本地源码接入；不是新发行包、全局安装或GitHub推送。整体源码十二个Skill，视频部分为一个总入口和五个专业模块。

## 已实现的接口

| 工序 | 正式模块 | 产物 |
|---|---|---|
| 1 剧本与关键画面25宫格 | [writer](../skills/math-courseware-video-writer/SKILL.md) | 可拍剧本、完整声音、25格预览/映射及意图覆盖 |
| 2 图片资产 | [assets](../skills/math-courseware-video-assets/SKILL.md) | 实际角色三视图、场景多角度、必要道具、来源和风格初稿 |
| 3 导演 | [director](../skills/math-courseware-video-director/SKILL.md) | 原八部分结构，静态/动态双表，专业节奏与有目的运镜 |
| 4 正式黑白板 | [storyboard](../skills/math-courseware-video-storyboard/SKILL.md) | 按正式镜号生图、逐格核对、映射与生图词 |
| 5 固定风格 | assets | 从实际采用彩色图冻结风格，各段逐字共用 |
| 6 完整视频词 | [prompts](../skills/math-courseware-video-prompts/SKILL.md) | 每段五部分完整词、真实上传映射和普通文件夹入口 |

[video总入口](../skills/math-courseware-video/SKILL.md)调度模块并维护当前版本。单角色固定讲话保留完整台词＋实际单首帧＋数字人用法简路，不强制25格、双表或故事板。素材由AI实际生成/复用并查看，平台未知不阻断图片；工具不可用保持AI待办，不把提示词等同于图片完成。

课堂接话、观看任务、PPT预留与回填迁入[studio课程衔接](../skills/math-courseware-studio/references/video-integration.md)。保留整课视频必做/准备先行及既有共同记录，无新增运行时API。旧文件兼容续作，不强制改名或重做已采用图片，图片与文字平铺普通文件夹，不自动ZIP。

## 基线与独立应用

旧规则已有完整逐段视频词能力，在游乐园与两片段案例中能保留事件和对白；没有把基线描述为全面失败。主要缺口是25格无独立格式、课堂职责混入及单体规则过长。前轮导演/故事板候选应用及双表字段、纯板格式验证继续复用；本轮提升后核对引用及新增恢复约束。

- 编剧/路由：实际输出三场剧本、六句台词、25格映射和完整预览词；分别核对剧本/声音稿/声音表，台词一致。固定讲话保留左侧全身构图、完整原台词；旧稿只改上传顺序时保留原镜号/实图，不倒退补25格。
- 资产/组装：只读查看六张已有图片作为合成输入，提炼彩色风格，输出两段各五部分完整词及上传映射；两段风格逐字相同，执行对白恰好一次。图片采用前提仅属于合成测试，不登记为真实课程新增采用。
- 冲突处理：应用识别板图的多人挥手与给定单人动作、机位/设施连接的待核对项，保留原导演字段并交回上游；未用文字优先级掩盖实图差异，未声称可提交。
- 缺图：只有角色三视图时明确缺讲话首帧；无工具时列AI恢复生成任务，没有假图片/音频路径，没有把三视图冒充首帧。

## 审阅发现与修正

1. studio确认串与plan调用提示残留旧顺序：改为第二步协同风格/资产，再导演和制板。
2. “动作变化”路由过宽：限定为超出持续讲话的独立叙事动作；自然口型/轻微手势继续走讲话简路。
3. “不复用旧ID”容易影响续作：统一未变镜头沿用原ID，新增镜头不占用现有或已废弃ID。
4. 旧shots补双表规则扩大局部工作：仅继续导演/改镜头或缺字段影响当前任务时补齐，上传顺序/标签修改不做格式迁移。
5. 故事板直接交prompts的说明：明确先由assets核对/冻结风格，同版已冻结可沿用。

独立需求审阅及修改读回复核通过；独立可维护性审阅、应用与最终静态证据保留在本地测试运行目录。修后复核不冒称另一轮盲测。

## 自动验证及保留问题

- 官方quick_validate、UI元数据、UTF-8与Python语法：十二Skill通过；109处Skill本地引用存在。
- 共用控制器doctor通过运行环境发现，隔离init/validate通过；validate使用合成空项目，媒体/教学质量不在其证明范围。
- 单元套件运行60项，两次完整运行均59通过、1错误；中间该单项重跑通过。未声称全套通过。
- 未通过项：`test_direct_refill_dispatch_registers_real_authorization_dependency`。第一次OfficeCLI关闭测试副本报告缺`System.Private.Xml`；第二次OfficeCLI未在测试PPTX中生成预期命名文字对象。只读比较保留的三次PPTX后，失败与成功的文件差异可复核；原因未查明，未更改系统、安装工具、屏蔽测试或加入绕过。
- 本轮运行时代码和已有PPT回填测试源码与开始快照字节一致；此次只改Skill及必要集成文档、模块集合校验。上述既有PPT回填检查问题需另行定位，不能称已根治。
- 2125个真实课程文件哈希未变，原有非本轮源码修改保留；没有真实课件重做、媒体生成、安装、推送或删除。

常用复核命令（使用已有Python环境）：

```powershell
& $python -B -X utf8 tests/validate_skills.py --validator '<system-skill-creator>/scripts/quick_validate.py'
& $python -B -X utf8 -m unittest discover -s tests -p 'test_*.py' -v
& $python -B -X utf8 skills/math-courseware-studio/scripts/courseware.py doctor
& $python -B -X utf8 skills/math-courseware-studio/scripts/courseware.py validate --project '<isolated-test-project>'
git diff --check
```

## 验证边界

本轮检验了规则、实际图片读取与合成任务应用，没有生成新的预览/设定图/黑白板，没有调用视频平台、配音、剪辑或实际课堂播放。不能据此承诺一次稳定出片、跨帧数学正确或学生观看效果。最近发行包仍为七模块0.2.1；新流程读取当前十二模块源码，旧包不能替代。
