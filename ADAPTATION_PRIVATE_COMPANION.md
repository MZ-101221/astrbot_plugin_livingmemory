# LivingMemory × Private Companion 记忆功能适配报告

> 结论先行：两个插件**不是二选一**，Private Companion 本身就带官方协同开关（`enable_livingmemory_integration`，默认 `true`）。真正的重复不在存储层（各用各的库），而在**注入层**与**人物档案层**。下面的方案全部是配置级调整，不需要改任何一边的代码。

## 一、两者的职责与数据落点

| 维度 | LivingMemory 2.14.0 | Private Companion |
|---|---|---|
| 记忆形态 | 会话窗口摘要（episodic）+ 原子 + 知识图谱 + 版本化人物档案 | 人物档案 `companion_memory`、`dialogue_episodes`、`open_loops`、`behavior_habits`、`action_preferences`、`intent_profile`、`birthday_profile` |
| 存储 | `data/plugin_data/astrbot_plugin_livingmemory/livingmemory.db`（+ `livingmemory_graph_documents.db`、FAISS 索引） | `data/plugin_data/astrbot_plugin_private_companion/companions.db`（可用 `storage_sqlite_path` 改路径） |
| 检索方式 | 向量 + BM25 混合召回，按 `memory_scope` 隔离 | 结构化查询（按 person 读档案/片段），带 `private_scope_isolation` |
| 注入方式 | `recall_engine.injection_method`（默认 `extra_user_content`），块标记 `<RAG-Faiss-Memory>` | 档案块 + `livingmemory.guidance` 引导段 + 关系上下文 |
| 管理界面 | 记忆管理页（列表 / 详情 / 编辑 / 图谱） | 陪伴面板（`pages/companion-panel`）内含记忆区块，并聚合 `GET /worldbook/member/livingmemory` |
| 隐私控制 | 本 fork 新增 `privacy` 逐条标签（`public` / `private:<owner_scope>`） | 自己的 `private_scope_isolation.py`，按 person 隔离 |

## 二、实际重复点（三处，按影响排序）

1. **注入层重复**：同一次 LLM 请求里，LivingMemory 会塞一个记忆块，Private Companion 又会塞「档案 + 记忆片段 + 引导语」。两边都开时上下文里出现两套"记忆"，既浪费 token，也可能让模型看到互相矛盾的说法。
2. **人物档案重复**：LivingMemory 的 `memory_profiles`（`basic` / `preferences` / `status` / `task_preferences`，≤300 字符）与 Companion 的 `companion_memory` / `intent_profile` 语义高度重合，而且两边都会**主动写入**（LivingMemory 靠总结，Companion 靠 episode 刷新）。
3. **界面重复**：LivingMemory 记忆管理页 与 Companion 陪伴面板的记忆区块展示的是两套数据，用户容易以为是同一份记忆的两份视图。

## 三、推荐适配方案（配置级，零改码）

### 3.1 保留协同开关，让它当"编排者"

`astrbot_plugin_private_companion_config.json`：

```json
{
  "enable_livingmemory_integration": true,
  "livingmemory_tool_name": "recall_long_term_memory"
}
```

理由：Companion 在 `final_response_persistence.py:724/740` 里会 **临时挂起再恢复** LivingMemory 的响应捕获（`_defer_livingmemory_response_capture` / `_restore_livingmemory_response_capture`），这正是为了避免同一轮对话被两边各写一次。关掉这个开关反而会失去这层互斥。

另外 `integration_status.py:538 _patch_livingmemory_processor_compat` 是给旧版 LivingMemory 补 `MemoryProcessor.config` 的兜底；2.14.0 的 `MemoryProcessor.__init__(context, llm_provider, config)` 已经自带该参数，所以这段补丁在新版上是 no-op，留着无害。

### 3.2 人物档案只留一套：交给 Companion

LivingMemory 侧关掉档案注入，只保留原文/向量召回：

```json
{
  "profile_settings": { "enabled": false }
}
```

