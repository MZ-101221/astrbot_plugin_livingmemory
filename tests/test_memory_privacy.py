"""privacy 逐条标签的单元测试（纯函数，不依赖 AstrBot 运行时）。"""

from astrbot_plugin_livingmemory.core.memory_privacy import (
    PRIVACY_METADATA_KEY,
    PRIVACY_PUBLIC,
    USER_SCOPE_PREFIX,
    apply_privacy_field,
    config_value,
    filter_by_privacy,
    is_private_label,
    metadata_privacy,
    normalize_privacy_label,
    privacy_owner,
    privacy_visible,
    private_label,
)

OWNER = f"{USER_SCOPE_PREFIX}aiocqhttp:10001"
OTHER = f"{USER_SCOPE_PREFIX}aiocqhttp:10002"


def test_normalize_privacy_label_accepts_known_forms() -> None:
    """只有 public / private / private:<scope> 三种形态，其余一律回落 public。"""
    assert normalize_privacy_label(None) == PRIVACY_PUBLIC
    assert normalize_privacy_label("") == PRIVACY_PUBLIC
    assert normalize_privacy_label("PUBLIC") == PRIVACY_PUBLIC
    # 没有归属作用域时保留无主的 private: 前缀（严格模式下不可见），
    # 不能被误判成公开记忆。
    assert normalize_privacy_label("private") == "private:"
    assert normalize_privacy_label("private", owner_scope=OWNER) == f"private:{OWNER}"
    assert normalize_privacy_label(f"private:{OWNER}") == f"private:{OWNER}"
    assert normalize_privacy_label("nonsense") == PRIVACY_PUBLIC
    assert private_label(None) == "private:"
    assert private_label(OWNER) == f"private:{OWNER}"


def test_owner_and_metadata_helpers() -> None:
    label = private_label(OWNER)
    assert is_private_label(label) is True
    assert is_private_label(PRIVACY_PUBLIC) is False
    assert privacy_owner(label) == OWNER
    assert privacy_owner(PRIVACY_PUBLIC) is None
    assert metadata_privacy({PRIVACY_METADATA_KEY: label}) == label
    assert metadata_privacy({}) == PRIVACY_PUBLIC
    assert metadata_privacy("not-a-dict") == PRIVACY_PUBLIC


def test_privacy_visible_matrix() -> None:
    """public 恒可见；私有只回给归属者；群聊不比对会话 ID。"""
    public = {PRIVACY_METADATA_KEY: PRIVACY_PUBLIC}
    mine = {PRIVACY_METADATA_KEY: private_label(OWNER)}
    theirs = {PRIVACY_METADATA_KEY: private_label(OTHER)}

    assert privacy_visible(public, viewer_scope=OTHER, is_group=True) is True
    assert privacy_visible(mine, viewer_scope=OWNER, is_group=True) is True
    assert privacy_visible(theirs, viewer_scope=OWNER, is_group=True) is False
    # 私聊：会话 ID 与归属一致时可见（session 作用域写入的私有标签）
    assert (
        privacy_visible(
            mine, viewer_scope=None, viewer_session_id=OWNER, is_group=False
        )
        is True
    )
    # 群聊：不比对会话 ID，避免同群其他成员读到本人私有记忆
    assert (
        privacy_visible(
            mine, viewer_scope=None, viewer_session_id=OWNER, is_group=True
        )
        is False
    )


def test_unowned_private_label_follows_strict_mode() -> None:
    """无归属的私有标签：严格模式下不可见，宽松模式下放行。"""
    metadata = {PRIVACY_METADATA_KEY: "private:"}
    assert (
        privacy_visible(
            metadata, viewer_scope=OWNER, strict_in_group=True, is_group=True
        )
        is False
    )
    assert (
        privacy_visible(
            metadata, viewer_scope=OWNER, strict_in_group=False, is_group=True
        )
        is True
    )


def test_filter_by_privacy_reports_removed_count() -> None:
    items = [
        {"id": 1, "metadata": {PRIVACY_METADATA_KEY: PRIVACY_PUBLIC}},
        {"id": 2, "metadata": {PRIVACY_METADATA_KEY: private_label(OWNER)}},
        {"id": 3, "metadata": {PRIVACY_METADATA_KEY: private_label(OTHER)}},
        {"id": 4},
    ]
    kept, removed = filter_by_privacy(items, viewer_scope=OWNER, is_group=True)
    assert [item["id"] for item in kept] == [1, 2, 4]
    assert removed == 1

    kept_all, removed_all = filter_by_privacy(
        items, viewer_scope=OWNER, is_group=True, enabled=False
    )
    assert len(kept_all) == 4
    assert removed_all == 0


def test_config_value_supports_three_config_shapes() -> None:
    """扁平 dict、嵌套 dict、ConfigManager 点号键都要能取到值。"""

    class DottedConfig:
        def __init__(self, data: dict) -> None:
            self._data = data

        def get(self, key: str, default=None):
            node = self._data
            for part in key.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return node

    nested = {"privacy_settings": {"enabled": True}}
    assert config_value(nested, "privacy_settings.enabled", False) is True
    assert config_value(DottedConfig(nested), "privacy_settings.enabled", False) is True
    assert config_value({"privacy_settings.enabled": True}, "privacy_settings.enabled") is True
    assert config_value({}, "privacy_settings.enabled", "fallback") == "fallback"


def test_apply_privacy_field_respects_default_label() -> None:
    metadata: dict = {}
    assert apply_privacy_field(metadata, owner_scope=OWNER) == PRIVACY_PUBLIC
    assert metadata[PRIVACY_METADATA_KEY] == PRIVACY_PUBLIC

    metadata = {}
    label = apply_privacy_field(metadata, owner_scope=OWNER, default_label="private")
    assert label == private_label(OWNER)
    assert metadata[PRIVACY_METADATA_KEY] == label

    # 已有显式标签时不覆盖
    metadata = {PRIVACY_METADATA_KEY: PRIVACY_PUBLIC}
    assert apply_privacy_field(metadata, owner_scope=OWNER, default_label="private") == (
        PRIVACY_PUBLIC
    )
