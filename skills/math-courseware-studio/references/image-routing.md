# 生图线路与执行证据

## 项目线路

`builtin`使用当次真实可用Codex生图工具；`openai_image_api`是API线路，服务商另以`provider`选择`grsai`或`duomi`。旧项目/任务未写服务商时兼容为Grsai。新课首次选择一次，已明确指定则直接登记。所有角色、地点、道具、封面、试样、整页图、去字和返工继承当前项目线路，不静默改用另一条。

切换线路或API服务商修改项目记录并说明范围，不重做已经确认的图片。内置与各API服务商的参数、密钥和执行证据分开处理；切换服务商不重置本课累计图片额度，也不继承另一服务商或显式改选模型前的付费授权。以下API参考图增强只适用于`openai_image_api`，不改变`builtin`提示词、参考图组织、工具调用或登记行为。

## API参考图与整页流程

PPT页与视频素材共用本课同一套已采用角色、场景、道具和风格图片。写每页/本镜头画面时同步明确实际出现的对象及参考职责，由宿主在现有`asset_refs`或任务`reference_assets`中登记资产ID和版本；不搜索提示词中的名字猜选图，也不另建素材库。首次创建原创母版可以没有前置参考；已有形象的衍生图及依赖页面必须登记需要继承的真实图片，不能仅加外观文字替代附件。

按当前画面需要选图；参考图少且整组都适用时可以直接传入整组。参考图中的其他人物不代表本页登场。角色身份、地点结构、道具外形和风格各说明用途；风格/样页参考不默认继承其中题目、文字和构图。每张图片的编号必须对应实际上传顺序，提示词写明“图N”的资产、版本、视角及职责。上一张候选图不能自动替换已采用母版。

准备及发送前只做技术检查：引用版本、文件与哈希可用、视角存在、附件及顺序正确、协议支持。缺少已声明必需图片或接口不支持输入时停止并报告，不能丢图后退回纯文字生成。图像效果由用户亲自检查；本次增强不增加自动视觉评分、跨媒体审核或额外确认节点，也不把技术检查通过当作用户采用。

保持“完整带字整页图→全部去字→完整有序PPT/PDF→可画拆层回传→忠实回填”。API去字仅把本页已采用带字源图作为唯一图片输入，沿用源图真实像素和明确的去除/保留说明，不附加角色、场景、风格图重新组织画面。不加入素材拼装或先做局部可编辑的步骤；内置去字仍按原行为执行。

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

## 多米协议

