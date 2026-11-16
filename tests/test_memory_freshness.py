"""记忆时效状态（time_status）与注入提醒的单元测试。"""

from datetime import datetime, timezone

from astrbot_plugin_livingmemory.core.memory_freshness import (
    TIME_STATUS_CURRENT,
    TIME_STATUS_OUTDATED,
    TIME_STATUS_PENDING,
    TIME_STATUS_TIMELESS,
    VALID_UNTIL_METADATA_KEY,
    annotate_time_status,
    apply_valid_until_field,
    derive_time_status,
    freshness_notice,
    parse_valid_until,
    time_status_label,
)

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc).timestamp()
FUTURE = "2027-01-01"
PAST = "2026-01-01"


def test_parse_valid_until_supported_formats() -> None:
    """支持日期、日期时间、ISO 8601、epoch 秒与数字字符串。"""
    assert parse_valid_until(FUTURE) == datetime(
        2027, 1, 1, tzinfo=timezone.utc
    ).timestamp()
    assert parse_valid_until("2027-01-01 08:30") == datetime(
        2027, 1, 1, 8, 30, tzinfo=timezone.utc
    ).timestamp()
    assert parse_valid_until("2027-01-01T08:30:00") == datetime(
        2027, 1, 1, 8, 30, tzinfo=timezone.utc
    ).timestamp()
    assert parse_valid_until("1798761600") == 1798761600.0
    assert parse_valid_until(1798761600) == 1798761600.0


def test_parse_valid_until_rejects_invalid_values() -> None:
    assert parse_valid_until(None) is None
    assert parse_valid_until("") is None
    assert parse_valid_until("not-a-date") is None
    assert parse_valid_until(-5) is None
    assert parse_valid_until(True) is None


def test_derive_time_status_four_states() -> None:
    """四态推导：无时效 / 有效 / 待复核 / 已取代。"""
    assert derive_time_status({}, now=NOW) == TIME_STATUS_TIMELESS
    assert (
        derive_time_status({VALID_UNTIL_METADATA_KEY: FUTURE}, now=NOW)
        == TIME_STATUS_CURRENT
    )
    assert (
        derive_time_status({VALID_UNTIL_METADATA_KEY: PAST}, now=NOW)
        == TIME_STATUS_PENDING
    )
    # 取代关系优先于有效期
    assert (
        derive_time_status(
            {"superseded_by": 7, VALID_UNTIL_METADATA_KEY: FUTURE}, now=NOW
        )
        == TIME_STATUS_OUTDATED
    )
    assert derive_time_status("not-a-dict", now=NOW) == TIME_STATUS_TIMELESS


def test_annotate_and_labels() -> None:
    items = [
        {"metadata": {VALID_UNTIL_METADATA_KEY: PAST}},
        {"metadata": {}},
    ]
    annotated = annotate_time_status(items, now=NOW)
    assert [entry["time_status"] for entry in annotated] == [
        TIME_STATUS_PENDING,
        TIME_STATUS_TIMELESS,
    ]
    assert annotated[0]["item"] is items[0]
    assert time_status_label(TIME_STATUS_PENDING) == "待复核"
    assert time_status_label(TIME_STATUS_OUTDATED) == "已取代"
    assert time_status_label("unknown") == "无时效"


def test_freshness_notice_counts_and_switches() -> None:
    """提醒文本按状态聚合，且可分别关闭。"""
    items = [
        {"metadata": {VALID_UNTIL_METADATA_KEY: PAST}},
        {"metadata": {"superseded_by": 3}},
    ]
    notice = freshness_notice(items, now=NOW)
    assert "待复核" in notice
    assert "已取代" in notice

    assert freshness_notice([{"metadata": {}}], now=NOW) == ""
    assert (
        freshness_notice(
            items, now=NOW, remind_expired=False, remind_superseded=False
        )
        == ""
    )
    only_superseded = freshness_notice(
        items, now=NOW, remind_expired=False, remind_superseded=True
    )
    assert "已取代" in only_superseded
    assert "待复核" not in only_superseded


def test_apply_valid_until_field_normalizes_and_clears() -> None:
    metadata: dict = {VALID_UNTIL_METADATA_KEY: FUTURE}
    assert apply_valid_until_field(metadata) == datetime(
        2027, 1, 1, tzinfo=timezone.utc
    ).timestamp()
    assert isinstance(metadata[VALID_UNTIL_METADATA_KEY], float)

    invalid: dict = {VALID_UNTIL_METADATA_KEY: "not-a-date"}
    assert apply_valid_until_field(invalid) is None
    assert VALID_UNTIL_METADATA_KEY not in invalid


def test_injection_formatter_embeds_notice() -> None:
    """format_memories_for_injection 在 header 之后插入提醒文本。"""
    from astrbot_plugin_livingmemory.core.utils.formatting import (
        format_memories_for_injection,
    )

    memories = [
        {
            "id": 1,
            "content": "张三喜欢黑咖啡",
            "score": 0.9,
            "metadata": {},
            "timestamp": NOW,
        }
    ]
    plain = format_memories_for_injection(memories)
    with_notice = format_memories_for_injection(memories, notice="时效提醒：测试")
    assert "时效提醒：测试" in with_notice
    assert "时效提醒：测试" not in plain
    assert len(with_notice) > len(plain)
