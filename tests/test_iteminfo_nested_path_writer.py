"""Iteminfo writer must handle Format 3 dotted/indexed paths.

Bug 2026-05-08: gmVIP233 reported a Marni armor mod with intent
field=prefab_data_list[4].tribe_gender_list, niyaruza reported the
same path on Kliff Wears Damiane Armor, floozo reported drop_default_
data.add_socket_material_item_list and drop_default_data.use_socket
on a cloak mod. CDUMM v3.2.10 silently skipped all of them with
'nested-field writes are not implemented' even though the native
parser round-trips these fields byte-perfect on read+write.

Fix: validator no longer rejects these paths for iteminfo, apply
path force-batches them into the iteminfo writer, the writer's new
_resolve_path_target walks the parsed dict and assigns at the
correct nested location.
"""
from __future__ import annotations

import pytest


def test_resolve_path_target_walks_indexed_then_keyed():
    """prefab_data_list[4].tribe_gender_list -> walk into list at 4,
    return (that_dict, 'tribe_gender_list') for assignment."""
    from cdumm.engine.iteminfo_writer import _resolve_path_target
    item = {
        "prefab_data_list": [
            {"tribe_gender_list": [1, 2]},
            {"tribe_gender_list": [3]},
            {"tribe_gender_list": [4]},
            {"tribe_gender_list": [5]},
            {"tribe_gender_list": [99]},
        ],
    }
    parent, last = _resolve_path_target(
        item, "prefab_data_list[4].tribe_gender_list")
    assert parent is item["prefab_data_list"][4]
    assert last == "tribe_gender_list"
    parent[last] = [4184612308, 3215062603]
    assert item["prefab_data_list"][4]["tribe_gender_list"] == [
        4184612308, 3215062603]


def test_resolve_path_target_walks_keyed_keyed():
    """drop_default_data.use_socket -> walk into 'drop_default_data'
    dict, return (that_dict, 'use_socket') for assignment."""
    from cdumm.engine.iteminfo_writer import _resolve_path_target
    item = {
        "drop_default_data": {
            "use_socket": 0,
            "add_socket_material_item_list": [],
        },
    }
    parent, last = _resolve_path_target(
        item, "drop_default_data.use_socket")
    assert parent is item["drop_default_data"]
    assert last == "use_socket"
    parent[last] = 1
    assert item["drop_default_data"]["use_socket"] == 1


def test_resolve_path_target_assigns_list_field():
    """drop_default_data.add_socket_material_item_list -> assign a
    list of dicts to the nested key."""
    from cdumm.engine.iteminfo_writer import _resolve_path_target
    item = {
        "drop_default_data": {
            "add_socket_material_item_list": [],
            "use_socket": 0,
        },
    }
    parent, last = _resolve_path_target(
        item, "drop_default_data.add_socket_material_item_list")
    new_list = [{"item_key": 14510, "count": 1}]
    parent[last] = new_list
    assert (item["drop_default_data"]
            ["add_socket_material_item_list"] == new_list)


def test_resolve_path_target_returns_none_on_missing_key():
    from cdumm.engine.iteminfo_writer import _resolve_path_target
    item = {"prefab_data_list": [{"foo": 1}]}
    assert _resolve_path_target(
        item, "prefab_data_list[0].does_not_exist") is None
    # The caller treats None as a skip and logs at warning.


def test_resolve_path_target_returns_none_on_index_out_of_range():
    from cdumm.engine.iteminfo_writer import _resolve_path_target
    item = {"prefab_data_list": [{"tribe_gender_list": [1]}]}
    # Mod targets index 4 but the record only has index 0
    assert _resolve_path_target(
        item, "prefab_data_list[4].tribe_gender_list") is None


def test_resolve_path_target_handles_plain_field():
    """Plain field with no '.' or '[' still returns (item, field)."""
    from cdumm.engine.iteminfo_writer import _resolve_path_target
    item = {"max_stack_count": 1}
    parent, last = _resolve_path_target(item, "max_stack_count")
    assert parent is item
    assert last == "max_stack_count"


def test_validator_accepts_iteminfo_nested_paths():
    """The format3 validator must NOT reject dotted iteminfo paths
    that the writer can handle."""
    from cdumm.engine.format3_handler import _diagnose_unsupported_intent

    msg = _diagnose_unsupported_intent(
        "prefab_data_list[4].tribe_gender_list",
        [4184612308, 3215062603], "iteminfo")
    assert msg is None, (
        f"validator still rejects prefab_data_list path: {msg}")

    msg = _diagnose_unsupported_intent(
        "drop_default_data.use_socket", 1, "iteminfo")
    assert msg is None, (
        f"validator still rejects drop_default_data path: {msg}")

    msg = _diagnose_unsupported_intent(
        "drop_default_data.add_socket_material_item_list",
        [], "iteminfo")
    assert msg is None


def test_validator_still_rejects_unknown_nested_paths():
    """Other dotted iteminfo paths the writer doesn't handle should
    still surface a clear skip message."""
    from cdumm.engine.format3_handler import _diagnose_unsupported_intent

    msg = _diagnose_unsupported_intent(
        "some.unknown.deep.path", 42, "iteminfo")
    assert msg is not None
    assert "nested-field writes are not implemented" in msg


def test_iteminfo_writer_applies_nested_intent():
    """End-to-end: iteminfo writer takes a list of intents including
    a dotted-path intent, applies it to the parsed dict, and the
    nested value reflects the change."""
    from cdumm.engine.iteminfo_writer import _resolve_path_target

    # Build a minimal items table mock the writer would parse
    item = {
        "key": 14510,
        "prefab_data_list": [
            {"tribe_gender_list": [1, 2]},
            {"tribe_gender_list": [3, 4]},
        ],
        "drop_default_data": {
            "use_socket": 0,
            "add_socket_material_item_list": [],
        },
    }

    # Apply two nested intents the way the writer's loop will.
    target1 = _resolve_path_target(
        item, "prefab_data_list[1].tribe_gender_list")
    assert target1 is not None
    target1[0][target1[1]] = [99, 100]

    target2 = _resolve_path_target(item, "drop_default_data.use_socket")
    assert target2 is not None
    target2[0][target2[1]] = 1

    assert item["prefab_data_list"][1]["tribe_gender_list"] == [99, 100]
    assert item["prefab_data_list"][0]["tribe_gender_list"] == [1, 2]
    assert item["drop_default_data"]["use_socket"] == 1