2026-11-03核对用户提供的[多米官方文档](https://s.apifox.cn/b924931e-29c0-4127-b025-d68c90285060)，API服务商值为`duomi`：

- 生成`POST https://duomiapi.com/v1/images/generations?async=true`，`Content-Type: application/json`，`Authorization`直接传原始密钥，不加`Bearer`。
- `model`支持`gpt-image-2`（默认）、`gpt-image-2.5-flare`、`gpt-image-2.5-sunburst`；`prompt`最多5000字符，包含自动展开的参考图用途。超限停止，不截掉题目或附件说明。
- 实际请求使用`model/prompt/size/quality/background`；普通`quality:medium`，高清`quality:high`，`background:auto`。普通尺寸`1792x1008`，高清`3840x2160`；宽高须为16的倍数且各在16至3840，总像素655360至8294400。去字/修图继承源图尺寸，源图不符合接口限制时报告，不擅自缩放或重排。
- 参考图使用`image`数组，按job附件顺序传实际图片。本地参考文件保存`path/sha256`；没有多米URL时，按图片真实格式把原始字节编码为`data:image/...;base64,...`，不压缩、缩放或上传图床。文件缺失、格式损坏或哈希变化时在生成前停止，不退回纯文字。
- 同一文件记录可明确填写`provider_urls:{"duomi":"实际可访问的HTTPS图片URL"}`，此时保留URL输入；执行前不带API鉴权读取URL，核对返回图片字节与本地SHA256一致。显式URL无效、不可访问或哈希不符时停止，不悄悄改用Base64。URL须指向同一张实际图片，不能只是一个同名网页。
- 创建响应保存真实`id`；查询`GET https://duomiapi.com/v1/tasks/{id}`，使用相同鉴权。`state`为`pending/running/succeeded/error`，成功结果图在`data.images[0].url`。仅拿到ID不代表完成。

官方文档明确展示URL；2026-11-03经用户授权的单次实测另证实：`gpt-image-2`接收2416字节的PNG data URI，输出保留了仅在参考图中出现的形状、数量、颜色和相对位置。该结果不证明其他模型/格式、大图、多参考图或整课一致性的实际表现；不承诺未查证的图片数量或请求大小上限。只拿到任务ID不算参考图生效。本接口接入不包含视频生成，不同服务商的字段、错误和任务ID不混用。

## 派发

selection格式：

```json
{
  "tasks": [{"purpose": "page", "target_id": "P007", "version": "v001"}],
  "api": {"provider": "duomi", "model": "gpt-image-2"},
  "high_resolution": false,
  "authorization_evidence": "当前批次正式生图的实际授权依据"
}
```

`api`只用于API线路；无run的手动任务可在此明确服务商/模型，否则沿项目配置，未配置服务商的旧记录仍为Grsai。有run时沿有效image偏好，不能用手动selection绕过当前服务商选择和授权。准备后服务商/模型属于该job输入；恢复旧job不按项目后来的选择重写。

`image-prepare`检查当前定稿、真实参考文件及哈希后，写入`_state/jobs/<任务ID>/job.json`和`prompt.txt`及batch清单。page提示词从页面数据展开。asset/cover/test/repair传完整`prompt`；asset可指定`reference_assets`和`size`。

API参考选择复用`asset_refs`和`reference_assets:[{"asset_id":"CHAR001","version":"v001","views":["front"]}]`；`views`可省略，省略时传该资产已登记且适用的全部`files`，需要子集时明确填写其实际`view`名称，不能用猜测名称。列表非空、无重复；同一资产不能混用版本。权威记录中的资产顺序在前，任务补充资产在后；任务不能删掉权威记录已明确要求的视角。双方均指定视角时保留权威视角并追加任务新视角；仅任务指定则采用任务视角顺序，同视角内沿`files`顺序。最终附件按此顺序编号，职责从资产`kind/fixed_features`及文件`view`展开，不引入另一份角色设定。无需继承共享对象的页面允许空`asset_refs`，但实际有共享对象时宿主须完整登记。

erase必须传`source_image:{path,sha256}`、`remove_texts:[文字]`、`preserve_elements:[必须保留的教学图形/场景]`；API erase不带额外资产附件，多米默认把该源图原始字节编码为Base64，也可在`source_image`中明确提供同图的`provider_urls:{"duomi":"实际HTTPS图片URL"}`。repair同样需要确认源图和完整修改提示词。数学刻度线、几何边界和分组数量必须保留，不能按“无文字”误删教学对象。

首次连接只准备一项`purpose:test`，不能和生产任务混批。完成一张后报告成功与否、耗时、实际尺寸、真实ID、SHA256、文件和evidence路径；不自动推进整套。

## 执行与密钥

CLI按job服务商读取已有`GRSAI_API_KEY`或`DUOMI_API_KEY`环境变量，或显式`--key-file`指向项目外本机secret，或`--key-stdin`。不把密钥作为命令行值，不写项目、提示词、任务、报告、日志或聊天。运行时不提供自动配置/修改密钥功能。需要新配置时遵守用户的独立授权边界。

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

有run时先读run-status的有效image设置，按[启动协议](../../math-courseware-autopilot/references/queue-contract.md)用run-configure记录本课实际改选；无run仍按项目线路及API配置。image-prepare采用同一有效路线/服务商/模型并绑定当前run；任务输入创建后不静默重写。API运行接受原有当批authorization_evidence，或适用于同run/真实课程模块范围/路线/服务商/显式模型/用途的结构化授权；所有API服务商均需paid_generation:true，额外用途或未授权返工不能继承。仅选线路、服务商或模型不等于授权费用；未显式设置模型时保留该服务商原有默认/高清策略。内置调用前由宿主按相同范围核对，登记不能追认工具调用。旧任务查询下载保持原线路/服务商及未知不重提规则。

同run累计图片上限默认60张，包含测试、封面、视频预览/正式板、资产、页面、去字、修图及返工；25格拼图算1张，4张独立封面算4张。API整批在请求前核量并在共享锁内预占，剩2张请求4张整批不执行；直接job入口同样检查。失败/未知/中断预占不退还、不自动重提，查询下载不重复计数。预占记录存在而job仍pending时先查实际服务端证据，不把pending当成从未发出。

内置为软上限：run-next按任务明确image_count或image_requests张数检查，宿主调用工具前核剩余；image-register只登记真实成功结果并按job/input去重。已生成超额图仍保存，记录超额并阻止后续新生成。没有image-reserve或内置预占凭据；未登记的直接工具调用及失败/未知内置尝试，Python无法硬拦截或完整计数。不得以此冒称请求前硬限额。

旧run没有预算时先run-configure记录limits.max_images和真实evidence，不扫描推算历史基线；run-status只读显示记账起点及旧用量未知。扩额保留原账，run-resume不解除额度阻塞。同run手动模式继续计数，无run手动保持原行为；已提交API仍可查询下载，真实内置结果仍可登记。
