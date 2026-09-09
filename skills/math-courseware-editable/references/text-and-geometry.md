# 原生文字、字号和坐标

## 三份规划

1. `text-unit-plan.json`：从pages.text_units逐个列标题、题干、答案、步骤、标签。不可用OCR错字覆盖定稿。
2. `text-ownership.json`：哪些必须原生，哪些非教学图片细节保留栅格。关键数学标签不能因嵌在插画内就自动归为栅格。
3. `coordinate-plan.json`：回传页、原对象、文字框、实际字体字号、颜色、对齐、行距、边距、换行、独立数学对象映射与确认来源。

控制器逐字比较计划text与pages.text_units，禁止缺单元、多单元或重复。display_text只允许排版空白变化。一单元对应一个独立命名对象，题干与答案不共用一大框。

## 字体策略

默认KaiTi（楷体），显式东亚字体槽；不要替换成STKaiti（华文楷体）后仍称同字体。标题、核心算式、题干和辅助文字逐单元登记字号，优先依据确认图和课堂投屏校准。32pt执行缺省不是整套统一字号标准。

不自动缩字，保留`auto_shrink:false`。溢出先查文字框、边距、行距和布局，需改文案则回写上游。先做真实PPTX文字试样在WPS查看；HTML/PIL预演只辅助，不冒充原生字体效果。

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
  "mapping": {"P001": 1},
  "text_units": [{
    "page_id": "P001", "unit_id": "P001-T01", "text": "课堂真实标题",
    "box": {"x": 60, "y": 35, "width": 800, "height": 70},
    "font": {"family": "KaiTi", "east_asian": "KaiTi", "size_pt": 36, "color": "18334A", "bold": true},
    "paragraph": {"align": "left", "line_spacing": 1.2, "margin_pt": {"left": 0, "right": 0, "top": 0, "bottom": 0}},
    "auto_shrink": false
  }],
  "required_native_objects": [{"page_id": "P001", "object_id": "group-1", "shape_id": 5}],
  "review": {"confirmed": true, "evidence": "_state/editable/review-v001.json", "sha256": "确认文件实际SHA256"}
}
```

这是字段示例，不是实际批准。确认JSON含`confirmed:true/scope:editable-build/plan_sha256/reviewer/evidence_ref`，plan_sha256由`pptx_editor.plan_digest(plan)`计算（忽略最外层review）。evidence_ref保存用户对实际预览的确认依据，不由助手自检替代。

A路线为每单元补`target_shape_id`、`expected_text`和对象清单的`expected_geometry_sha256`；这些值来自回传原件。B不填target_shape_id，追加独立文本。必要数学对象按pages.native_objects的object_id逐个映射实际原生shape_id；缺少则先补，不假装自动恢复了图形。

## 验收与修改

执行editable-build，保存新文件及逐单元报告。回读文字、字体槽、字号、颜色、对齐、行距、边距、坐标；检查媒体、分组、裁切和叠放关系。原稿哈希必须不变，重跑不得叠字。用户已手调输出有变化时拒绝覆盖，重新基于那份实际文件规划。

把结构通过、视觉通过、WPS通过分别登记；静态图层检查不证明演示动画效果。完成后由用户在WPS设置动画，同时复核；若改了课件内容，登记变更并同步讲稿等文稿。
