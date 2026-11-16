# LivingMemory × Private Companion 联动设计（一期）

> 状态：设计稿，未实现。经三轮问答确认，本文是一期改动的唯一依据。
> 涉及两个仓库：本仓库（LivingMemory，下称 **LM**）与 `astrbot_plugin_private_companion`（下称 **PC**）。

---

## 一、结论

**LM 提供记忆，PC 提供人物与关系。运行时单向依赖：PC 调 LM，LM 不知道 PC 存在。**

- LM 仍是可独立发布、独立测试的插件，不引入对 PC 的任何 import。
- PC 新增一个适配模块 `livingmemory_bridge.py` 承担全部耦合，其余文件只加两三处调用点。
- 人物档案归 PC 独占，LM 的档案层关闭（当前为空操作，关闭零成本）。
- 群聊不做"一刀切"：**成员画像锁当前发言人，群体氛围与关系边放开**。

---

## 二、事实基线（已核实）

| 事实 | 位置 |
|---|---|
| 钩子按 `priority` 降序执行，同值按插件加载序 | `astrbot/core/star/star_handler.py:26` |
| PC 的 `on_llm_request` 优先级 110000，LM 为 0 → PC 先执行、内容排在 LM 之前 | `astrbot_plugin_private_companion/main.py:1779`、LM `main.py:465` |
| LM 只注册 `on_llm_request` / `on_llm_response`，无 `on_decorating_result` | LM `main.py:465`、`main.py:478` |
| LM 的档案渲染为四节单行文本，≤300 字符 | LM `core/utils/formatting.py:308` |
| LM 的 `memory_profiles` 表当前 **0 行**，唯一写入口是默认关闭的 `update_user_profile` 工具 | LM `main.py:326` |
| PC 没有"记忆注入"的模型校验开关；现有 judge/review 开关管的是回复审查、情绪判定、主动消息 | PC `_conf_schema.json:1460/1808/1948/2008/2014/2026` |
| PC 注入统一走 `ConversationInjectionPlan`，默认落 `turn_tail` → `req.extra_user_content_parts` | PC `conversation_injection_plan.py:44-46`、`:603-611` |
| PC 群聊只注入当前发言人的成员记录 | PC `group_observation.py:3347-3351` |
| PC 群聊会注入第三人之间的关系边（≤4 条） | PC `group_observation.py:2969-3017` |
| PC 群聊侧没有任何敏感行过滤，只有一句提示词；私聊侧有正则黑名单 + 相关性过滤 | PC `group_observation.py:3453-3456` vs `user_memory.py:10150-10173` |
| PC 从不构造或读取 `livingmemory:channel:*` 作用域（全仓库 0 命中） | — |
| LM 的原子类型写入 `metadata.atom_types`（排序后的字符串列表） | LM `core/managers/memory_engine_crud.py:163-166` |

---

## 三、一期四项改动

### ① LM 关闭档案注入（配置级，零代码）

- 改动：`profile_settings.enabled` 由 `true` 改为 `false`。
- 落点：`AstrBot/data/config/astrbot_plugin_livingmemory_config.json`。
- 效果：`_load_profile_injection_text` 在 `manager.enabled` 为假时直接返回 `""`（LM `core/event_handler_modules/memory_recall.py:520-522`），注入块里不再出现「用户档案：」。
- 回滚：改回 `true` 即可。当前表为空，改回也不会产生任何内容。

### ② PC 新增 `livingmemory_bridge.py`（进程内直调）

**为什么不用 HTTP**：LM 的外部 API 需要 Bearer key、要开端口、要处理限流与序列化（`core/external_api_server.py:41-44`）；插件之间同进程，直调没有这些成本。

**取实例**：

```python
meta = context.get_registered_star("astrbot_plugin_livingmemory")
plugin = getattr(meta, "star_cls", None)
initializer = getattr(plugin, "initializer", None)
ready = bool(initializer and initializer.is_initialized)   # LM core/plugin_initializer.py:366-369
engine = getattr(initializer, "memory_engine", None)
```

