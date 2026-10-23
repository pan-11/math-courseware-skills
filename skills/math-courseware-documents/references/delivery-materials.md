# 实际材料清单与交付检查

## 中文成品文件名

- 交给用户直接打开、编辑、打印的配套文件必须中文命名，包括Word/PDF、电子板书PPTX、单件PNG、打印版、尺寸表和使用说明；中文网页标签不能代替实际中文文件名。
- 文稿使用`《课题》教学设计.docx`、`《课题》教学逐字稿.docx`、`《课题》说课稿.docx`、`《课题》学习任务单.docx`，同源PDF使用同名；板书用`《课题》电子板书.pptx`、`《课题》板书打印版（A3）.pdf`等明确名称。贴片可保留顺序号，如`01_课题.png`；规格A3/A4、扩展名及必要编号可保留。用户明确指定其他名称时按其最新要求。
- 内部逻辑角色、脚本、制作源稿、版本目录及状态/审核记录仍可英文；`AGENTS.md`等工具固定名称不受此成品要求影响，不把内部文件作为用户主交付。
- 改名或生成中文交付副本时，同步HTML相对引用、下载属性、说明文字、清单路径与实际哈希；内部源路径与历史审核仍指向原件，不全局替换旧记录。旧版本保留，交接和当前入口指向中文版，不产生内容不同的两套“最新版”。
- 交付前核实际文件名、所有本地链接、下载名称及文档/图片的内容一致性；仅改名时通过同哈希证明正文与版式未变，无需重写或重新生图。

整课默认必交三教师稿（classroom-script、lesson-presentation、lesson-plan）、学生学习单（worksheet）、黑板贴（blackboard）及当前已承诺的互动（interactive）。同课实际资料仍按各专业规范制作与审核，程序检查文件存在、可读取及来源绑定，不证明教学质量或课堂时长。独立文稿/回填任务不因此扩成整课。

现有`workflow.stages.documents.files`或`delivery.files`可直接用角色名保存`{path,sha256}`；对应stage.source_versions须绑定当前`_state/pages.json`及存在的`stages.editable.files.pptx`。旧版本保留，但不能指向已过期课件的材料。互动承诺来自当前蓝图interactive_ids，或已采用story.interactive_nodes / pages[].interactive_ids；没有承诺不凭空加互动。

需要多个格式或离线依赖时，stage.files增加`materials-manifest:{path,sha256}`，实际JSON格式如下。所有路径在本课内，destination为交付包内相对路径，不允许上跳、绝对路径、隐藏或凭据文件。清单由真实已存在文件产生，不能先填占位文件冒充实物。

```json
{
  "schema_version": "1.0",
  "source_versions": {"_state/pages.json": "actual-sha256", "editable/output/current.pptx": "actual-sha256"},
  "roles": {
    "worksheet": [{"path": "documents/worksheet-v001/student.docx", "sha256": "actual-sha256"}],
    "blackboard": [{"path": "assets/blackboard-v001/electronic.pptx", "sha256": "actual-sha256"}, {"path": "assets/blackboard-v001/print.pdf", "sha256": "actual-sha256"}],
    "interactive": [{"path": "interactive/H001/index.html", "sha256": "actual-sha256"}, {"path": "interactive/H001/app.js", "sha256": "actual-sha256"}]
  }
}
```

完整包要把实际需要的JS/CSS、字体、图片和媒体都按原相对关系列入，collect只收明确清单，不扫描整课或浏览器profile。至少一份角色主文件须能读取：教师文本MD/DOCX/PDF，学习单DOCX/PDF，黑板贴实际PPTX/PDF/图片，互动实际HTML。其他格式仍须按专业规范补齐；一个有效文件不证明所有承诺格式已交，也不证明离线交互已实测。

只有用户真实省略时可设`waivers:{角色:{reason,evidence:{path,sha256}}}`；证据JSON含实际`user_evidence`、`waived_roles`及绑定当前课件的`source_versions`。助手不能以“还没做”填豁免，也不能把旧课指令借到新课。不为默认必交内容再问许可。

`collect`和整课最终检查同时核必交角色；当前缺项应继续制作，不把收集失败当成重新征求范围的理由。收集后的包仍需核链接、字体、打印尺寸、课堂任务一致性与真实适用放映。正式文稿的PPT完成门槛、视频未回传的草稿标识保持原规则。

独立文稿以当前`inputs.documents.files`为必需来源；更换输入路径也需要重新核对文稿，旧输入仍存在不代表当前有效。已明确选择的角色文件（包括清单列出的多个格式）优先于历史export登记，旧稿保留但不混入新包，也不因未选中的旧登记过期而阻塞交付。

最终`delivery.files.manifest`须指向可解析的JSON：可直接使用collect的`artifacts`（每项含原件path、实际delivery_path、sha256及source_versions），也可使用`files`映射/数组（每项含实际副本path、sha256；原件通过source_path或顶层source_versions的同哈希文件对应）。完成检查逐个核实际副本，并核当前材料是否齐全、是否与当前原件一致；纯文字清单不能表示已核验。H23最终审核版本覆盖实际清单和副本；先完成包与清单，再保存引用它们的显示/播放检查记录，避免自引用。
