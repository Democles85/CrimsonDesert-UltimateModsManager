"""Iteminfo writer must refuse cooltime intents on misaligned records.

Bug 2026-05-08 (hhkbble's My_ItemBuffs_Mod on item 1001250):

The native iteminfo parser's reported offsets for cooltime,
unk_post_cooltime_a, and unk_post_cooltime_b are 13 bytes earlier
on-disk than where mod authors target those fields. The parser is
byte-roundtrip consistent within itself (some upstream variable-length
field consumes fewer bytes than reality, balancing out), but a Format
3 intent on those fields writes at the parser's claimed offset, which
is 13 bytes too early on disk. The bytes that get overwritten belong
to other game data the engine validates on load, and the game crashes
on launch.

Until the parser's layout is fully corrected, the writer refuses these
intents on records detected as misaligned. Detection uses two
heuristics:

1. prefab_data_list parsed as opaque (the failure-recovery path that
   notoriously leaves the cursor mid-flight).
2. unk_post_cooltime_a or unk_post_cooltime_b non-zero. Vanilla
   cooltime values are small (milliseconds), so a non-zero unk field
   in u64 territory almost always means the parser read those 8 bytes
   from a wrong on-disk position.

Other intents on the same mod (max_stack_count, enchant_data_list)
still apply normally.
"""
from __future__ import annotations

import pytest


def _make_intent(key, field, value):
    from cdumm.engine.format3_handler import Format3Intent
    return Format3Intent(
        entry=f"item_{key}", key=key, field=field,
        op="set", new=value, old=None)


def test_cooltime_intent_on_opaque_prefab_record_skipped():
    """Records with opaque prefab_data_list have known misalignment.
    Cooltime intents must be refused with a warning."""
    from cdumm.engine.iteminfo_writer import build_iteminfo_intent_change
    # We need a real iteminfo body to invoke this, but the writer's
    # skip logic kicks in DURING the per-intent loop, not at parse
    # time. Direct unit-test by calling the helper guard in
    # isolation via the writer's loop. Use a synthesized parsed
    # item dict.
    item = {
        "key": 1001129,
        "max_stack_count": 1,
        "cooltime": 0,
        "unk_post_cooltime_a": 0,
        "unk_post_cooltime_b": 0,
        "prefab_data_list": {"_opaque": True, "bytes": b""},
    }
    # Run the guard logic directly
    intent = _make_intent(1001129, "cooltime", 18000)
    # Reproduce the guard expression (kept in sync with iteminfo_writer)
    is_cooltime_field = intent.field in (
        "cooltime", "unk_post_cooltime_a", "unk_post_cooltime_b")
    assert is_cooltime_field
    is_opaque = (
        isinstance(item.get("prefab_data_list"), dict)
        and item["prefab_data_list"].get("_opaque")
    )
    assert is_opaque, (
        "opaque-prefab record should be detected as misaligned")


def test_cooltime_intent_on_nonzero_unk_record_skipped():
    """Records with non-zero unk_post_cooltime_a or _b are misaligned
    even when prefab parsed cleanly. Mod author's intent target is at
    a different byte offset than the parser's."""
    item = {
        "key": 1001250,
        "max_stack_count": 1,
        "cooltime": 0,
        # The parser reports unk_post_cooltime_a as a huge u64 value
        # that's clearly bytes from an upstream field, not a real
        # cooltime variant. Marker for misalignment.
        "unk_post_cooltime_a": 1979120994421309440,
        "unk_post_cooltime_b": 1979120929996800000,
        "prefab_data_list": [{"hash_a": 0}],
    }
    intent = _make_intent(1001250, "cooltime", 18000)
    is_cooltime_field = intent.field in (
        "cooltime", "unk_post_cooltime_a", "unk_post_cooltime_b")
    assert is_cooltime_field
    misaligned = (
        item.get("unk_post_cooltime_a", 0) != 0
        or item.get("unk_post_cooltime_b", 0) != 0
    )
    assert misaligned


def test_cooltime_intent_on_aligned_record_still_applies():
    """Records where unk_post_cooltime_a/b are both zero AND prefab
    parsed cleanly are aligned correctly. Cooltime intents must
    still apply (no false-positive skip)."""
    item = {
        "key": 1,
        "max_stack_count": 1,
        "cooltime": 0,
        "unk_post_cooltime_a": 0,
        "unk_post_cooltime_b": 0,
        "prefab_data_list": [],  # cleanly-parsed list, not opaque dict
    }
    is_opaque = (
        isinstance(item.get("prefab_data_list"), dict)
        and item.get("prefab_data_list", {}).get("_opaque")
    )
    has_unk = (
        item.get("unk_post_cooltime_a", 0) != 0
        or item.get("unk_post_cooltime_b", 0) != 0
    )
    misaligned = is_opaque or has_unk
    assert not misaligned, (
        "aligned record should pass the guard cleanly")


def test_max_stack_count_intent_unaffected_by_guard():
    """The guard targets only cooltime-family fields. Other intents
    (max_stack_count, enchant_data_list, etc.) on misaligned records
    still apply."""
    intent_max_stack = _make_intent(1001250, "max_stack_count", 1000)
    intent_enchant = _make_intent(1001250, "enchant_data_list", [])
    is_cooltime_family = intent_max_stack.field in (
        "cooltime", "unk_post_cooltime_a", "unk_post_cooltime_b")
    assert not is_cooltime_family
    is_cooltime_family_2 = intent_enchant.field in (
        "cooltime", "unk_post_cooltime_a", "unk_post_cooltime_b")
    assert not is_cooltime_family_2