**调用契约**（LM 侧本期同步新增 `allowed_atom_types`，见 ③）：

```python
items = await asyncio.wait_for(
    engine.search_memories(
        query=query,
        k=top_k,                                   # 夹 1..10
        session_id=umo,                            # 当前会话 umo
        persona_id=persona_id,
        extra_scopes=[channel_scope] if channel_scope else None,
        viewer_scope=viewer_scope,                 # 见第五节
        is_group=is_group,
        allowed_atom_types=["episodic", "factual"] if is_group else None,
    ),
    timeout=timeout_seconds,                       # PC memory_companion_context_timeout_seconds，默认 1.2
)
```

**渲染**：桥接自己渲染，不复用 LM 的 `format_memories_for_injection`——后者会带上 `<RAG-Faiss-Memory>` 头尾标记，PC 的块再包一层就变成嵌套标记，排查困难。桥接输出形如：

```
- [2026-08-29] 和 HiMZ 规划便携屏一线连 PCB 项目……
- [2026-06-01] HiMZ 在 Blender 里跑 socket 服务器遇到 OSError……
```

**挂载点**：PC 的 `place_sections`（`passive_state_pipeline.py:163-209`）

```python
section = PromptSection(key="livingmemory.recall", title="长期记忆", content=text)
self.place_sections("livingmemory.recall", [section], priority=74)
```

- 私聊与群聊都新增 `livingmemory.recall` 段，priority 74（介于 `memory.private_recall` 73 与 `companion.planner` 80 之间）：私聊保留 PC 自己的 `memory.private_recall`，桥接段只补 LM 的长期记忆，两者不合并成一段。
- 群聊在该段上额外限定 `allowed_atom_types=["episodic","factual"]`。

**降级**：任何异常都不抛出，返回 `RecallResult(ok=False, reason=..., text="")`。`reason` 取值：

| reason | 触发条件 | PC 行为 |
|---|---|---|
| `ok` | 正常返回 | 注入记忆段 |
| `plugin_missing` | `get_registered_star` 返回 None | 跳过，只注入档案 |
| `engine_not_ready` | `is_initialized` 为假或 `memory_engine` 为 None | 跳过 |
| `timeout` | `asyncio.TimeoutError` | 跳过，记一条 debug 日志 |
| `error` | 其他异常 | 跳过，记一条 warning 日志（含异常类型） |

### ③ LM 读侧按 AtomType 过滤

- `search_memories` 新增关键字参数 `allowed_atom_types: list[str] | None = None`，透传给 `_search_memories_impl`。
- 过滤位置：与 privacy 过滤同一处（缓存写入之后、`_finalize_recall_trace` 之前），保证**缓存里存的仍是未过滤结果**，同一份缓存可服务不同调用方。
- 判定：读 `metadata["atom_types"]`（列表）；与 `allowed_atom_types` 无交集则丢弃。字段缺失视为 `unknown`，群聊场景一并丢弃。
- 计数：`rejected["atom_type"] += n`，并追加 `trace.notes.append(f"atom_type_filter:{n}")`。
- `allowed_atom_types=None` 时完全跳过，行为与 2.14.0 一致。

### ④ 群聊两层注入

| 层 | 内容 | 谁负责 | 过滤规则 |
|---|---|---|---|
| 成员级 | 当前发言人的画像、相处线索、`livingmemory:user:*` 记忆 | PC `group_observation.py:3347` + LM `speaker_locked_injection` | **严格锁发言人**，其他人的 user 记忆一律不进 |
| 群体级 | 群氛围、群片段、关系边、`livingmemory:channel:*` 公共记忆 | PC `group_observation.py:2969` + LM `channel_memory` | 只放事实型（`episodic`/`factual`），关系与偏好不进 |

