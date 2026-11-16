# LivingMemory 规划与实现方案 v5（2.13.0 基线，四项已实现）

> 版本: v5 | 日期: 2026-11-16 | 基线: 上游 2.13.0（tag `e7a9573`）
> v4 是设计稿，v5 记录落地结果：四项能力已实现，全部以开关形式提供、默认关闭。下文第三、五、六节保留设计原文，与实现不一致处已就地标注。

## 零、实现状态（v5）

| 能力 | 开关（默认） | 落点 | 与 v4 设计的差异 |
| --- | --- | --- | --- |
| 逐条隐私标签 | `privacy_settings.enabled`（false） | `core/memory_privacy.py`；召回侧在 `MemoryEngineRecallMixin._filter_by_privacy()` 后置过滤 | **不走 SQL**：作用域 SQL 分散在 `bm25_retriever.py`、`memory_engine_agentic.py`、`memory_engine_recall.py` 三处，改在统一出口过滤更稳，也避免为 `json_extract` 条件新增索引 |
| 记忆时效状态 | `freshness_settings.enabled`（false） | `core/memory_freshness.py`；注入侧 `freshness_notice()` 拼进注入头 | 与设计一致：只存 `valid_until`，`time_status` 每次实时推导 |
| 注入触发模式 | `recall_engine.injection_mode`（`auto`） | `core/event_handler_modules/memory_recall.py` | 与设计一致；`on_demand` 改为在系统提示追加工具提示 |
| 按发言人锁定注入 | `recall_engine.speaker_locked_injection`（false） | 同上，`_filter_by_speaker_lock()` | 群聊只保留当前发言人的用户级记忆，其余用户级记忆丢弃 |

实现层面的三条硬约束（与 v4 相同，未变）：
- 关闭开关时**不写任何新 metadata 键**，升级后行为与 2.13.0 完全一致；
- `privacy` 缺失即 `public`，不做存量回填；
- 无主的 `private:` 标签按不可见处理（fail-closed）。

已知未做：仪表盘表格未加列展示这两个字段（列表接口已返回 `privacy` 与 `time_status`，编辑接口已可修改）；`storage/schema.py` 未加 `idx_doc_privacy`（当前实现不依赖该索引）。

---

## 一、这份文档解决什么问题

v3 的出发点是一个 54 文件的 2.3.2 代码库，规划了 10 处改动。到 2.13.0，上游已经用 252 个 Python 文件、1606 项测试把其中大部分能力做完了。继续照 v3 施工会和上游撞车，因此本版做三件事：

1. 逐项核对 v3 的规划，标出已被上游覆盖的部分（第二节）。
2. 只对仍缺失的能力给出设计，并绑定到 2.13.0 的真实文件与扩展点（第三节、第五节）。
3. 划清与上游既有机制的边界，避免重复实现（第四节）。

一句话结论：**v3 的 10 项改动中 6 项已被上游吸收，剩下 4 项仍属于本 fork。**

---

## 二、原规划 → 上游实现对照

