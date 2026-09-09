# 已有分层 PPTX 回填探针

更新：2026-09-09。范围为 M0/M6 合成测试夹具，不是真实可画回传或真实课件验收。

## 实际证据

- 使用已安装的 OfficeCLI `1.0.148`，先查阅 `help pptx add shape` / `help pptx set shape` / `help pptx shape`；旧环境记录的 `1.0.106` 不代表本次版本。
- 使用 Codex bundled Python 3.12、python-pptx 仅制作输入夹具，PIL 仅制作测试色块图片。执行器不用 python-pptx 重存原包。
- 夹具包含全页图片、独立裁剪图片、原生文本、含两个独立数学方块的组合、叠放顺序和未识别 `customXml/retained.xml` 部件。
- 实际 CLI 对副本执行 `set` 更新已有标题、`add --type shape` 增加独立文字、`save`、`validate`，文本回读正确，原件 SHA256 不变。
- 新增文本使用 `font=KaiTi`、`font.ea=KaiTi`、`autoFit=none`，测试直接检查东亚字体槽和 `a:noAutofit`。
- 原有非目标对象结构哈希、组合成员、裁剪、叠放顺序保持；所有未修改 slide XML 以外的 ZIP 部件逐字节一致，包括媒体、关系、母版、主题和未知部件。
- 通过完整 plan 哈希绑定人工确认材料；重复运行不增加对象；手工改变输出后再次运行拒绝覆盖。

最新验证命令：

```powershell
& 'C:/Users/sansh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest discover -s tests -p test_pptx_editor.py -v
```

结果：最终回归 10/10 通过，26.910 秒（上一轮同生产代码 27.265 秒）。包含真实 CLI 更新/新增、幂等、防覆盖、源文件变更、正文不符、目标冲突、重复单元、越界页码、缺少独立数学对象、确认过期、绝对 OPC 关系路径、完整字体段落回读、未知字段拒绝、源图像素到内嵌幻灯片内容区映射等断言。

本次干净普通回填产物在 `tests/runs/pptx-20260909-215400-bac44a38/editable/output/result.pptx`；白色粗体居中及边距回归在 `tests/runs/pptx-20260909-215354-1542fc93/editable/output/result.pptx`；绝对关系回归在 `tests/runs/pptx-20260909-215347-55fe67a3/editable/output/result.pptx`。各自同名 `.report.json` 包含证据工作目录和规范化 font/paragraph 数据。相邻的 `pptx-20260909-215407-29d58240` 是故意改坏输出以验证防覆盖的测试，不能作为成品使用。所有运行目录保留，不自动清理。

## API 与数据契约

实现：`skills/math-courseware-studio/scripts/runtime/pptx_editor.py`。

- `inspect_deck(path)`：返回页宽高（pt）、按实际演示顺序的 `slides`（1 起始索引）、部件名、递归 shape ID/name/type/text、显式字体槽/字号、EMU 几何及哈希、父组合 ID、裁剪、媒体及所有 ZIP 部件 SHA256。字体信息不是主题继承后的最终视觉字体。
- `import_deck(project, deck, mapping)`：`mapping={"P001":1}`；不同 page_id 不得绑定同一页。复制到 `editable/returned/<sha256前12位>-<原名>`，返回包含 `source_deck` 相对路径、mapping 和库存的 JSON，并保存 `.inventory.json`。既有导入副本变更时拒绝覆盖。支持相对关系和 `/ppt/slides/slide1.xml` 这种合法包内绝对 OPC 关系。
- `plan_digest(plan)`：按 UTF-8、键排序、紧凑 JSON 计算 SHA256，忽略最外层 `review`。
- `build_editable(project, plan)`：仅在确认校验通过后操作副本，返回并保留 `.report.json`；失败的工作目录不删除，不能当作通过的输出。计划与库存快照保存在工作目录。

计划最小形式：

```json
{
  "source_deck": "editable/returned/<hash>-source.pptx",
  "source_sha256": "<完整文件哈希>",
  "output": "editable/output/lesson-v1.pptx",
  "mapping": {"P001": 1},
  "review": {"confirmed": true, "evidence": "_state/editable-review.json", "sha256": "<确认文件哈希>"},
  "text_units": [{
    "page_id": "P001", "unit_id": "title",
    "text": "一共有5个", "display_text": "一共有\n5个",
    "box": {"x": 60, "y": 45, "width": 750, "height": 100},
    "font": {"family": "KaiTi", "east_asian": "KaiTi", "size_pt": 32, "color": "FFFFFF", "bold": true},
    "paragraph": {"align": "center", "line_spacing": 1.5, "margin_pt": {"left": 12, "right": 12, "top": 4, "bottom": 4}},
    "auto_shrink": false
  }],
  "required_native_objects": [{"page_id": "P001", "shape_id": 5}]
}
```

