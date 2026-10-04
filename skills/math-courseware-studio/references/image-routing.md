# 生图线路与执行证据

## 项目线路

`builtin`使用当次真实可用Codex生图工具；`openai_image_api`使用Grsai。新课首次选择一次，已明确指定则直接登记。所有角色、地点、道具、封面、试样、整页图、去字和返工继承当前项目线路，不静默改用另一条。

切换线路修改项目记录并说明范围，不重做已经确认的图片。内置与Grsai的参数、额度和证据分开处理。

## Grsai协议

依据服务商[旧接口文档](https://grsai.ai/dashboard/documents/gpt-image)和用户明确覆盖，2026-09-09核对：

- `https://grsai.dakka.com.cn`，生成`POST /v1/draw/completions`。
- 实际请求`model/prompt/aspectRatio/shutProgress`；参考图通过`urls`传真实URL或Base64，本执行器使用已保存参考图的Base64。
- 默认`gpt-image-2.5`和`1672x941`；用户明确4K/高清/高分辨率/终稿大图时`gpt-image-2-vip`和`3840x2160`。
- `shutProgress`是布尔true。内部`size`须与`aspectRatio`一致，不把未知size字段发给旧接口。
- 去字/修图继承源图实际像素；非横版资产可显式记录其他像素比例，不拉伸三视图。
- 查询`POST /v1/draw/result`，JSON为`{"id":"服务商真实任务ID"}`。成功码0，data含id/status/results；id本身不代表完成。
- 不混入`/v1/api/generate`的新字段，也不回退`/v1/images/edits`。

项目设置2.5不代表服务商已实测支持；如果返回不支持，保留实际错误状态并核对接口，不擅自换模型。

## 派发

selection格式：

```json
{
  "tasks": [{"purpose": "page", "target_id": "P007", "version": "v001"}],
  "high_resolution": false,
  "authorization_evidence": "当前批次正式生图的实际授权依据"
}
```

`image-prepare`检查当前定稿、真实参考文件及哈希后，写入`_state/jobs/<任务ID>/job.json`和`prompt.txt`及batch清单。page提示词从页面数据展开。asset/cover/test/repair传完整`prompt`；asset可指定`reference_assets`和`size`。选定单个需要的资产视角时先按同一asset版本的实际文件组织引用，不替换形象。

erase必须传`source_image:{path,sha256}`、`remove_texts:[文字]`、`preserve_elements:[必须保留的教学图形/场景]`；repair同样需要确认源图和完整修改提示词。数学刻度线、几何边界和分组数量必须保留，不能按“无文字”误删教学对象。

首次连接只准备一项`purpose:test`，不能和生产任务混批。完成一张后报告成功与否、耗时、实际尺寸、真实ID、SHA256、文件和evidence路径；不自动推进整套。

## 执行与密钥

CLI读取已有`GRSAI_API_KEY`环境变量，或显式`--key-file`指向项目外本机secret，或`--key-stdin`。不把密钥作为命令行值，不写项目、提示词、任务、报告、日志或聊天。运行时不提供自动配置/修改密钥功能。需要新配置时遵守用户的独立授权边界。

运行`image-run --batch FILE`；已有任务运行`image-resume --batch FILE`。每批最多6路，默认单任务500秒；长批次让工具返回后台会话并持续向用户汇报，不能让同一任务重复提交。

内置线路由Codex读取该任务和实际参考图，按当前imagegen工具规则执行；脚本不能代替工具调用。真实结果JSON含`job_path`、`input_digest`、`image_path`、`tool_evidence`及工具实际返回的可选ID，执行`image-register`。本地编号不能冒充服务商或工具调用ID。

## 状态和检查

- `pending`尚未提交；resume不会自动提交这些任务。
- `submitting`进程中断或提交超时无ID→`submission_unknown`，先查服务端记录，不自动重试扣费。
- 有ID→`running`，只查询该ID；有结果URL但下载失败→`download_failed`，只下载同一个结果。
- `downloaded`记录实际图像哈希/像素、真实URL和ID、请求配置、参考图、提示词与版本。尺寸不符明确标记，不伪装成请求尺寸。
- `downloaded`仍需视觉检查，不能自动批准。保存检查结论后，由用户确认将正确版本写入资产/页面记录。

如果用户提供了服务端查到的真实ID，先保存其依据，再把未知任务恢复为该ID的running状态并查询；禁止编造ID或创建同内容新任务掩盖未知状态。连续同类错误先核对协议或视觉方法，不靠反复生成碰运气。

## 自动队列共用选择与授权

有run时先读run-status的有效image设置，按[启动协议](../../math-courseware-autopilot/references/queue-contract.md)用run-configure记录本课实际改选；无run仍按原项目线路。image-prepare采用同一有效路线并绑定当前run；任务路线创建后不静默重写。API运行接受原有当批authorization_evidence，或适用于同run/真实课程模块范围/路线/用途的结构化授权；Grsai还需paid_generation:true，额外用途或未授权返工不能继承。仅选线路不等于授权费用。内置调用前由宿主按相同范围核对，登记不能追认工具调用。旧任务查询下载保持原线路及未知不重提规则。

同run累计图片上限默认60张，包含测试、封面、视频预览/正式板、资产、页面、去字、修图及返工；25格拼图算1张，4张独立封面算4张。API整批在请求前核量并在共享锁内预占，剩2张请求4张整批不执行；直接job入口同样检查。失败/未知/中断预占不退还、不自动重提，查询下载不重复计数。预占记录存在而job仍pending时先查实际服务端证据，不把pending当成从未发出。

内置为软上限：run-next按任务明确image_count或image_requests张数检查，宿主调用工具前核剩余；image-register只登记真实成功结果并按job/input去重。已生成超额图仍保存，记录超额并阻止后续新生成。没有image-reserve或内置预占凭据；未登记的直接工具调用及失败/未知内置尝试，Python无法硬拦截或完整计数。不得以此冒称请求前硬限额。

旧run没有预算时先run-configure记录limits.max_images和真实evidence，不扫描推算历史基线；run-status只读显示记账起点及旧用量未知。扩额保留原账，run-resume不解除额度阻塞。同run手动模式继续计数，无run手动保持原行为；已提交API仍可查询下载，真实内置结果仍可登记。