| v3 规划项 | 上游版本 | 2.13.0 中的落点 | 结论 |
| --- | --- | --- | --- |
| 记忆作用域 `user/group/session/global` | 2.5.0 | `filtering_settings.memory_scope_mode`（`legacy` / `session` / `user` / `global`）+ `isolated_sessions` + 白名单 + 身份别名 | 已覆盖 |
| 取代链与「过时记忆不再召回」 | 2.10.0 | `superseded_by` 数据通路，召回跳过被取代记忆；`/lmem trace` 回溯取代链 | 已覆盖 |
| 用户画像 | 2.11.0 | `memory_profiles` + `memory_profile_history`，按人格与作用域组织，可审核变更 | 已覆盖 |
| 群级共享池 | 2.11.0 | 频道公共记忆 `livingmemory:channel:<平台>:<群ID>`（`channel_memory.*`，默认关闭） | 已覆盖 |
| 独立 REST API | 2.11.0 | `core/external_api_server.py` + `scripts/memory_mcp_server.py`（MCP） | 已覆盖 |
| 会话级记忆池开关 | 2.5.0 | `filtering_settings.use_session_filtering` 仍保留，与 `memory_scope_mode` 并存 | 已覆盖 |
| 逐条隐私标签 | — | 无。全仓 `.py` 中 `privacy` 命中 0 次 | **仍缺失** |
| 记忆时效状态 `time_status` | — | 无。`time_status` / `valid_until` 命中 0 次 | **仍缺失** |
| 注入触发模式 `auto/on_demand/hybrid` | — | 无。`injection_mode` 仅出现在 `tests/test_config_manager.py` 的旧配置归一化用例 | **仍缺失** |
| 群聊按发言人锁定注入 | 部分（2.5.0 / 2.6.0） | `memory_scope_mode=user` 隔离 + 自主回忆 `target="current_speaker"` | **部分具备** |

注：v3 里"新增 4 个 Agent 工具""新增 `api.py`"两项也已落地——2.13.0 的 `core/tools/` 已有 `memory_forget_tool.py`、`memory_profile_tool.py`、`memory_read_tool.py`、`memory_agentic_search_tool.py`，外部 API 由 `core/external_api_server.py` 承担。

---

## 三、仍待实现的能力

### 3.1 逐条隐私标签（privacy）

**上游现状**：`memory_scope_mode` 是"分区"——按会话、按用户或全局各存一份，互不可见。它回答的是"这条记忆属于谁"，不是"同一条记忆谁能看"。

**缺口**：把作用域设为 `user` 后，用户 A 的记忆存在 A 的 scope 里，但一旦有人把模式切回 `session` 或 `legacy`，A、B、C 的记忆又会落进同一个池子，没有逐条可见性控制。v3 的"一个池子 + 逐条标签"在 2.13.0 里没有对应实现。

**设计**：标签存在 `documents.metadata.privacy`，取值两种形态。

```
public                 所有会话可见（默认）
private:<session_id>   仅产生该记忆的会话可见
```

- 写入：`memory_processor` 的总结 prompt 增加一个 `privacy` 判定字段（规则与现有 `importance` 同级），经 `memory_processor_parse.py` 解析后随 `metadata` 透传进 `MemoryEngineCrudMixin.add_memory()`（`core/managers/memory_engine_crud.py:63` 已有 `metadata` 参数，签名无需改动）。
- 召回（**已按此实现，取代 v4 的 SQL 方案**）：在 `MemoryEngineRecallMixin` 的统一出口 `_filter_by_privacy()` 里做 metadata 后置过滤，调用 `core/memory_privacy.filter_by_privacy()`：
  - 群聊事件：只保留 `public`，或 `private:` 归属等于当前发言人**用户级作用域**的条目；
  - 私聊事件：在群聊规则之外，额外允许归属等于当前会话 ID 的条目（`memory_scope_mode=session` 时 owner 就是会话 ID）；
  - 缓存存未过滤结果，过滤在读取侧做——同一作用域下不同发言人的可见集合不同。
- 索引：不需要。过滤在内存里按 metadata 判断，`storage/schema.py` 未加 `idx_doc_privacy`。
- 管理：`core/page_api_modules/memory_handler_update.py` 增加 `privacy` 可写字段；`pages/dashboard/modules/memory-page.js` 在记忆行加切换。
- 迁移：存量记忆 `privacy` 缺失，一律按 `public` 处理（SQL 用 `COALESCE(json_extract(metadata,'$.privacy'),'public')`），不做数据回填。

### 3.2 记忆时效状态（time_status）

**上游现状**：两套机制都不等价。

