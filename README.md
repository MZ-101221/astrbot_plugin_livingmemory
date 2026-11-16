<p align="center">
  <strong>中文</strong> · <a href="README_en.md">English</a> · <a href="README_ru.md">Русский</a>
</p>

![LivingMemory：连接偏好、人物、计划与上下文的长期记忆](docs/public/images/livingmemory-cover.svg)

<p align="center">
  <a href="https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/"><strong>使用文档</strong></a> ·
  <a href="https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/webui"><strong>管理界面</strong></a> ·
  <a href="https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory/releases"><strong>版本下载</strong></a> ·
  <a href="https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory/issues"><strong>问题反馈</strong></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-52675c?style=flat-square" alt="Python 3.10 或更高">
  <img src="https://img.shields.io/badge/AstrBot-4.24.2%2B-52675c?style=flat-square" alt="插件视图需要 AstrBot 4.24.2 或更高">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-52675c?style=flat-square" alt="AGPL-3.0"></a>
</p>

## 让对话留下有用的记忆

LivingMemory 为 AstrBot 保存长期偏好、人物关系、项目进展和历史约定。它从对话中整理记忆，在需要时结合关键词、语义和图谱召回，并通过归档、衰减和访问强化管理记忆生命周期。

> **最新稳定版：2.13.0**<br>
> 管理界面默认外观升级为 macOS 26 液态玻璃，新增外观面板自定义，并把样式收敛为统一设计令牌；无命令、配置项与数据库结构变化，升级无需迁移。<br>
> [下载 2.13.0](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory/releases/tag/2.13.0) · [版本与升级](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/releases) · [历史版本](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory/releases)

## 从记住，到想起来

- **自动整理** — 达到配置的对话轮次后生成长期记忆；重要记录可保留原文，方便核验和重新总结。
- **按上下文召回** — 文档与图谱都支持关键词和向量检索，融合排序后结合会话、人格和生命周期筛选。
- **主动回忆与写入** — Agent 可调用 `recall_long_term_memory` 和 `memorize_long_term_memory`，按需读写长期记忆。
- **看得见、可维护** — 在官方插件视图中浏览 2D/3D 图谱、点击节点变焦并查看关联记忆，以及编辑记忆、测试召回、管理提示词和查看系统状态。

## 一个工作区，四种风格

**macOS 26 · 液态玻璃** 的浮动玻璃与壁纸，**Studio · 轻盈** 的柔和卡片，**Paper · 书页** 的暖纸色与衬线标题，或 **Terminal · 终端** 的等宽字体和仪表布局。

每种风格均支持浅色、深色与自动模式。点击管理页面的「外观与主题」即时切换，偏好保存在当前浏览器。放大图谱时标签保持稳定，手机端也能筛选会话、定位记忆和完成管理操作。

3D 图谱使用独立的暖光空间，支持旋转、缩放、节点聚焦和关联记忆查看；大量节点与关系通过 GPU 批量绘制。

[查看主题与操作指南 →](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/webui)

## 开始使用

1. 从 AstrBot 插件市场安装，或将指定版本的插件代码放入 `data/plugins/astrbot_plugin_livingmemory`。
2. 先在 AstrBot 后台「模型提供商 → 嵌入」中创建并启用 Embedding Provider（推荐免费的 `BAAI/bge-m3`，见[配置步骤](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/guide/embedding-model)），再重载 AstrBot 并在 LivingMemory 配置中填写其 ID 与 LLM Provider；Embedding 留空只会回退到第一个可用 Provider，容易选错或导致向量/图索引初始化失败。
3. 打开 `插件 → LivingMemory → 视图 → dashboard`（旧版 AstrBot 显示为 `Pages`）。插件视图需要 **AstrBot 4.24.2 或更高版本**。

测试版请从上方指定标签下载，具体安装及回退步骤见[版本与升级](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/releases)。已有数据时，升级前保留插件数据与配置备份。

发送几轮对话后，用 `/lmem status` 查看状态、`/lmem summarize` 手动总结、`/lmem search 关键词` 检查召回。

## 免费的嵌入模型

LivingMemory 的语义召回依赖 Embedding Provider，推荐硅基流动当前免费的 `BAAI/bge-m3`（1024 维）。在 AstrBot「模型提供商 → 嵌入 → 新增模型提供商 → OpenAI Embedding」中填写：

