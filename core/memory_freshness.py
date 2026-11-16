"""记忆时效状态（time_status）的解析与派生。

设计要点：

- **不落库**。只持久化 ``metadata.valid_until``（epoch 秒，缺失/None 表示无时效）。
- ``time_status`` 每次读时派生，取值四态：

  ===========  ==============================================
  ``timeless`` ``valid_until`` 为空
  ``current``  ``valid_until`` 尚未到期
  ``pending``  ``valid_until`` 已过期且没有被取代
  ``outdated`` 存在 ``superseded_by``（取代优先于过期）
  ===========  ==============================================

- 取代判定直接复用上游 2.10.0 的 ``superseded_by``，不新增指针。
- 注入前缀按状态合并成一行，不逐条追加，避免挤压注入预算。
- 总开关 ``freshness_settings.enabled`` 默认关闭。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

TIME_STATUS_TIMELESS = "timeless"
TIME_STATUS_CURRENT = "current"
TIME_STATUS_PENDING = "pending"
TIME_STATUS_OUTDATED = "outdated"

VALID_UNTIL_METADATA_KEY = "valid_until"

TIME_STATUS_LABELS = {
    TIME_STATUS_TIMELESS: "无时效",
    TIME_STATUS_CURRENT: "有效",
    TIME_STATUS_PENDING: "待复核",
    TIME_STATUS_OUTDATED: "已取代",
}

_NOTICE_PENDING = "以下记忆已过有效期，引用前请先确认是否仍然成立。"
_NOTICE_OUTDATED = "以下记忆已被后续记忆取代，请优先参考较新的内容。"


def parse_valid_until(value: Any) -> float | None:
    """把多种输入形态解析为 epoch 秒。

    Args:
        value: epoch 秒（int/float/数字字符串）、ISO 8601 字符串、
            ``YYYY-MM-DD HH:MM[:SS]``、``YYYY-MM-DD``，或 None。

    Returns:
        epoch 秒；无法解析或为空时返回 None。
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        number = None
    if number is not None:
        return number if number > 0 else None
    candidate = text.replace("/", "-").replace("Z", "+00:00")
    if candidate.endswith("+00:00"):
        pass
    for parser in (
        lambda raw: datetime.fromisoformat(raw),
        lambda raw: datetime.strptime(raw, "%Y-%m-%d %H:%M:%S"),
        lambda raw: datetime.strptime(raw, "%Y-%m-%d %H:%M"),
        lambda raw: datetime.strptime(raw, "%Y-%m-%d"),
    ):
        try:
            parsed = parser(candidate)
        except (TypeError, ValueError):
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    return None


def apply_valid_until_field(metadata: dict[str, Any]) -> float | None:
    """就地规范化 ``metadata["valid_until"]``，供写入侧复用。

    非法或空值会被移除，保持 metadata 结构与升级前一致。

    Args:
        metadata: 待写入的 metadata（会被就地修改）。

    Returns:
        规范化后的 epoch 秒；无有效时效时返回 None。
    """
    if not isinstance(metadata, dict):
        return None
    parsed = parse_valid_until(metadata.get(VALID_UNTIL_METADATA_KEY))
    if parsed is None:
        metadata.pop(VALID_UNTIL_METADATA_KEY, None)
    else:
        metadata[VALID_UNTIL_METADATA_KEY] = parsed
    return parsed


def derive_time_status(metadata: Any, *, now: float | None = None) -> str:
    """派生一条记忆的时效状态。

    Args:
        metadata: 记忆 metadata。
        now: 参照时间（epoch 秒），默认取当前时间。

    Returns:
        四态之一。
    """
    if not isinstance(metadata, dict):
        return TIME_STATUS_TIMELESS
    if metadata.get("superseded_by") is not None:
        return TIME_STATUS_OUTDATED
    valid_until = parse_valid_until(metadata.get(VALID_UNTIL_METADATA_KEY))
    if valid_until is None:
        return TIME_STATUS_TIMELESS
    reference = now if now is not None else datetime.now(tz=timezone.utc).timestamp()
    return TIME_STATUS_CURRENT if valid_until > reference else TIME_STATUS_PENDING


def annotate_time_status(
    items: Iterable[Any], *, now: float | None = None
) -> list[dict[str, Any]]:
    """给候选列表逐条附加派生状态（用于列表接口/仪表盘）。

    Args:
        items: 候选对象列表，需带 ``metadata`` 属性或为 dict。
        now: 参照时间。

    Returns:
        ``[{"item": 原对象, "time_status": 状态, "valid_until": 时间戳}]``。
    """
    annotated: list[dict[str, Any]] = []
    for item in items:
        metadata = (
            item.get("metadata")
            if isinstance(item, dict)
            else getattr(item, "metadata", None)
        )
        annotated.append(
            {
                "item": item,
                "time_status": derive_time_status(metadata, now=now),
                "valid_until": parse_valid_until(
                    (metadata or {}).get(VALID_UNTIL_METADATA_KEY)
                    if isinstance(metadata, dict)
                    else None
                ),
            }
        )
    return annotated


def freshness_notice(
    items: Iterable[Any],
    *,
    now: float | None = None,
    remind_expired: bool = True,
    remind_superseded: bool = True,
) -> str:
    """生成注入用的时效前缀文本。

    Args:
        items: 本轮准备注入的候选。
        now: 参照时间。
        remind_expired: 是否提示 ``pending``。
        remind_superseded: 是否提示 ``outdated``。

    Returns:
        前缀文本；无需提示时返回空字符串。
    """
    pending = 0
    outdated = 0
    for entry in annotate_time_status(items, now=now):
        status = entry["time_status"]
        if status == TIME_STATUS_PENDING:
            pending += 1
        elif status == TIME_STATUS_OUTDATED:
            outdated += 1
    lines: list[str] = []
    if remind_superseded and outdated:
        lines.append(
            f"时效提醒（{TIME_STATUS_LABELS[TIME_STATUS_OUTDATED]}，"
            f"{outdated} 条）：{_NOTICE_OUTDATED}"
        )
    if remind_expired and pending:
        lines.append(
            f"时效提醒（{TIME_STATUS_LABELS[TIME_STATUS_PENDING]}，"
            f"{pending} 条）：{_NOTICE_PENDING}"
        )
    return "\n".join(lines)


def time_status_label(status: str) -> str:
    """返回状态的中文短标签（仪表盘用）。"""
    return TIME_STATUS_LABELS.get(str(status or ""), TIME_STATUS_LABELS[TIME_STATUS_TIMELESS])


__all__ = [
    "TIME_STATUS_CURRENT",
    "TIME_STATUS_LABELS",
    "TIME_STATUS_OUTDATED",
    "TIME_STATUS_PENDING",
    "TIME_STATUS_TIMELESS",
    "VALID_UNTIL_METADATA_KEY",
    "annotate_time_status",
    "apply_valid_until_field",
    "derive_time_status",
    "freshness_notice",
    "parse_valid_until",
    "time_status_label",
]