- `AtomStatus`（`active` / `dormant` / `superseded` / `expired` / `forgotten`）+ 每类型 TTL（`core/models/memory_atom.py` 的 `_ATOM_TTL_CONFIG`，如 `episodic` 7 天、`factual` 180 天）走的是"自动衰减到遗忘"，不可逆。
- `superseded_by` 走的是"被新记忆取代"，只覆盖"后来者覆盖前者"这一种过时。

**缺口**："明天下午三点开会"这类事实有明确有效期，但既不该按 TTL 猜，也不是被新记忆取代，而是"到期后需要复核"。2.13.0 没有这个状态。

**设计**：`time_status` 是**派生值**，不落库；只持久化 `metadata.valid_until`（REAL 时间戳，`null` 表示无时效）。

| 状态 | 判定 | 注入表现 |
| --- | --- | --- |
| `timeless` | `valid_until` 为空 | 正常引用 |
| `current` | `valid_until` 未到期 | 正常引用 |
| `pending` | `valid_until` 已过期，且无 `superseded_by` | 前置「时效提醒：以下记忆已过有效期，引用前请确认」 |
| `outdated` | 存在 `superseded_by` | 前置「时效提醒：以下记忆已被取代，请参考新记忆」 |

关键取舍：**不存 `time_status` 字段**。状态随 `now` 变化，存下来就会和事实漂移；派生计算只在召回后、注入前做一次，代价是每批结果一次时间比较。取代链直接复用已有的 `superseded_by`，不新增指针。

- 写入：`memory_processor` prompt 增加 `valid_until` 输出（仅当对话含明确时间语义时才给值，避免 LLM 乱填）。
- 注入：在 `core/event_handler_modules/memory_recall.py:327` 组装 `req.extra_user_content_parts` 处按状态分组，前缀文本放在 `MEMORY_INJECTION_HEADER`（`core/base/constants.py:6`）之后、正文之前，便于 `auto_remove_injected` 的正则清理。
- 管理：Dashboard 记忆表增加时效列，`pending` 与 `outdated` 用不同色标；`memory_handler.py` 返回派生状态。

### 3.3 注入触发模式（injection_mode）

**上游现状**：`recall_engine.injection_method` 控制的是"注入到哪个位置"（`extra_user_content` 默认，兼容 `user_message_before` / `user_message_after` / `fake_tool_call` / `fake_tool_call_deepseek_v4` / `system_prompt`），不控制"要不要注入"。

**缺口**：没有"只在 Agent 主动调用工具时才给记忆"的模式，也没有按相关度决定是否自动注入的混合模式。

**设计**：新增 `recall_engine.injection_mode`，三档。

| 模式 | 行为 |
| --- | --- |
| `auto`（默认，等价现状） | 每轮请求前按现有链路召回并注入 |
| `on_demand` | 跳过自动召回，只保留 `recall_long_term_memory` / 自主召回工具 |
| `hybrid` | 自动召回后按最高相似度判定：达到 `hybrid_auto_threshold` 才注入，否则丢弃并提示可用工具 |

落点单一：`MemoryRecall.handle_memory_recall()`（`core/event_handler_modules/memory_recall.py:96`）入口处按模式短路，不改检索层。`on_demand` 下仍需注册工具，注册逻辑在 `main.py:262 _register_agent_tools_if_needed()`，与模式无关。

### 3.4 按发言人锁定注入（部分具备）

**上游现状**：`memory_scope_mode=user` 时召回已按用户分区；自主回忆可用 `target="current_speaker"`。但默认模式是 `legacy`，此时群聊召回不区分发言人，仍可能把其他人的个人记忆拼进上下文。

**设计**：不改作用域语义，只在注入侧加一层发言人过滤。

- 用 `core/memory_scope.py:163 resolve_event_identity()` 取得当前发言人身份。
- 群聊事件下，注入集合限定为：当前发言人的 `user:<id>` 记忆 + 本群 channel 记忆 + `global` 记忆；其他成员的 `user:*` 记忆即使被检索到也丢弃。
- 配置 `recall_engine.speaker_locked_injection`（默认关闭），关闭时行为与 2.13.0 完全一致。

