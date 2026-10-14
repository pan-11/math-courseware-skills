# 本地排版工具自动调用

图文笔记中的课件实页展示图复用用户已配置的本地 [xiaohongshu-ppt-layout-tool](https://github.com/pan-11/xiaohongshu-ppt-layout-tool)，支持原工具排版1—4。默认整组的第1篇用排版1，第2篇由AI按内容从2/3/4中选一种，第3篇用原图文说明卡，见[整组分配与选版标准](note-planning.md)。艺术封面、第三篇说明卡和两篇视频资料沿各自规范。原模板不复制、不改写，加载后直接调用其现有`xhsLayoutAutomation.render`。

## 模板与真实分组

| 工具版式 | 任务`template` | 原模板的输出方式 |
| --- | --- | --- |
| 排版1 | `watermark` | 每张右侧最多3页大图、左侧10个缩略槽；大图依输入顺序推进，缩略图按原规则取后10页或循环。最多36个输入页，避免模板12张上限静默截断 |
| 排版2 | `product` | 首张用前2页；之后每5页一张“1大＋4小”图。1200×1600，传本篇实际标题；仅1页时模板首图重复该页，尾组缺图时原模板显示占位 |
| 排版3 | `direct-133-33` | 7页及以上先出“1大＋3＋3”总览，从第8个输入起每3页细看；不足7页只生成每3页细看图 |
| 排版4 | `direct-1222-3-3` | 7页及以上先出“1＋2＋2＋2”总览，随后从第1个输入起每3页细看；不足7页只生成细看图 |

这些“第几页”指输入顺序，源PPT页码另由`slide`记录。排版1的重复缩略图、排版2的单页重复不代表多出课件页。制作时按主题选择真实页，不为凑版式造页；排版1超36页需要缩小实际选页范围，入口会明确报错。第2篇采用排版2时优先选择完整的2＋5n个合适页面，出现占位且无法补足真实相关页时选3或4。原模板称“封面页/首图”的图在笔记中仍是内容图，艺术封面另按原规范完成。

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

在本课`中间文件/notes/vNNN`先约定目录，再为前两篇分别写任务JSON和不同输出目录。相对路径以任务JSON所在目录为基准。`images`数组就是排版顺序，不自动按文件名排序；`slide`必须是本课源PPT中唯一的正页码。可附图片`sha256`约束已核版本。真实课任务应填写`source_pptx`用于记录原PPT哈希；合成测试可省略。新任务明确写`template`；旧任务省略时继续按排版4，避免破坏已验证用法。下面保留排版4完整示例：

```json
{
  "template": "direct-1222-3-3",
  "source_pptx": "../../../最终产品/lesson.pptx",
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

上述三个页码仅示范格式，实际由本课主题决定。各版式的`config`不同，不把排版4参数机械套到其他模板：

- 排版1：可用`bgColor`、`fitMode`、`watermarkText`、`watermarkEnabled`；默认白底、等比、空水印且关闭。宽度和间距由原模板固定计算，不接受`width/gap`。适配器显式关闭原模板“ 双击编辑 ”示例文本框，不读取个人预设。
- 排版2：必填非空`title`，如`{"title":"本课三个关键活动","fitMode":"contain"}`；可选`subtitle`、`bgColor`、`barColor`、`accentColor`。输出固定1200×1600，标题置于两页之间，不接受`width/gap/watermarkText`。原生`settings.fit`由入口设为contain，避免裁掉页面。
- 排版3、4：参数同上方完整示例，默认宽1242；排版3间距默认18、排版4默认10。宽度至少720，间距为大于0且小于宽度四分之一的整数。两原模板都对0间距回退，因此入口拒绝0，避免参数与结果不一致。

所有模板都要求`fitMode=contain`。水印只使用用户提供或已采用的文字；排版1需同时设置`watermarkEnabled: true`，未指定时留空且关闭。任务中的规范参数保存在`config`，实际传给不同HTML的原生参数保存在`render_config`，二者均进入渲染记录。

```text
python <Skill目录>/scripts/render_layout_tool.py <本课绝对路径>/layout-job.json
python <Skill目录>/scripts/render_layout_tool.py <任务JSON> --settings <本机设置JSON>
```

## 输出与检查

- 按上表各模板实际分组检查页序和总数，尤其排版3不重复放大前7页、排版4会完整细看。缺槽、原有缩略重复和主图/缩略图都以实际记录为准。
- 四种模板均输出JPG，保留原版式和页面等比完整显示，不改扩展名冒充PNG或拉伸成3:4。排版2首张`lead`、排版3/4的`overview`都是内容角色。
- `output_dir`必须是尚不存在的新版本目录，父目录已建立并声明用途，且不在外部工具目录内。入口先写AGENTS，再保存编号JPEG、`layout-request.json`和`render-manifest.json`；runtime保存隔离的Electron数据和真实执行返回，失败记录为`failure.json`。失败目录和旧图均保留，下次使用新目录。
- 成功清单逐图记录实际编码、尺寸、SHA256、原页码与角色；排版1另记`detail_slides/thumbnail_slides`，排版2记重复的`panel_slides`或`empty_slots`。同时记录输入页图、可选源PPT及原模板哈希；`PASS`仅代表渲染完整性检查，不代表数学、手机阅读或人工验收通过。
- 检查完整图与手机缩图，确认页序、完整条件、数字/单位、等比与可读性。合格后按原字节复制选用图片到`笔记素材/vNNN/note-NN`，内部参数/来源/运行记录留在工作区，交付检查引用对应工作区清单。
- 工具、模板或输入缺失时给出实际原因和已准备材料；不静默改用旧卡片脚本并称作工具输出，不要求重复批准已授权制作。

## 图文交付清单

原PNG内容卡仍用字符串路径；四种工具内容图使用显式对象。独立笔记可按需要混排，默认五篇整组则按已确认的三种图片路线分别交付。封面继续用原PNG、3:4规则。新类型必须匹配已支持模板的成功渲染记录中的某张输出，检查真实JPEG编码、尺寸和SHA256；复制或改名后也可核原字节。下面是单篇字段示例：

```json
{
  "notes": [{
    "id": "01", "topic": "本课一个具体教学问题", "format": "image",
    "cover": "note-01/00-cover.png", "copy": "note-01/copy.md",
    "cards": [{
      "file": "note-01/01-content.jpg",
      "kind": "courseware-layout",
      "render_manifest": "../../中间文件/notes/v001/layout-v001/render-manifest.json",
      "render_output": "01-pages-004-007-010.jpg"
    }]
  }]
}
```

此例的`delivery.json`位于`笔记素材/v001`，任务与输出位于`中间文件/notes/v001`；实际沿本课目录调整引用。默认整组另在顶层写`"series_profile": "three-image-two-video"`，放入按顺序的五篇：第1篇课件主体匹配`watermark`，第2篇主体匹配`product/direct-133-33/direct-1222-3-3`其中同一种，第3篇为原PNG卡；三篇可加入多张显式`teaching-companion`组合图，同一成品组合图可跨篇复用，不需要改本工具。第4/5篇为`video-cover-copy`（封面、标题、正文和话题；视频由用户制作）。历史或明确另需的`video-edit-kit`保持兼容。不同素材完整性规则见[文案与交付检查](copy-and-review.md)。

使用`check_delivery.py`检查整篇或整组，同时执行逐图目视与文案核查。交付当轮在聊天展示实际图、编号文件名、顺序和整包目录，并说明第2篇实际选用的版式和理由，不只保存文件或给总览链接。
