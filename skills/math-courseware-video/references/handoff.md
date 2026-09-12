# 视频文件、回传与恢复

## 项目内保存

不另建第二套课程。先在当前课AGENTS补充下列用途，再创建实际需要的目录；现有init不会自动建立videos。保留旧版本，不自动删除。

| 位置 | 用途 |
|---|---|
| planning/video-handoff.md | 全课视频总表、当前版本路径、教学节点、待办与模块交接 |
| _state/story.json 的 video_nodes | 共同内容：video_id、purpose、event、place、characters、math_ids、dialogue、narration、asset_refs、teacher_next；沿用已有编号 |
| assets/ 与 _state/assets.json | PPT与视频共用的实际角色/场景/关键道具，不另造重复权威记录 |
| videos/V01/v001/ | 此视频版本的screenplay.md、audio-script.md、materials.md、shots.md，以及实际需要的board-prompt.md、generation-packet.md、return-review.md、manifest.json |
| videos/V01/v001/inputs/ | 按需保存的构图板、关键帧、音频等实际输入；共享资产引用原项目路径即可 |
| videos/V01/v001/returned/ | 原样保存用户或工具回传的候选片段，文件名含稳定片段ID |
| videos/V01/v001/output/ | 剪辑输出、最终字幕/音轨；不修改returned原件 |
| deliveries/video-delivery-v001/ | 按明确清单复制的本轮视频交付及manifest；与课件collect输出分开 |

只有实际进入视频制作才建相应版本目录；早期情境候选仍在planning。新版本用未占用的v002等编号；未改的素材引用原文件，不为改运镜重做角色。与当前进度无关的空文件不创建。

## 记录真实状态

技术制作进度保存在视频manifest和全课总表，不为每次出图/剪辑重写共同story记录，避免无内容变化也让PPT失效。

状态按实际证据推进：`draft`草稿 → `content_confirmed`内容定稿 → `materials_pending`或`ready_to_generate` → `sample_review`/`sample_passed` → `editing` → `final_review` → `accepted`。已有真实成果可以从对应阶段接入；这些是指导记录，不是新增控制器命令。

`accepted`表示实际内容、画面、声音已检查且有用户采用依据；`classroom_playback`单独记录待查/通过/未通过。没有WPS/PPT实际播放证据，不能称课堂播放验收完成。用户选择其他播放方式则据实际使用环境检查。

每个manifest至少写：

```json
{
  "video_id": "V01",
  "revision": "v001",
  "stage": "draft",
  "source_versions": {},
  "files": [],
  "clip_results": [],
  "final": null,
  "classroom_playback": "pending",
  "next_action": "当前实际缺口和下一步"
}
```

以上仅说明字段；正式清单由AI填实际内容，不能把空对象当成已验证清单：

- `source_versions`：实际使用的`_state/story.json`、`_state/math.json`、`_state/assets.json`及其他输入路径到SHA256的映射；不存在的文件不填假哈希，明确缺项。
- `files`：实际存在文件的项目相对`path`、`sha256`、`role`、`status`；可包含现有共享资产，禁止把尚未生成的目标路径列成文件。
- `clip_results`：clip_id、模式、实际任务ID（若有）、候选文件、时长、采用/退回原因、费用/耗时（未知就写未知），不编后台ID。
- `final`：仅在实际收到文件后记录path、sha256、实测duration_seconds、width/height、最终逐字稿路径、审阅证据与采用依据；未知数据保留null并说明。有成片文件不代表已通过。

草稿可直接保存；批准用现有`record-approval`，目标绑定具体剧本、声音稿或小样文件哈希，证据来自用户对当前内容的实际确认。一次明确确认覆盖的一组文件可一起登记，不为同版逐项重问。

## 与现有执行器的衔接

共用执行器维持现有命令，不存在`generate-video`、`video-register`或`video-package`命令。视频manifest是本模块工作记录，不是数据库变更，不传给只支持既有权威JSON的`record-change`。

用`state.register_artifact(project, id, path, dependencies, metadata)`登记已存在的制作资料或成片，ID如`video-V01-script`、`video-V01-final`。`dependencies`包含实际使用的V/E/M/资产ID及权威记录路径；`metadata`保存`source_versions`和实际审阅状态。制作时若确实依赖某稿文件，也登记其路径/哈希。不要登记不存在的成片。

`status`显示通用artifacts及stale_targets；`validate`核查已登记文件哈希，但不会核查视频播放、时长、台词或全部视频来源哈希。恢复时必须另外比较manifest中的来源哈希、读实际内容/图片/视频，不能仅因validate退出0就沿用旧稿。

全记录哈希会保守标记可能受影响的材料；按具体V/E/M/资产依赖逐项复核。确认无内容影响可以记录核查证据后更新来源，不重新生成未受影响素材；有影响就修内容，不仅刷新哈希。

## 改动与回填顺序

1. 读取真实回传文件与原剧本，核对哈希、可取得的媒体属性、画面与完整声音；只有转述或文件名时写待回传，不冒充已看过。当前工具无法播放/读媒体时记录限制并安排实际检查。
2. 列出数学、事件、语义、台词和声音的差异。拍摄角度/停顿的普通调整在视频记录内处理；改变共同事件、条件或台词含义时回到plan和共同数据确认，不能仅在文稿里圆回来。
3. 数学差异先核准。例如“至少两颗”不能改成“正好两颗”；只证明必有某个位置重复，不能凭此指定哪一个位置。错误成片标为需修，不修改正确题目配合错误视频。
4. 共同数据变更通过`impact`/`record-change`保存旧版，再同步引用该video_id的页面、可见文字与相关文稿。原故事重新批准不会自动使旧视频产物有效，必须重新核对。
5. 内容一致后登记实际成片、最终逐字稿、结束画面、教师接话、已知时长与检查证据；技术状态写manifest，避免写入共同故事造成循环失效。
6. 已有页面用真实page_id及当前order关联；尚未排页只填教学节点与“页面待关联”。页面建立后由pages写入video_ids；教师逐字稿、说课稿、教学设计按最终采用内容同步。无锁定课件时只能给文稿相关段落草稿，不能编造逐页最终稿。

## 单独交付与继续

视频先做不依赖页面完成。现有`collect`只收规定路径的课件/文稿/图片，并要求课件依据已锁定；它会忽略mp4等视频。登记artifact并不会改变这个行为。

视频交付由AI使用当前文件工具按明确清单操作：先复核来源哈希与实际状态，在新的`deliveries/video-delivery-vNNN/`中复制实际需要的剧本、声音稿、素材/参考图、分镜、操作包、候选或成片。保留项目相对目录，使包内引用可追踪；文件不在项目内先登记合法来源副本，不能越界收集。排除密钥、缓存和无关课程。

给交付清单写入每项原path、delivery_path、SHA256、用途、当前状态及来源版本；复制前后哈希一致才记录完成。只有准备材料也可交付，名称和说明标明制作准备包；成片未回传就不列成片文件。清单不要哈希自身造成循环。正式课件成套交付前，汇总课件collect与视频独立交付位置并核对页面/文稿关联。

更新课件HANDOFF：当前视频/版本、完成内容、文件、检查与依据、缺项、下一步、待关联页面和课堂播放状态。用户继续时从这些记录恢复；不重写已确认故事，不重复生成已通过素材，不把等待回传当任务完成。