---

## 四、与现有机制的边界

| 既有能力 | 与新能力的关系 |
| --- | --- |
| `memory_scope_mode`（分区） | 与 privacy 正交：scope 决定"存在哪个分区"，privacy 决定"同一池内谁能看"。两者同时生效时取交集 |
| `AtomStatus` + TTL 衰减 | 与 `time_status` 互补：TTL 管"短期记忆自动清理"，`time_status` 管"长期事实的有效期复核"，互不替代 |
| `superseded_by` | 直接复用为 `outdated` 的判定依据，不新增字段 |
| `injection_method`（位置） | 与 `injection_mode`（是否注入）正交，两者可自由组合 |
| `channel_memory`（群共享池） | 与 3.4 的发言人锁定叠加：channel 记忆始终注入，个人记忆按发言人过滤 |
| `agentic_recall`（自主召回） | `on_demand` 模式复用这条链路，不新增工具 |

---

## 五、改动清单（按 2.13.0 实际文件）

| 文件 | 类型 | 改动 |
| --- | --- | --- |
| `_conf_schema.json` | 修改 | 新增 `privacy_settings`、`freshness_settings` 两个顶层块；`recall_engine` 增加 `injection_mode`、`hybrid_auto_threshold`、`speaker_locked_injection` |
| `core/memory_privacy.py` | 新增 | privacy 取值构造/解析、可见性判定、批量过滤与计数（已实现，不含 SQL 条件） |
| `core/memory_freshness.py` | 新增 | `valid_until` 解析、`time_status` 派生、注入前缀文本 |
| `core/managers/memory_engine_recall.py` | 修改 | `_search_memories_impl()` 追加 privacy 条件；召回结果附加派生时效状态 |
| `core/event_handler_modules/memory_recall.py` | 修改 | `handle_memory_recall()` 入口按 `injection_mode` 短路；注入组装处加时效前缀与发言人过滤 |
| `core/processors/memory_processor.py` | 修改 | 总结 prompt 增加 `privacy` 与 `valid_until` 字段说明 |
| `core/processors/memory_processor_parse.py` | 修改 | 解析并校验两个新字段，非法值回落默认 |
| `core/page_api_modules/memory_handler.py` | 修改 | 列表/详情返回 `privacy` 与派生 `time_status` |
| `core/page_api_modules/memory_handler_update.py` | 修改 | 允许编辑 `privacy` 与 `valid_until` |
| `pages/dashboard/modules/memory-page.js` | 未改 | 计划中的时效色标、privacy 切换与筛选项未做；后端接口已具备数据 |
| `storage/schema.py` | 修改 | 新增 `idx_doc_privacy` 表达式索引 |
| `storage/db_migration.py` | 修改 | 新版本号一步：仅建索引，不回填数据 |
| `core/tools/memory_search_tool.py` | 修改 | 增加 `privacy` 过滤参数，返回时效状态 |
| `core/tools/memory_memorize_tool.py` | 修改 | 增加可选 `privacy`、`valid_until` 参数 |
| `tests/test_memory_privacy.py` | 新增 | 可见性矩阵、群聊/私聊分支、缺省 public 兼容 |
| `tests/test_memory_freshness.py` | 新增 | 四态派生、边界时间、取代优先于过期 |
| `tests/test_injection_mode.py` | 新增 | 三模式分流、hybrid 阈值、关闭时行为不变 |

不动：`core/retrieval/`（检索层）、`core/managers/memory_engine.py` 及其 `_crud` / `_agentic` / `_batch` / `_stats` 分片、`core/memory_scope.py`（只在调用侧使用）、`storage/atom_store.py`、`core/managers/profile_manager.py`。

---

## 六、数据库与迁移

