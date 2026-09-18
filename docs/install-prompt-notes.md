# 安装提示词适配说明

2026-09-18更新：源码已按批准方案拆为十二个Skill，视频由总入口和writer/assets/director/storyboard/prompts五专业模块组成。两份安装提示词核对全部十二目录与相对引用，旧0.2.1 ZIP不能替代。用户已另行授权同步到现有私有仓库；同步源码不代表其他项目安装副本自动更新，安装时仍需核对来源和manifest。下文版本记录保留历史含义。

2026-09-15更新：0.2.1加入通用公开课封面设计规范，并区分封面与知识页的密度要求。两份安装提示词增加封面规范文件及入口引用核对，避免从旧0.2.0包安装后误认为已经获得新规则。当前项目直接读取源码时生效，其他项目的独立安装副本需按已有manifest更新；更新GitHub源码不等于自动更新这些副本。0.2.0及下方记录作为历史保留。

2026-09-12更新：0.2.0已增加math-courseware-video，现为七个相邻Skill目录。两份安装提示词同步模块数量、视频入口与版本预检；若GitHub来源还不含视频，使用完整0.2.0 ZIP，不把旧版装成新版。本轮仅更新本地提示词与交付包，没有执行安装或推送。下文2026-09-10记录保留为首版适配依据。

Date: 2026-09-10

用户粘贴的原版Codex与WorkBuddy提示词内容相同。新包使用六个相互引用的Skill目录，不能原样替换仓库地址后继续使用旧名称、四阶段口令或inputs/outputs/tmp骨架。

本次交付两份可分别完整复制的提示词：

- [Codex版](install-codex-prompt.md)：项目级安装到.agents/skills，识别后使用$math-courseware-studio，也提供文件路径入口。
- [WorkBuddy版](install-workbuddy-prompt.md)：项目级安装到.codebuddy/skills，通过当前客户端的技能选择或文件路径入口使用；按Grsai执行器说明后续生图，不假定Codex专用工具可用。

两者都将原仓库保存于工作空间tools/math-courseware-skills，再将六个完整目录成套同步到宿主的项目级路径。安装记录和旧文件哈希保留于tools，课程后续单独放在projects。更新预检同时检查源仓库和实际安装副本；不删除或覆盖已有用户内容。ZIP可离线安装，但不能把未知commit或离线版本称为GitHub最新版。

当前仓库经GitHub API核对仍为private=true，默认分支main。其他人需要自己的仓库访问权限，或由鹿鸣另行提供完整ZIP。编写提示词没有更改仓库可见性、邀请人员或发送文件。

## 官方依据与实际范围

[OpenAI官方Skill文档](https://learn.chatgpt.com/docs/build-skills)说明仓库级发现目录.agents/skills，以及Codex CLI/IDE的$提及方式。当前桌面客户端的实际识别情况仍需检查，不能仅凭目录存在认定宿主已加载。

[WorkBuddy项目文档](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Project)说明.codebuddy/skills项目级配置。web打开该页失败后，通过只读HTTP读取正文核对了这一具体字段；未以搜索摘要代替正文核查。[WorkBuddy技能文档](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)说明技能导入和启用方式。本方案不要求使用可能改变用户级配置的全局导入。

本次没有在Codex或WorkBuddy执行安装，也没有修改六个Skill及运行时。WorkBuddy没有真实课件验证记录；提示词只能安排安装、环境检查和能力适配，不能保证全流程通过。

检查范围：六个真实目录及共享脚本存在、两份提示词自包含、宿主路径不同、旧命令未被当成新包入口、依赖和私有源说明齐全、没有复制作者本机路径或凭据。提示词可用于新安装和安全更新，不是已经执行的安装记录。
