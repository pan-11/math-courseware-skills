# 本地排版工具自动调用

图文笔记中的课件实页展示图默认复用用户已配置的本地 [xiaohongshu-ppt-layout-tool](https://github.com/pan-11/xiaohongshu-ppt-layout-tool)，首版支持排版4 `direct-1222-3-3`。艺术封面、教学解释卡、配套关系卡及视频素材按各自规范制作；不拿拼图代替这些内容。原模板不复制、不改写，加载后直接调用其现有 `xhsLayoutAutomation.render`。

## 本机定位

使用已有Python 3.11+、Pillow及排版工具开发目录中的Electron，无须网络服务。Windows默认查找工具目录内`desktop/node_modules/electron/dist/electron.exe`；其他运行时可在本地设置中明确给出，但首版实际验证范围为Windows。单独一个打包EXE不等于可加载原模板的开发目录，不自动安装、下载或重建。

当前仓库默认读取已被Git忽略的`sources/xhs-layout-tool.local.json`，只保存本机路径。例如：

```json
{
  "tool_root": "D:/tools/xhs-layout-tool"
}
```

本文件的路径是示例，不是鹿鸣的实际地址。工具目录配置一次后各课沿用，先核路径和模板是否可读；不要让用户每篇重新填写。分发或安装到其他位置后，可用`--settings <本机设置JSON>`明确定位；JSON内可选`electron`指定已有运行时。一次调用也可用`--tool-root <工具目录>`覆盖默认设置。路径写在本机设置，不把个人绝对路径写进通用Skill或上传Git。

## 选页和任务

先核最终PPT的版本、页码和来源。复用该版本已有的准确页图；缺少时从最终PPT实际渲染，不把旧生图当成最终课件截图。按笔记主题选择页面并保留完整题干、数字、单位与图形；模板接收PNG/JPEG，不直接渲染PPTX。

在本课`02_work/notes/vNNN`先约定目录，再写任务JSON。相对路径以任务JSON所在目录为基准。`images`数组就是排版顺序，不自动按文件名排序；`slide`必须是本课源PPT中唯一的正页码。可附图片`sha256`约束已核版本。真实课任务应填写`source_pptx`用于记录原PPT哈希；合成测试可省略。

```json
{
  "template": "direct-1222-3-3",
  "source_pptx": "../../../03_final/lesson.pptx",
  "output_dir": "layout-v001",
  "images": [
    {"path": "page-exports/p004.png", "slide": 4},
    {"path": "page-exports/p007.png", "slide": 7},
    {"path": "page-exports/p010.png", "slide": 10}
  ],
  "config": {
    "width": 1242,
    "gap": 10,
    "bgColor": "#f3f3f3",
    "fitMode": "contain",
    "watermarkText": ""
  }
}
```

上述三个页码仅示范格式，实际由本课主题决定。水印只使用用户提供或已采用的文字；未指定留空。`contain`为必需条件，不允许铺满裁切。宽度至少720，间距为大于0且小于宽度四分之一的整数；原模板把0间距回退为10，因此入口拒绝0，避免参数与结果不一致。其余参数不提供时采用示例中的默认值。

```text
python <Skill目录>/scripts/render_layout_tool.py <本课绝对路径>/layout-job.json
python <Skill目录>/scripts/render_layout_tool.py <任务JSON> --settings <本机设置JSON>
```

## 输出与检查

- 7页及以上生成一张前7页总览，随后从输入第1页起每3页一张细看图；不足7页只出细看图。最后不足3页保留空位，不复制页面凑数。
- 首张“总览”是课件内容展示，不自动替换笔记的艺术封面。排版4依原模板输出JPG长图，保留等比完整显示，不改扩展名冒充PNG或拉伸成3:4。
- `output_dir`必须是尚不存在的新版本目录，父目录已建立并声明用途，且不在外部工具目录内。入口先写AGENTS，再保存编号JPEG、`layout-request.json`和`render-manifest.json`；runtime保存隔离的Electron数据和真实执行返回，失败记录为`failure.json`。失败目录和旧图均保留，下次使用新目录。
- 成功清单逐图记录实际编码、尺寸、SHA256、原页码与角色，并记录输入页图、可选源PPT及原模板哈希；`PASS`仅代表渲染完整性检查，不代表数学、手机阅读或人工验收通过。
- 检查完整图与手机缩图，确认页序、完整条件、数字/单位、等比与可读性。合格后按原字节复制选用图片到`04_notes/vNNN/note-NN`，内部参数/来源/运行记录留在工作区，交付检查引用对应工作区清单。
- 工具、模板或输入缺失时给出实际原因和已准备材料；不静默改用旧卡片脚本并称作工具输出，不要求重复批准已授权制作。

## 图文交付清单

普通PNG内容卡仍用原字符串路径；排版4内容图使用显式对象，可与普通卡混排。封面继续用原PNG、3:4规则。新类型必须匹配成功渲染记录中的某张输出，检查真实JPEG编码、尺寸和SHA256；复制或改名后也可核原字节。

```json
{
  "notes": [{
    "id": "01", "topic": "本课一个具体教学问题", "format": "image",
    "cover": "note-01/00-cover.png", "copy": "note-01/copy.md",
    "cards": [{
      "file": "note-01/01-content.jpg",
      "kind": "courseware-layout",
      "render_manifest": "../../02_work/notes/v001/layout-v001/render-manifest.json",
      "render_output": "01-pages-004-007-010.jpg"
    }]
  }]
}
```

此例的`delivery.json`位于`04_notes/v001`，任务与输出位于`02_work/notes/v001`；实际沿本课目录调整引用。使用原`check_delivery.py`检查整篇，同时执行逐图目视与文案核查。交付当轮在聊天展示实际图、编号文件名、顺序和整包目录，不只保存文件或给总览链接。