- 不新增表。privacy 与 `valid_until` 全部落在 `documents.metadata` JSON 里，沿用现有 `json_extract` 表达式索引模式。
- **没有迁移**：实现改为读取侧后置过滤，未新增索引、未新增表、不改 `documents` 结构。存量文档不写 `privacy` 键即按 `public` 处理，**升级不触发数据重写，也不需要重建索引或重新生成 Embedding**。
- `valid_until` 缺失即 `timeless`，同样无需回填。

---

## 七、配置项草案

```json
{
  "privacy_settings": {
    "enabled": false,
    "default_label": "public",
    "strict_in_group": true
  },
  "freshness_settings": {
    "enabled": false,
    "remind_expired": true,
    "remind_superseded": true
  },
  "recall_engine": {
    "injection_mode": "auto",
    "hybrid_auto_threshold": 0.55,
    "speaker_locked_injection": false
  }
}
```

三个开关默认关闭，保证升级后行为与 2.13.0 逐字节一致；用户显式打开才生效。

---

## 八、风险与取舍

1. **privacy 与 scope 双重过滤可能过严**。`memory_scope_mode=user` 又开 privacy 时，群聊里只剩 public 项，召回量可能骤降。缓解：默认关闭 privacy，并在诊断页展示"被 privacy 过滤掉多少条"。
2. **`valid_until` 由 LLM 判定，存在误填风险**。缓解：只在对话含明确时间语义时写值；`valid_until` 一旦写入可在 Dashboard 手改；不做自动回填。
3. **时效前缀占注入预算**。`pending`/`outdated` 每批加一行前缀，长会话下会挤压正文。缓解：前缀按状态合并一次，不逐条加。
4. **派生状态的一致性**。`time_status` 不落库意味着列表接口也要现算，Dashboard 分页时需在 SQL 里算而非 Python 侧算，否则排序会错。缓解：列表接口用同一表达式，排序键与展示值同源。
5. **`on_demand` 模式的可用性**。关掉自动注入后，模型必须知道有工具可用，否则记忆等于失效。缓解：`on_demand` 下在 system prompt 追加一句工具提示。

---

## 九、实施顺序

1. **privacy**：数据标签 + SQL 过滤 + Dashboard 切换。改动面最大，先做。
2. **time_status**：派生状态 + 注入前缀 + 列表列。依赖 privacy 的 metadata 透传通道。
3. **injection_mode**：纯入口开关，独立可测。
4. **speaker lock**：依赖 privacy 的可见集合推导，放最后。

每步独立可回滚：三个开关默认关闭，任何一步出问题都能单独关掉而不影响其余。

---

## 十、Q&A

**Q: 上游已经有 `memory_scope_mode`，为什么还要 privacy？**
A: scope 是分区，切模式会把不同人的记忆重新混在一起；privacy 是逐条可见性，跟着记忆走，不随模式变化。两者解决的不是同一个问题。

**Q: 为什么不直接用 `AtomStatus.expired`？**
A: `expired` 是 TTL 到期的终态，进入后不再召回。`pending` 需要"仍然召回但带提醒"，语义相反。硬套会破坏原子生命周期。

**Q: `pending` 记忆怎么变成 `current`？**
A: 两条路。LLM 回复里出现新信息时，总结阶段写一条新记忆并给旧记忆设 `superseded_by`，旧记忆转为 `outdated`；用户也可以在 Dashboard 直接改 `valid_until` 续期。

**Q: 为什么不把 `time_status` 存进数据库？**
A: 它随时间变化。存下来要么靠定时任务刷新（引入调度依赖和漂移窗口），要么每次读时纠正（等于没存）。派生计算更简单，也不会出现"库里写着 current、实际已过期"的状态。

**Q: 这些改动会不会破坏现有测试？**
A: 三个开关默认关闭，默认路径的 SQL、prompt 与注入文本都不变。新增测试只覆盖开关打开后的分支。
