# 视频文件、版本与恢复

## 一份当前清单

先读项目AGENTS/HANDOFF并声明目录用途，再创建实际需要的文件。单独视频使用用户指定项目/普通素材目录即可，不要求先初始化整套课程；已有课件复用原story/math/assets及video_nodes，不新造第二套权威记录。

| 位置 | 职责 |
|---|---|
| videos/<原video_id>/<新版本>/ | 当前manifest、来源与制作记录；按需returned/output保留回传原件和剪辑结果 |
| 同版本asset-kit/ | 平铺全部对外实际图、文本和start-here.md；整课汇总可用deliveries/video-assets-vNNN并加video_id前缀 |
| 原assets/及其索引 | 已有共享角色/场景/道具的权威原图；交付副本不成为新外观版本 |
| planning/video-handoff.md | 仅整课需要，由studio维护视频节点、当前manifest入口、PPT前置与教师衔接；不塞回编剧模板 |

路径为建议，已有等效目录沿用。旧版本保留，新修订使用未占用版本号；不创建无关空文件，不自动删除。用户只需一个文件夹内找到当前素材，不必跨内部归档找图。

## 当前产物与状态

总入口维护当前视频manifest（普通工作记录，不是新的runtime API）。至少记录video_id、revision、route、source_versions、products、files、缺项和next_action。沿用已有manifest时追加必要描述，不强制迁移老字段。

- source_versions：真正读取的源路径、版本及SHA256；无文件不能填假哈希。可含共同story/math/assets及本轮脚本、导演表、风格等。
- products：script/preview/assets/director/storyboard/style/prompts各自当前路径、版本、依据与状态；讲话的非适用步骤明确不适用。计划目标路径可以在缺项中描述，不加入files充当已有成果。
- files：实际文件path、role、sha256、状态；复用副本另存source_path/source_sha256并核对一致。清单不哈希自身。
- 图片生成、内部查看、用户采用分别记录；采用依据绑定具体文件版本/哈希，不把“请制作”当作“效果通过”。
- 图片材料齐备、视频平台待配置、视频可提交、已提交待回传、成片待审/已采用分别记录；有图不等于有视频。
- clip_results/final按实际回传记录任务ID（若有）、文件、实测时长/尺寸、实际逐字稿、审阅和采用依据。未知参数保持未知，不能从计划秒数填成实测。

两个主要创作审阅为剧本＋预览、导演＋正式板。资产/风格采用可并入对应组，已确认的同版成果直接复用；技术细节由AI检查。内容实质改变依真实授权处理，不能借“减少询问”伪造采用。固定讲话以完整台词＋首帧为审阅对象。

## 同一普通文件夹交付

运镜路线按进度保存script.md、voice-script.txt/audio-script.md、plot-preview-25.png及映射、实际设定图与asset-list、director.md、storyboard.png及映射/生图词、style.md、video-prompts.md、upload-map.md、start-here.md。没有实际对白时明确“无对白”，不捏造声音文件。

讲话只需完整台词、实际单首帧、必要设定参考/生图词、talking-packet与start-here；不为目录整齐伪造其他步骤文件。暂缺成果在start-here列清，不用空PNG或文本文件假冒图片。

交付前查看新增图、检查每个实际文件可打开、复制哈希相同、路径/镜号/版本相互对应；按本轮范围检查齐备性。起始说明直接告诉用户上传哪些实际文件、复制哪段词、哪些参数仍需配置。

素材包指普通文件夹，不自动ZIP或其他压缩。给文件夹和关键文件直接链接；已有ZIP是历史，不删除，也不作为新版入口。用户明确另要压缩再处理。

## 编号与变更

沿用已有V001或V01，不为新Skill强制改编号。示例中预览P01—P25、正式镜头V01-S01、板内关键状态V01-S01a/b、生成片段V01-C01各有用途；预览格不自动变成镜头，a/b不变成两个独立镜头。重排不复用已废弃ID。

| 变化 | 必须复核 | 通常保留 |
|---|---|---|
| 剧情事件/台词语义改变 | script/声音、预览、导演两表、相关板格/视频词，实际需要的资产 | 不受影响的原资产 |
| 仅构图或运镜 | 同镜两表共享字段、相关板格/映射及逐段视频词 | 剧本及外观资产 |
| 角色/场景外观改变 | 相关实际资产、风格、预览/板/首帧及引用该图的词 | 无关事件和其他资产 |
| 风格段落修订 | 核对其实际图依据，所有相关片段替换同一段原文 | 与风格无关的镜号/台词 |
| 仅上传顺序变化 | upload-map及每段全部实际标签 | 剧本、镜头、实图及style原文 |

下游发现不一致先定位到镜号/源版本，回正确上游修复，再同步，不各自补出不同剧情。与当前视频无关的共同文件变更可记录检查证据后沿用，不能只刷新哈希掩盖实际过期。

## 旧稿继续

先核实际文件与内容，不根据文件名或最新修改时间猜版本。旧screenplay/materials/shots/board-prompt/generation-packet可映射到新职责，齐备同版直接使用。仅在继续导演设计、修改镜头或缺字段确实影响本次工作时，将旧shots在新版本补成双表，共享字段必须一致；只调整上传顺序/标签不触发格式迁移。已有合格正式板与采用镜头时不倒退强制重画25格预览；记录预览在历史制作中未使用即可。

历史teacher_next等课程字段不删除、不写进视频音轨，由studio读取；现有classroom_playback交课程总入口维护，视频模块只提供实际成片、逐字稿、结束状态和媒体检查。不要因Skill升级重写真实课程或登记新的用户采用。

## 现有执行器

共用状态仍是[studio项目协议](../../math-courseware-studio/references/project-contract.md)。无generate-video/video-register/video-package命令，不将manifest传给只支持既有权威JSON的record-change。

在已有课程中，用现有state.register_artifact(project, id, path, dependencies, metadata)登记已存在文件；dependencies引用实际V/E/M/资产ID和源路径，metadata保存source_versions和真实状态。没有课程执行器的单独视频只维护清单，不声称已自动登记。

status/validate能核登记哈希，不能证明导演语义、实图质量、声音、时长或播放正确；另读来源哈希及真实输出。共同事件/数学的修改由plan通过现有impact/record-change保存历史并同步课程；纯技术进度只更新视频记录，避免共同故事反复失效。

collect当前不收视频。单独视频按明确清单复制到普通交付文件夹、核对来源与副本哈希；不因注册artifact就称已打进课件。课程回填、教师接话和课堂播放交[studio衔接](../../math-courseware-studio/references/video-integration.md)。

更新HANDOFF时写当前视频/版本/路线、完成文件、实际检查与采用依据、缺项、依赖变化、下一步；用户说继续时从最早受影响或未完成步骤续作。