- Provider ID：保留 AstrBot 生成的值，如 `openai_embedding`
- API Base URL：`https://api.siliconflow.cn/v1`
- API Key：硅基流动控制台创建的密钥
- 嵌入模型：`BAAI/bge-m3`
- 嵌入维度：`1024`

保存并点击测试后，把该 Provider ID 填入 LivingMemory 的 `provider_settings.embedding_provider_id`。模型 ID 与 Provider ID 不同，完整说明见[嵌入模型与 BGE-M3](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/guide/embedding-model)。

## 本仓库的规划功能

本仓库在 2.13.0 基础上继续开发。原设计中的记忆作用域、取代链、用户档案、群共享与外部接口已由上游实现；本仓库补上剩余四项，全部以配置开关提供，默认关闭，升级后行为与 2.13.0 一致。

### 上游 2.13.0 已实现

| 原规划项 | 上游实现 |
| --- | --- |
| 记忆作用域 | `filtering_settings.memory_scope_mode` 提供 `legacy` / `session` / `user` / `global` 四种模式，另有强制隔离、白名单与身份别名 |
| 记忆取代链 | 旧记忆被取代后保留 `superseded_by` 指针，召回时跳过；`/lmem trace` 可回溯取代链 |
| 用户档案 | `memory_profiles` 按人格与作用域保存偏好、状态与任务画像，可查看历史版本 |
| 群共享池 | 频道公共记忆 `livingmemory:channel:<平台>:<群ID>`，与个人作用域合并召回，默认关闭 |
| 外部接口 | `core/external_api_server.py` 提供本地 HTTP API，`scripts/memory_mcp_server.py` 提供 MCP 接入 |

### 本仓库新增（默认关闭）

| 功能 | 开关 | 行为 |
| --- | --- | --- |
| 逐条隐私标签 | `privacy_settings.enabled` | 写入时把 `privacy` 规范为 `public` 或 `private:<归属作用域>`；召回侧按发言人过滤，群聊只比对用户级作用域，私聊兼容会话归属，无主私有标签按不可见处理 |
| 记忆时效状态 | `freshness_settings.enabled` | 由 `valid_until` 与 `superseded_by` 实时推导 `timeless` / `current` / `pending` / `outdated`；注入时按状态附加中文提醒，过期与被取代两类可分别关闭 |
| 注入触发模式 | `recall_engine.injection_mode` | `auto` 每轮注入（默认）；`on_demand` 不主动注入，改为在系统提示中提示模型调用检索工具；`hybrid` 仅当最高相似度达到 `recall_engine.hybrid_auto_threshold`（默认 0.55）时注入 |
| 按发言人锁定注入 | `recall_engine.speaker_locked_injection` | 群聊只保留当前发言人的用户级记忆、本群公共记忆与全局记忆 |

时效状态不落库，每次按 `valid_until` 与取代关系实时推导；隐私标签仅在开关打开时随写入落到 `documents.metadata.privacy`。记忆列表接口已返回 `privacy` 与 `time_status`，编辑接口支持修改这两个字段；仪表盘表格尚未加列展示。

### 尚未实现

- 取代关系自动改写：`outdated` 只做注入提示，不会自动把旧记忆的 `superseded_by` 指向新记忆，仍由上游的合并流程维护。

字段设计与落点文件见 [ANALYSIS.md](ANALYSIS.md)。

## 继续了解

[快速开始](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/guide/getting-started) · [配置参考](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/configuration) · [命令速查](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/commands) · [技术架构](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/architecture) · [更新记录](CHANGELOG.md)

从 v1.4.0–v1.4.2 升级时，请先查看[备份与迁移说明](https://lxfight-s-astrbot-plugins.github.io/astrbot_plugin_livingmemory/configuration#备份迁移与清理)。

---

社区支持：QQ 二群 `1129994749`（新群） · [QQ 一群 953245617](https://qm.qq.com/cgi-bin/qm/qr?k=WdyqoP-AOEXqGAN08lOFfVSguF2EmBeO&jump_from=webapi&authKey=tPyfv90TVYSGVhbAhsAZCcSBotJuTTLf03wnn7/lQZPUkWfoQ/J8e9nkAipkOzwh)（已满） · 口令：`lxfight`<br>
开源许可证：[AGPL-3.0](LICENSE)
