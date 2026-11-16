"""逐条隐私标签（privacy）的取值构造、解析与可见性判定。

设计要点：

- 标签只存在于 ``documents.metadata.privacy``，不新增表、不新增列。
- 取值两种形态：``public``（默认，所有人可见）与 ``private:<owner_scope>``。
- ``owner_scope`` 用**写入者**的用户级作用域（``livingmemory:user:<平台>:<身份>``），
  而不是会话 ID。这样无论用户把 ``memory_scope_mode`` 切成 ``legacy`` /
  ``session`` / ``user`` / ``global``，同一条私有记忆的归属都不会漂移。
- 缺失标签一律按 ``public`` 处理，因此升级不需要回填数据。
- 总开关 ``privacy_settings.enabled`` 默认开启；关闭时本模块的过滤函数
  直接返回原列表，行为与 2.13.0 完全一致。
"""

from __future__ import annotations

from typing import Any, Iterable

PRIVACY_PUBLIC = "public"
PRIVACY_PRIVATE_PREFIX = "private:"
PRIVACY_METADATA_KEY = "privacy"
#: 用户级作用域前缀，与 ``core.memory_scope.resolve_user_memory_scope`` 保持一致。
USER_SCOPE_PREFIX = "livingmemory:user:"


def config_value(config: Any, key: str, default: Any = None) -> Any:
    """读取配置项，兼容 ConfigManager、嵌套 dict 与扁平点号 dict 三种形态。

    Args:
        config: ConfigManager 实例或配置 dict。
        key: 支持点号分隔的嵌套键，如 ``privacy_settings.enabled``。
        default: 缺失时的返回值。

    Returns:
        配置值。
    """
    if config is None:
        return default
    getter = getattr(config, "get", None)
    if callable(getter):
        try:
            value = getter(key, None)
        except TypeError:
            value = None
        if value is not None:
            return value
    current: Any = config
    for part in key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return default if current is None else current



def normalize_privacy_label(value: Any, *, owner_scope: str | None = None) -> str:
    """把任意输入归一化为合法标签。

    Args:
        value: 原始输入（``public`` / ``private`` / ``private:<scope>`` / None）。
        owner_scope: 写入者作用域；``private`` 不带作用域时用它补齐。

    Returns:
        合法标签；无法判定为私有时返回 ``public``。
    """
    text = str(value or "").strip()
    if not text:
        return PRIVACY_PUBLIC
    lowered = text.casefold()
    if lowered == PRIVACY_PUBLIC:
        return PRIVACY_PUBLIC
    if lowered == PRIVACY_PRIVATE_PREFIX.rstrip(":"):
        return private_label(owner_scope)
    if lowered.startswith(PRIVACY_PRIVATE_PREFIX):
        owner = text[len(PRIVACY_PRIVATE_PREFIX) :].strip()
        if not owner:
            return private_label(owner_scope)
        return f"{PRIVACY_PRIVATE_PREFIX}{owner}"
    return PRIVACY_PUBLIC


def private_label(owner_scope: str | None) -> str:
    """构造 ``private:<owner_scope>`` 标签。

    归属作用域缺失时返回无主的 ``private:`` 前缀——这类标签在严格模式下
    不可见（fail-closed），不会被误当作公开记忆。
    """
    owner = str(owner_scope or "").strip()
    return f"{PRIVACY_PRIVATE_PREFIX}{owner}"


def is_private_label(value: Any) -> bool:
    """判断标签是否为私有。"""
    return str(value or "").strip().casefold().startswith(PRIVACY_PRIVATE_PREFIX)


def privacy_owner(value: Any) -> str | None:
    """取出私有标签的归属作用域；非私有标签返回 None。"""
    text = str(value or "").strip()
    if not text.casefold().startswith(PRIVACY_PRIVATE_PREFIX):
        return None
    owner = text[len(PRIVACY_PRIVATE_PREFIX) :].strip()
    return owner or None


