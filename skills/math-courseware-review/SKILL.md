---
name: math-courseware-review
description: Independently review courseware analysis, teaching and math, images, video materials or deliveries against actual versioned sources. Use standalone or from the optional autopilot queue; reports never grant user adoption.
---

# 独立审核

可以单独审一份产物，也可接收[自动推进](../math-courseware-autopilot/SKILL.md)已建立的packet。独立审核不启用自动模式，不写用户采用，不改变课程文件。先读课程AGENTS/HANDOFF与[审核协议](references/review-contract.md)，确认当前范围及实际源文件。

以下派发与入库步骤由主持审核的主会话执行。**如果你已经是被派发的独立审核者，直接读取packet及原始材料，按第3步返回报告；不再次派发子代理，不写入库记录。**

1. 已有packet时核路径、版本和范围；单独审核时用`review-prepare`创建packet，输入真实producer_id、artifacts、sources、rubric和instruction。不要让用户填写JSON。依据原始资料、已采用内容和当前需求选择范围，不把制作自评当原始依据。
2. **调用全新、只读的独立子代理，不继承制作对话。** 只给本Skill/审核协议、packet和其中列出的原始产物/依据；请求实际阅读或看图，核每条criteria。不得给它预设通过结论、可疑问题答案或上轮作者解释。适用的项目约束仍有效，但不额外转交制作过程或自评。没有独立代理能力时保留pending，说明缺口，不能由制作者填一份报告冒充独立审核。
3. 审核者逐条返回pass、changes_required或unverified，含实际证据路径、位置/观察、具体修正建议或不能验证的原因。五类规则见协议；数学要实算，图片要实看，声音/动态/投屏没有实际证据就写未验证。已知数学错误不能因“整体还可以”通过。
4. 主会话原样保存真实审核者报告，填真实reviewer_id及packet绑定信息，调用`review-record`。报告必须逐项齐全、来源未变且与制作者身份不同；运行时从逐条结论计算总结果，不接受省略项或自报passed:true。
5. 向用户呈现具体问题和未验证项，区分“质量检查通过”和“用户采用”。自动模式由队列处理有限修改循环；单独审核按本次范围交报告，不擅自改文件或启动整课。修订后用新packet重审，不覆盖旧报告。

对新Skill本身做前向测试时，只允许隔离合成材料与测试目录；不让测试审核写入真实课程的采用或完成记录。文件哈希和身份字段用于追溯与完整性核对，不宣称能抵抗同磁盘权限的任意伪造。