这就是 Q4「中和」的落点：**锁人，不锁气氛**。PC 现有的关系边注入（`A ↔ B｜常见氛围`）保留，但 LM 侧不再往里塞任何 `relational`/`preference` 类型的记忆。

---

## 四、配置表

| 键 | 归属 | 一期值 | 范围 | 说明 |
|---|---|---|---|---|
| `profile_settings.enabled` | LM | **false**（原 true） | bool | 关掉 LM 档案注入 |
| `privacy_settings.enabled` | LM | true | bool | 私有标签过滤 |
| `freshness_settings.enabled` | LM | true | bool | 时效提醒 |
| `recall_engine.speaker_locked_injection` | LM | true | bool | 群聊只注入当前发言人记忆 |
| `recall_engine.injection_mode` | LM | auto | auto/on_demand/hybrid | 不变 |
| `channel_memory.enabled` | LM | 保持现状 | bool | 本期不强制打开 |
| `livingmemory_bridge_enabled` | PC 新增 | true | bool | 桥接总开关，关掉即回到 2.14.0 行为 |
| `livingmemory_bridge_top_k` | PC 新增 | 4 | 1–10 | 记忆条数 |
| `livingmemory_bridge_max_chars` | PC 新增 | 1500 | 200–3000 | 记忆字符预算 |
| `memory_companion_context_top_k` | PC | **3**（原 5） | 1–10 | 档案/相处线索条数 |
| `memory_companion_context_max_chars` | PC | **600**（原 900） | 240–1800 | 档案/相处线索字符 |
| `memory_companion_context_timeout_seconds` | PC | 1.2 | — | 桥接超时 |

合计上限：档案 600 + 记忆 1500 = **2100 字符**，低于当前最坏情况（900 + 3000 = 3900）。

---

## 五、身份映射（放 PC 侧）

LM 的隔离键是 `livingmemory:user:<platform>:<identity>`；PC 的身份是五元组（`companion_instance_id`、`bot_account_id`、`adapter_instance_id`、`subject_namespace`、`platform_subject_id`，见 PC `unified_person_registry.py:52-55`）。

桥接负责换算：

```python
platform = event.get_platform_name()          # astrbot/core/platform/astr_message_event.py:178
subject  = event.get_sender_id()              # 同文件 :273
identity = subject.strip().casefold()
# 若 identity_links 里该 identity 有 active link，则改用 link 的主账号 subject
viewer_scope = f"livingmemory:user:{platform}:{identity}"
```

- 一人多号：`identity_links` 命中时用主账号，保证跨号共享记忆。
- LM 侧不感知五元组，只接收一个字符串。

---

## 六、双写语义

PC 现在会把最终回复交给 LM（`final_response_persistence.py:1161-1242` 调 `handle_memory_reflection`），LM 会再总结入库。这条通路**保留**，但两侧写的东西不同构：

| 侧 | 写什么 | 例子 |
|---|---|---|
| LM | 事件摘要（发生了什么） | 「和 HiMZ 讨论便携屏一线连方案，确定用 Type-C 合成」 |
| PC | 结构化人物字段（关于这个人） | `companion_memory`: 喜欢硬件折腾；`open_loops`: 待交付 PCB 打样 |

要求：PC 侧不写原文摘要，只写 `companion_memory` / `open_loops` / `action_preferences` / `behavior_habits` 这类字段。这样重复只是"同源"，不是"同义"。

---

## 七、可观测性

- **LM**：`trace.notes` 追加 `atom_type_filter:{n}`，`/lmem trace` 可直接看到本次注入来自桥接。
- **PC**：`GET /diagnostics`（`page_api.py:1286`）新增字段：

```json
"livingmemory_bridge": {
  "ok": true, "reason": "ok", "items": 4, "chars": 812,
  "elapsed_ms": 96, "scope": "livingmemory:user:aiocqhttp:12345", "at": 1763...
}
```

注入块首行带不可见标记 `<!-- lm-bridge:v1 -->`，便于从日志里确认这段是桥接产出的。