def metadata_privacy(metadata: Any) -> str:
    """从 metadata 读取标签，缺失或非法时返回 ``public``。"""
    if not isinstance(metadata, dict):
        return PRIVACY_PUBLIC
    return normalize_privacy_label(metadata.get(PRIVACY_METADATA_KEY))


def apply_privacy_field(
    metadata: dict[str, Any],
    *,
    owner_scope: str | None,
    default_label: str = PRIVACY_PUBLIC,
) -> str:
    """就地规范化 ``metadata["privacy"]``，供写入侧复用。

    Args:
        metadata: 待写入的 metadata（会被就地修改）。
        owner_scope: 本次写入的存储作用域，作为私有标签的归属。
        default_label: 模型未给出标签时的默认值（``public`` / ``private``）。

    Returns:
        规范化后的标签。
    """
    if not isinstance(metadata, dict):
        return PRIVACY_PUBLIC
    raw = metadata.get(PRIVACY_METADATA_KEY)
    if not str(raw or "").strip() and str(default_label or "").strip().casefold() == (
        PRIVACY_PRIVATE_PREFIX.rstrip(":")
    ):
        raw = PRIVACY_PRIVATE_PREFIX
    label = normalize_privacy_label(raw, owner_scope=owner_scope)
    metadata[PRIVACY_METADATA_KEY] = label
    return label


def privacy_visible(
    metadata: Any,
    *,
    viewer_scope: str | None,
    viewer_session_id: str | None = None,
    strict_in_group: bool = True,
    is_group: bool = False,
) -> bool:
    """判断一条记忆对当前观察者是否可见。

    Args:
        metadata: 记忆 metadata。
        viewer_scope: 当前发言者的用户级作用域；None 表示无法确定观察者。
        strict_in_group: 群聊下是否把无主私有记忆视为不可见。
        is_group: 当前事件是否群聊。

    Returns:
        可见返回 True。
    """
    label = metadata_privacy(metadata)
    if not is_private_label(label):
        return True
    owner = privacy_owner(label)
    if not owner:
        # 私有但无归属：只有在严格模式下才拒绝，避免历史脏数据全部消失。
        return not strict_in_group
    viewer = str(viewer_scope or "").strip()
    if viewer and viewer == owner:
        return True
    # 私聊下兼容以会话 ID 作为归属的私有标签；群聊不比对会话 ID，
    # 否则同群其他人会读到本人的私有记忆。
    session_id = str(viewer_session_id or "").strip()
    if not is_group and session_id and session_id == owner:
        return True
    return False


def filter_by_privacy(
    items: Iterable[Any],
    *,
    viewer_scope: str | None,
    viewer_session_id: str | None = None,
    strict_in_group: bool = True,
    is_group: bool = False,
    enabled: bool = True,
) -> tuple[list[Any], int]:
    """按隐私标签过滤候选列表。

    Args:
        items: 候选对象列表，需带 ``metadata`` 属性或为 dict。
        viewer_scope: 当前发言者的用户级作用域。
        strict_in_group: 群聊下是否严格过滤。
        is_group: 当前事件是否群聊。
        enabled: 总开关；关闭时原样返回。

    Returns:
        ``(保留列表, 被过滤条数)``。
    """
    candidates = list(items)
    if not enabled:
        return candidates, 0
    kept: list[Any] = []
    removed = 0
    for item in candidates:
        metadata = item.get("metadata") if isinstance(item, dict) else getattr(
            item, "metadata", None
        )
        if privacy_visible(
            metadata,
            viewer_scope=viewer_scope,
            viewer_session_id=viewer_session_id,
            strict_in_group=strict_in_group,
            is_group=is_group,
        ):
            kept.append(item)
        else:
            removed += 1
    return kept, removed


__all__ = [
    "PRIVACY_METADATA_KEY",
    "PRIVACY_PUBLIC",
    "PRIVACY_PRIVATE_PREFIX",
    "USER_SCOPE_PREFIX",
    "apply_privacy_field",
    "config_value",
    "filter_by_privacy",
    "is_private_label",
    "metadata_privacy",
    "normalize_privacy_label",
    "privacy_owner",
    "privacy_visible",
    "private_label",
]
