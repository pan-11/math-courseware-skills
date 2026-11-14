# ToAPIs 生图配置

新建 API 生图任务默认使用 ToAPIs 的 `gpt-image-2-vip`、`quality: low` 和 `resolution: 1k`，横版课件使用 16:9。准备任务无需配置文件或凭据。使用内置生图时，从当前宿主选用实际可用的生图工具。

## 可选工作区设置

可在安装 Skill 的工作区根目录下设置 `tools/image-api-settings.json`。源码仓库直接使用 `skills/` 时，以仓库根为工作区。Codex 或 WorkBuddy 项目级安装时，以 `.agents/skills/` 或 `.codebuddy/skills/` 所在项目为工作区。配置字段均可省略，未设置的字段使用默认值。

```json
{
  "provider": "toapis",
  "base_url": "https://toapis.cn",
  "model": "gpt-image-2-vip",
  "quality": "low",
  "resolution": "1k"
}
```

大陆接入地址为 `https://toapis.cn`，国际接入地址为 `https://toapis.com`。以课程或单个任务为范围时，在 `image-prepare` 的整批选择或单任务中填写 `api_options`，可设置 `model`、`quality` 和 `resolution`。单任务优先。显式高清请求取 4K，单任务另定分辨率时按单任务设置。

## 执行与恢复

`image-run` 或 `image-resume` 可显式使用 `--key-file` 指向项目外凭据文件，或用 `--key-stdin` 读取标准输入。也可在工作区配置中添加 `key_file` 指向项目外文件，或使用 `TOAPIS_API_KEY`。在已通过适用的付费授权与额度检查后才读取凭据。配置仅保存文件路径，密钥值不得进入配置、课件记录或日志。

参考图先按 ToAPIs 上传接口提交本次生成所需的图片，生图接口接收参考图 URL。以实际生成结果检查画面、宽高和参考对应。已取得任务 ID 的任务使用原服务商和原地址查询并下载，提交结果未知时保留现状供核对。旧 Grsai 批次按原协议恢复。

参考官方 [GPT Image 2 VIP 生成接口](https://docs.toapis.com/docs/en/api-reference/images/gpt-image-2-vip/generation)、[上传图片](https://docs.toapis.com/docs/en/api-reference/uploads/images)与[查询图像任务](https://docs.toapis.com/docs/en/api-reference/tasks/image-status)。
