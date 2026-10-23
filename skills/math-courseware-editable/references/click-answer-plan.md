# 原位点击答案阶段

忠实文字复原后，用本阶段实际制作原位答案及原生点击动画，并保留可恢复证据。原有 `faithful_restore` / `teaching_reveal`、A/B路线和实际采用记录保持原含义。宿主先核本次工作范围，复用真实制作指令；默认组合不新增模式选择或答案许可。

## 文件与职责

- 执行模块为 `runtime/click_answers.py`，接口是 `build(project, plan)` 与 `validate_final(project, manifest)`。
- `editable/output/lesson-click.pptx` 旁保存不可覆盖的 `lesson-click.plan.json` 和 `lesson-click.manifest.json`。每次制作尝试先建立独立工作目录规则，再保留命令、OfficeCLI工作副本、候选与日志，不自动删除。
- 源文件、不同计划的已有输出、已有计划和manifest均不得覆盖。同版输入可幂等返回；输入变化须使用新输出名。若中断发生在输出落盘之后、manifest写入之前，核实实际输出后补齐manifest，保持输出字节不变。
- 基础版由宿主登记为中间产物；仅 `validate_final` 返回 `ready_for_final: true` 后才能选择最终课堂版。manifest记录制作和结构证据，不能代替用户采用或实际放映。

## 计划 v1

```json
{
  "schema_version": "inline_answers_v1",
  "source_deck": "editable/output/lesson-base.pptx",
  "source_sha256": "SHA256",
  "output": "editable/output/lesson-click.pptx",
  "mapping": {"P001": 1},
  "source_versions": {
    "editable/output/lesson-base.pptx": "SHA256",
    "inputs/page-001.png": "SHA256",
    "inputs/answer-basis.json": "SHA256",
    "inputs/fabrication-instruction.json": "SHA256"
  },
  "request": {
    "user_instruction": "本次实际已有制作指令，不编造额外答案许可",
    "evidence_ref": {"path": "inputs/fabrication-instruction.json", "sha256": "SHA256"}
  },
  "pages": [{
    "page_id": "P001",
    "scan_complete": true,
    "reference_image": "inputs/page-001.png",
    "items": [{
      "blank_id": "Q1",
      "disposition": "answer",
      "source_basis": {"path": "inputs/answer-basis.json", "locator": "Q1"},
      "reason": "原作答空位有确定答案",
      "answer_text": "5",
      "derivation": "3 + 2 = 5，已与绑定来源的Q1核对",
      "box": {"x": 300, "y": 180, "width": 80, "height": 48},
      "click_order": 1,
      "components": [{
        "object_id": "Q1-number",
        "kind": "text",
        "text": "5",
        "box": {"x": 300, "y": 180, "width": 80, "height": 48},
        "font": {"family": "KaiTi", "east_asian": "KaiTi", "size_pt": 32, "color": "B3261E"}
      }]
    }]
  }]
}
```

所有映射页必须各有一份扫描记录；没有填空的页也写 `items: []`。每页必须有真实参考图；参考图、答案依据、源PPT及指令证据均须列入 `source_versions` 并核哈希。所有坐标使用幻灯片点值，组件不得超出声明的原空位。宿主仍须实际看图、找全空位并独立验算；文件锁定、非空推导和结构检查本身不能证明数学正确或视觉对应。

空位分为四类：

- `answer`：需要确定的 `answer_text`、来源及推导、原空位box、从1连续排列的页内 `click_order` 和组件。文字组件按序拼回答案；`bar`在逻辑文字中表示 `/`，所以分子/横线/分母对应 `1/2`，实际横线仍是可编辑原生细矩形。默认字体KaiTi、32pt、深红 `B3261E`；应按原图实际字号设置计划，覆盖值会被记录，禁止自动缩字。
- `open_blank`：具体说明开放或非唯一原因，保持留白，不产生对象或动画。
- `already_visible`：用 `existing_shapes` 绑定实际 `shape_id`，文字对象还须给完全一致的 `expected_text`。本阶段保留这些对象，不再次新增或添加隐藏动画。若源对象已有入口动画，不能谎报其为初始可见。
- `ambiguous`：记录具体未解冲突，不产生对象。其他确定答案可继续制作，但整份候选保持 `ready_for_final: false`。

非 `answer` 项不得夹带新组件、答案或点击序号。所有项均保留 `source_basis` 与 `reason`。执行器还会拒绝在已有同位同文的顶层文字上重复新增答案；组合图层或图片内部的可见答案仍须宿主实际检查，不能将程序未检出等同于不存在。

## 动画与核验边界

每个答案占一个普通单击组：首组件为入口 `appear/onClick`，其余组件为 `withPrevious`，所有组件同时出现并持续保留。新答案组追加在原主点击序列之后，原序列相对顺序保持不变。若追加位置不符合实际教学顺序，宿主应登记具体冲突并处理，不能把不合适的顺序判为最终完成。不能安全保留的复杂/交互时序会明确报错，原时间线不清空。

OfficeCLI只编辑保留的工作副本；最终从原ZIP定点回写新增对象与经过校验的时间线。实际读回XML核一个逻辑答案一个点击、分数组件同组、入口可见性与hold行为、原对象和时间线不变、其他ZIP部件字节不变。初始及累计答案状态登记为shape ID清单；它们是结构状态，不冒充实际渲染截图。验证末尾再次核源文件与输出、计划、manifest，拒绝验证期间的手调变化。

全页实际扫描后零答案有效：新输出与基础PPT字节相同，但有本阶段独立计划和manifest。只有开放题或原已可见答案时也不凭空创建点击对象。所有报告均明确 `playback: "unverified"`；原生结构和静态状态不能代替实际单击放映。

## 返回值与集成

两接口均返回 `output`、`output_sha256`、`manifest`、`manifest_sha256`、`plan_sha256`、`plan`文件ref、`source_deck`、`source_sha256`、`source_versions`、`ready_for_final`、`counts`、`pages`、`checks`、`playback`、`idempotent`。`validate_final`接收项目相对manifest路径或 `{ "path": "...", "sha256": "..." }`，重新载入不可覆盖计划并核实际源/输出XML。仅改manifest的ready标记或重算被改PPT的哈希，不能通过实际动画校验。

宿主先调用 `build`，再调用 `validate_final`，使用返回的文件和来源版本登记PPT与manifest，将唯一当前课堂入口指向该结果。有歧义项则不选为最终交付。用户后续明确要求纯复原或学生无答案版，由宿主的最终选择规则核真实指令处理，不通过伪造零答案扫描绕过。