理由：Companion 的档案是**结构化、可编辑、带 open loop 与行为习惯**的，颗粒度比 LivingMemory 的 300 字符画像更细；LivingMemory 的强项是"记得你说过什么原话"，不是"记得你是什么人"。这样两边各司其职，也不会有两份画像打架。

### 3.3 给注入设预算，避免上下文膨胀

| 侧 | 键 | 建议值 | 说明 |
|---|---|---|---|
| Companion | `memory_companion_context_max_chars` | 800–1200 | 档案块上限 |
| Companion | `memory_companion_context_top_k` | 3–5 | 记忆片段条数 |
| LivingMemory | `recall_engine.top_k` | 3–5 | 召回条数 |
| LivingMemory | `recall_engine.injection_method` | `extra_user_content`（默认） | 保持默认即可 |

两者合计建议控制在 2000 字符以内，否则小模型容易"记串"。

### 3.4 界面：留一个入口

- 想看"关系/习惯/待办"→ Companion 陪伴面板（它已聚合了 LivingMemory 的成员视图 `GET /worldbook/member/livingmemory`）。
- 想看"某句话原文、图谱、逐条改隐私标签"→ LivingMemory 记忆管理页。
- 如果嫌重复，可以在 AstrBot 的页面配置里隐藏其中一个入口，但**不建议删页面**，排障时有用。

### 3.5 隐私语义要明确边界（重要）

本 fork 的 `privacy` 标签（`public` / `private:<owner_scope>`）**只在 LivingMemory 内部生效**：召回时由 `core/managers/memory_engine_recall.py::_filter_by_privacy` 逐条过滤，`owner_scope` 是写入时的 `memory_scope`（`livingmemory:user:<平台>:<身份>` 或会话 ID）。

Companion 的隔离走的是它自己的 `private_scope_isolation.py` 与 person 维度，**两套标签不互通**。也就是说：

- 在 LivingMemory 里标了 `private` 的记忆，不会被 Companion 的档案引用（因为它根本不读 LivingMemory 的表）；
- 反过来 Companion 的私有档案也不会进 LivingMemory 的召回池。

这实际上是**安全**的（各管各的），但如果你希望"在 Companion 里标记为私密的人，LivingMemory 也不再跨会话召回他"，就需要一层 person ↔ `livingmemory:user:*` 的映射，这属于后续开发项，不是配置能解决的。

## 四、验证方法

1. 改完配置重启 AstrBot，看日志里是否仍有 `已为 LivingMemory MemoryProcessor 添加 config 兼容兜底`（有也无害）。
2. 私聊发一句话，抓一次请求体（AstrBot 日志开 debug 或用 `/lmem trace`），确认上下文里**只有一块**记忆/档案内容。
3. 用 LivingMemory 的 `/lmem trace` 看召回条数与 `privacy_filter` 计数；用 Companion 的调试面板看 `memory_phase` 与档案块长度。
4. 观察一周：重点看"模型把 A 的话记成 B 的"这类串味是否减少。

## 五、如果以后要改代码（本次不做）

| 目标 | 落点 |
|---|---|
| privacy 标签与 Companion person 打通 | `core/memory_privacy.py` 增加 person ↔ user scope 映射，`_filter_by_privacy` 传入 person 维度 |
| 统一记忆搜索入口 | Companion 的 `memory_companion_adapter.py` 已有调用 LivingMemory 工具的能力，可扩成"先查档案再查原文"的单一入口 |
| 去掉 Companion 的兼容补丁 | `integration_status.py:538`，2.14.0 起可安全删除（但保留无副作用） |
| 合并两个管理界面 | Companion 的 `page_api.py` 已聚合 LivingMemory 数据，可把 LivingMemory 的逐条编辑能力做成 Companion 面板的一个 tab |

---

**一句话总结**：让 Companion 当"人物档案 + 编排者"，让 LivingMemory 当"原文检索 + 图谱"，关掉 LivingMemory 的档案注入、给两边都设注入预算，就能同时用而不打架。
