# 原生文字、字号和坐标

## 三份规划

1. `text-unit-plan.json`：从pages.text_units逐个列标题、题干、答案、步骤、标签。不可用OCR错字覆盖定稿。
2. `text-ownership.json`：哪些必须原生，哪些非教学图片细节保留栅格。关键数学标签不能因嵌在插画内就自动归为栅格。
3. `coordinate-plan.json`：回传页、原对象、文字框、实际字体字号、颜色、对齐、行距、边距、换行、独立数学对象映射与确认来源。

控制器逐字比较计划text与pages.text_units，禁止缺单元、多单元或重复。display_text只允许排版空白变化。普通单元对应一个独立命名对象；算式等需要逐项显示时用`segments`列出独立对象，每片含`object_id/text/box/font/paragraph/auto_shrink`，按序拼接text必须逐字等于原单元；不叠加重复整式文本。题干与答案不共用一大框。

原确认版式确实在多个区域重复同一句提示时，可对该单元使用`instances`（不与segments并用）；每个实例具有独立object_id和坐标，但每份text都必须逐字等于源单元，不能借重复排版新增内容。

## 字体策略

默认KaiTi（楷体），显式东亚字体槽；不要替换成STKaiti（华文楷体）后仍称同字体。标题、核心算式、题干和辅助文字逐单元登记字号，优先依据确认图和课堂投屏校准。32pt执行缺省不是整套统一字号标准。

不自动缩字，保留`auto_shrink:false`。溢出先查文字框、边距、行距和布局，需改文案则回写上游。直接整套回填后逐页检查真实PPTX渲染及WPS显示；内部字体校准不设用户试样确认。HTML/PIL预演只辅助，不冒充原生字体效果。`vertical_anchor`可显式取top/center/bottom。

## 几何契约

直接`box:{x,y,width,height}`单位为pt。1pt=12700EMU。
若用源图像素，提供`box_px`、`source_image_size:{width,height}`及回传页实际内容区`source_content_rect:{x,y,width,height}`，后者单位pt。

```text
目标x = 内容区x + 源框x / 原图宽 × 内容区宽
目标y = 内容区y + 源框y / 原图高 × 内容区高
目标w = 源框w / 原图宽 × 内容区宽
目标h = 源框h / 原图高 × 内容区高
```

内容区根据实际回传页及预览核对，不默认铺满整页。裁切/旋转/比例改变后重核坐标；不能用截图边界替代目标内容区。

## 回填计划

```json
{
  "source_deck": "editable/returned/真实哈希-source.pptx",
  "source_sha256": "源文件实际SHA256",
  "output": "editable/output/v001/lesson.pptx",
  "build_scope": "text-refill",
  "mapping": {"P001": 1},
  "text_units": [{
    "page_id": "P001", "unit_id": "P001-T01", "text": "课堂真实标题",
    "box": {"x": 60, "y": 35, "width": 800, "height": 70},
    "font": {"family": "KaiTi", "east_asian": "KaiTi", "size_pt": 36, "color": "18334A", "bold": true},
    "paragraph": {"align": "left", "line_spacing": 1.2, "margin_pt": {"left": 0, "right": 0, "top": 0, "bottom": 0}},
    "auto_shrink": false
  }],
  "required_native_objects": [{"page_id": "P001", "object_id": "group-1", "shape_id": 5}],
  "remaining_native_objects": [],
  "authorization": {"evidence": "_state/editable/authorization-v001.json", "sha256": "真实整套制作授权文件的SHA256"}
}
```

`review`仅保留兼容历史已审阅计划，不是当前必经确认。直接整套制作使用上例的`authorization`，不同时填写review。授权JSON必须含`authorized:true/scope:editable-build/source_sha256/page_ids/requested_by/user_instruction/evidence_ref`；保存本课真实整套制作原话、对应源文件及全部页ID，不宣称用户看过未来效果。plan_sha256仍由`pptx_editor.plan_digest(plan)`计算，忽略最外层review和authorization。授权绑定源文件/范围，输出仍核对实际计划哈希。

整套文字回填计划指定`build_scope:"text-refill"`，必须覆盖当前全部页面和文字；暂未满足独立对象要求的项目在`remaining_native_objects`逐项写`page_id/object_id/reason`。控制器核对缺口清单，报告为文字完成、图形粒度待处理；不得漏报或假写shape_id。省略build_scope仍为完整图层验收，必要独立对象缺失时拒绝完成。

A路线为每单元补`target_shape_id`、`expected_text`和对象清单的`expected_geometry_sha256`；这些值来自回传原件。B不填target_shape_id，追加独立文本。必要数学对象按pages.native_objects的object_id逐个映射实际原生shape_id；缺少则先补，不假装自动恢复了图形。

## 验收与修改

执行editable-build，保存新文件及逐单元报告。回读文字、字体槽、字号、颜色、对齐、行距、边距、坐标；检查媒体、分组、裁切和叠放关系。原稿哈希必须不变，重跑不得叠字。用户已手调输出有变化时拒绝覆盖，重新基于那份实际文件规划。

把结构通过、视觉通过、WPS通过分别登记；静态图层检查不证明演示动画效果。完成后由用户在WPS设置动画，同时复核；若改了课件内容，登记变更并同步讲稿等文稿。