---

## 八、回滚

| 想回到 | 操作 | 是否需重启 |
|---|---|---|
| 2.14.0 的 PC 行为（只有提示词引导） | `livingmemory_bridge_enabled=false` | 是（PC 重载） |
| LM 档案注入回来 | `profile_settings.enabled=true` | 是 |
| 群聊重新塞入全部类型记忆 | 桥接传 `allowed_atom_types=None` | 是 |

无数据库迁移，无 schema 变更，无新表。

---

## 九、验收清单

1. **私聊正常**：发一条消息，PC 诊断显示 `reason=ok`，注入块含「长期记忆」段，字符数 ≤1500。
2. **群聊锁人**：构造 A、B 两条私有记忆（`metadata.privacy=private:livingmemory:user:<B>`），B 不在场时 A 说话，B 的记忆不出现。
3. **群聊不锁气氛**：关系边注入仍然存在（≤4 条），且不含任何 `relational`/`preference` 类型的 LM 记忆。
4. **降级不炸**：停用 LM 插件后，PC 正常回复，诊断显示 `reason=plugin_missing`，日志无 traceback。
5. **类型过滤计数**：传 `allowed_atom_types=["episodic","factual"]`，含 `relational` 的记忆被丢弃，`rejected["atom_type"]` 数值正确。
6. **静态检查**：`python -m compileall -q core main.py` 退出码 0；新增测试 `tests/test_bridge_contract.py`（LM 侧）通过。

---

## 十、不在本期范围

- **模型校验层**（Q13 的 (b)）：每轮多一次 LLM 调用，等有真实误报样本再上。本期靠规则：speaker lock + privacy + AtomType 过滤。
- **频道公共记忆打通**：PC 仍不构造 `livingmemory:channel:*`；要让 PC 参与群级公共记忆，需另做一轮设计。
- **PC 的 `enable_group_episode_memory` 默认值不一致**：schema/bootstrap 写 `true`、`group_observation.py:4883` 用 `False`。这是独立 bug，不在本设计内修。
- **LM 侧任何对 PC 的感知**：一期不引入反向依赖。

---

## English Summary

LivingMemory (LM) owns memory; Private Companion (PC) owns persona and relationships. Dependency is one-way: PC calls LM in-process, LM knows nothing about PC.

**Phase 1, four changes:**

1. Disable LM's profile injection (`profile_settings.enabled=false`). The `memory_profiles` table is currently empty and its only writer is a default-off tool, so this is a no-op in practice.
2. Add `livingmemory_bridge.py` to PC: resolve LM via `context.get_registered_star(...).star_cls.initializer.memory_engine`, call `search_memories(...)` under a 1.2 s timeout, render its own compact bullet list (never reuse LM's `<RAG-Faiss-Memory>` formatter), inject as `PromptSection(key="livingmemory.recall", priority=74)`. All failures degrade to an empty string with a `reason` code.
3. Add `allowed_atom_types` to LM's `search_memories`; filter on `metadata.atom_types` after the cache write, so the cache stays unfiltered and shared.
4. Group chat is two-layered: member-scoped memory is locked to the current speaker; group-scoped mood/relationship edges stay open, but LM contributes only `episodic`/`factual` types.

**Budgets:** persona 600 chars / top_k 3; memory 1500 chars / top_k 4; total ≤2100 (down from a worst case of 3900).

**Identity:** PC maps its five-tuple identity to `livingmemory:user:<platform>:<identity>`, honouring `identity_links` so one person with several accounts shares memory. LM only receives the string.

**Dual writes:** LM stores event summaries; PC stores structured person fields only. Same source, different shape — no duplicated prose.

**Rollback:** flip `livingmemory_bridge_enabled` off. No schema change, no migration.

**Out of scope:** an LLM "is this memory appropriate here" judge (deferred until real false positives exist), wiring PC into `livingmemory:channel:*`, and fixing PC's `enable_group_episode_memory` default mismatch.
