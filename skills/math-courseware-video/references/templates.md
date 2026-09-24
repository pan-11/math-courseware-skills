# 视频格式索引

各格式只维护一份。总入口按路线读取所需专业Skill，由AI填写具体内容；不交空表要求用户自填。

| 成果 | 格式负责人 |
|---|---|
| script.md、voice-script.txt、audio-script.md、25格预览/映射/生图词 | [writer](../../math-courseware-video-writer/SKILL.md) |
| asset-list.md、实际角色/场景/道具图、首帧、asset-prompts.md、style.md | [assets](../../math-courseware-video-assets/SKILL.md) |
| director.md：八部分及静态/动态双表 | [director输出规范](../../math-courseware-video-director/references/output-template.md) |
| storyboard.png、storyboard-prompt.md、storyboard-map.md | [storyboard提示词](../../math-courseware-video-storyboard/references/board-prompt.md) |
| video-prompts.md、upload-map.md、start-here.md、talking-packet.md | [prompts](../../math-courseware-video-prompts/SKILL.md) |
| 当前版本、真实文件与来源、进度、回传检查 | [总入口交接](handoff.md) |
| 全课视频节点/预留页/教师接话/课堂播放 | [studio](../../math-courseware-studio/references/video-integration.md) |

## 固定镜头讲话：talking-packet.md

旧talking-packet入口可保留；当前格式在[prompts的讲话规范](../../math-courseware-video-prompts/references/talking-packet.md)。默认直接交单张实际首帧＋talking-prompt.txt完整视频词（含全部台词），不拆步确认，不加载导演八节、25格或黑白板。首帧实际文件与三视图分开标记。

## 每片段操作包：generation-packet.md

旧文件可以继续引用，字段齐全且版本有效时无需改名或重写。新任务用prompts的video-prompts.md集中保存各片段五部分完整词及其上传映射。模板占位标签只是准备稿，实际平台引用标签未核实时不能称可直接提交。

## 历史文件兼容

screenplay.md对应新script.md；materials.md对应asset-list.md；shots.md先核字段再作为director.md来源；board-prompt.md对应storyboard-prompt.md。名称不同不使内容自动失效；继续导演设计、改镜头或缺字段确实影响当前任务时才在新版本补齐双表，保留旧文件和稳定镜号。仅调整上传顺序/标签不要求重写旧shots。

旧稿教师现场语言转交课程总入口，不混入voice-script或视频词；回传的实际声音有差异时逐句记录，不能照抄计划稿称“最终逐字稿”。恢复与失效范围见[handoff](handoff.md)。