确认文件必须为 JSON，含 `confirmed:true`、`scope:"editable-build"`、`plan_sha256`、非空 `reviewer` 和 `evidence_ref`。真实确认引用必须来自鹿鸣实际审阅；执行器不能仅凭 `confirmed:true` 代替真实批准。测试的 reviewer/evidence_ref 明确标记 synthetic，不能进入真实课件。

A 路线在单元中增加 `target_shape_id`、`expected_text` 和库存提供的 `expected_geometry_sha256`，只允许顶层原生文本对象，拒绝原文/坐标冲突。B 路线省略 target_shape_id，追加独立对象。两者均命名为 `mcw:<page_id>:<unit_id>`，一单元一目标。

文字必须与逐页权威文本一致；`display_text` 只允许空白/换行变化。外层控制器负责将 plan 的 `text` 与 pages.json 定稿再次核对。字号默认 32pt 是执行器缺省，不代表所有版式适用；课件规划应显式给出确认字号。

规范 font 对象仅接受 `family/east_asian/size_pt/color/bold`，color 为六位 RGB（可带 #），bold 必须为布尔值。保留旧版 `font:"KaiTi",font_size:32` 写法，但不得与规范 font 对象混用 font_size。paragraph 仅接受 `align/line_spacing/margin_pt`；align 为 left/center/right/justify，line_spacing 是正数倍数，margin_pt 必须完整给出四边非负 pt。默认黑色、不加粗、左对齐、1 倍行距和零内边距。未知计划/单元/字体/段落字段或无法支持的格式在创建工作副本前拒绝，不静默丢弃。每一实际文字 run 的字族、东亚槽、字号、RGB、粗体，以及每段对齐、行距和文本体四边距均由最终 OOXML 回读核对。禁用自动缩字。

`box` 采用幻灯片 pt。另一种写法为 `box_px`（源图像素矩形）加 `source_image_size:{width,height}`（实际源图像素尺寸）及 `source_content_rect:{x,y,width,height}`（源图在目标幻灯片上实际占据的内容区，单位 pt）。公式为 `x_pt=content_x+box_x/source_width*content_width`，y 同理；宽高按对应尺寸比例转换。例：源图 1920×1080、目标内容区 `{x:50,y:60,width:800,height:450}`、像素框 `{x:24,y:48,width:900,height:90}`，得到 pt 框 `{x:60,y:80,width:375,height:37.5}`。目标内容区必须位于幻灯片内，像素框必须位于源图内；缺少实际尺寸即拒绝。旧版将 source_content_rect 解释为像素裁剪区的实现与实施计划不符，本次已纠正，旧计划须重新审阅，不能继续使用。

OfficeCLI 首次 Add 空 shape 后再 Set text 的实测不会形成文字 run；B 路线因此在 Add 时写入文字，显式 save 后才从磁盘读取新增 ID，再通过 Set 设置包括四边距在内的完整格式。该顺序已有真实 CLI 回归证据；四边 margin 的 `l,t,r,b` 写法按当前 help 仅用于 Set。

`required_native_objects` 校验既有原生 shape/connector/graphicFrame 存在，不自动重建数学图示。外层必须提供本课权威清单；缺失对象时拒绝构建。组合内既有独立对象可列入清单，但首版不支持直接回填组合内文字。

## 保层方法与未覆盖项

OfficeCLI 写工作副本后，执行器仅取回目标文本体/坐标变换，以及新增文本对象；其余 XML 沿用输入，最后按原 ZIP 文件清单写入新包。这样不会因第三方保存器处理未知扩展而使它们消失。源文件永远不写入。保留未知部件是包结构策略，不表示已理解其语义或确认所有外部软件都支持。

WPS 原生渲染、楷体换行效果、真实可画导出对象结构和 A/B 质量耗时：**未验证**。结构校验不能替代这些验收，也不能据此宣称首套真实课件可交付。没有启动可见 Office 应用、没有安装依赖、没有执行生图/公开发布/删除。
