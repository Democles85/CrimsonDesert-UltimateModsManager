# Iteminfo Native Parser Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Tasks 2-15 are independent and parallelizable.

**Goal:** Replace `crimson_rs.parse_iteminfo_from_bytes` and `crimson_rs.serialize_iteminfo` with a CDUMM-native Python parser that round-trips the live (post-2026-04-29 game patch) iteminfo.pabgb byte-identical and unblocks Format 3 list-of-dict mods.

**Architecture:** Schema-as-data driving a generic walker (`_ITEM_FIELDS` list of tuples). Per-nested-struct reader/writer pairs. Clean-room — no consultation of crimson_rs source or outputs during implementation; .pyd is used ONLY by tests as a regression oracle.

**Tech Stack:** Python 3.10+, struct module, pytest. No new dependencies.

**Design doc:** See `docs/plans/2026-05-06-iteminfo-native-parser-design.md` for full context.

---

## Clean-room rule (applies to every task)

Every subagent must follow these rules. The orchestrator must include them in every task prompt:

1. DO NOT import `crimson_rs` in production code (`src/cdumm/engine/iteminfo_native_parser.py`).
2. DO NOT read `.pyd` source code, Rust source, or any third-party project's iteminfo parser.
3. DO NOT use crimson_rs as a code reference. If you find yourself thinking "what does crimson_rs do here?", STOP — that is the line.
4. crimson_rs IS allowed in test code, ONLY as a regression oracle to verify your output. Use the `_RefOracle` helper at `tests/_iteminfo_ref_oracle.py` (Task 1 creates it).

---

## Task 1: Reference oracle helper for tests

**Files:**
- Create: `tests/_iteminfo_ref_oracle.py`

**Step 1: Write the helper**

```python
"""Reference oracle for iteminfo native parser tests.

The crimson_rs.pyd parser is used here ONLY to verify our native
parser's output. Production code never imports crimson_rs through
this file or directly.
"""
from __future__ import annotations

from typing import Any


def parse_with_oracle(data: bytes) -> list[dict]:
    """Run the .pyd parser. Skip if not loadable."""
    from cdumm.engine.crimson_rs_loader import get_crimson_rs
    crs = get_crimson_rs()
    if crs is None:
        import pytest
        pytest.skip("crimson_rs.pyd not loadable")
    return crs.parse_iteminfo_from_bytes(data)


def deep_dict_diff(a: Any, b: Any, path: str = "") -> list[str]:
    """Return human-readable list of every leaf-level mismatch
    between two dicts. Empty list = identical."""
    out: list[str] = []
    if type(a) is not type(b):
        return [f"{path}: type {type(a).__name__} vs {type(b).__name__}"]
    if isinstance(a, dict):
        keys = set(a) | set(b)
        for k in sorted(keys):
            sub = f"{path}.{k}" if path else k
            if k not in a:
                out.append(f"{sub}: missing in ours")
            elif k not in b:
                out.append(f"{sub}: missing in oracle")
            else:
                out.extend(deep_dict_diff(a[k], b[k], sub))
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path}: list len {len(a)} vs {len(b)}"]
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(deep_dict_diff(x, y, f"{path}[{i}]"))
        return out
    if a != b:
        out.append(f"{path}: {a!r} vs {b!r}")
    return out
```

**Step 2: Run smoke test**

```
py -3 -c "from tests._iteminfo_ref_oracle import deep_dict_diff; print(deep_dict_diff({'a':1},{'a':1}))"
```

Expected: `[]`

**Step 3: Commit**

```bash
git add tests/_iteminfo_ref_oracle.py
git commit -m "test(iteminfo): add reference oracle helper for native parser"
```

---

## Tasks 2-15: Per-nested-struct readers/writers

Each task follows the same structure. Replace `<NAME>` and `<FIELDS>`.

### Common steps for every nested-struct task

**Files:**
- Modify: `src/cdumm/engine/iteminfo_native_parser.py` (add `_read_<NAME>` and `_write_<NAME>` helpers in the "Nested struct readers / writers" section)
- Create: `tests/test_iteminfo_native_<name>.py` (one test that parses one example and compares to oracle for that struct)

**Per-task pattern:**

1. **RED**: Add a test that parses one struct of type `<NAME>` from a sub-slice of the live iteminfo and asserts the parsed dict equals what the oracle produces for the same bytes (use `deep_dict_diff` from Task 1).

2. **Verify RED**: Run the test, confirm it fails with `NotImplementedError` or `AttributeError` (function not yet defined).

3. **GREEN**: Add `_read_<NAME>` and `_write_<NAME>` to `iteminfo_native_parser.py`. Read fields in order from the `.pyi` stub.

4. **Verify GREEN**: Run the test, confirm it passes.

5. **Commit**: `git commit -m "feat(iteminfo): native parser for <NAME>"`

### List of nested-struct tasks

Task 2: `OccupiedEquipSlotData` — already implemented in scaffold; just add the test.

Task 3: `ItemIconData` — POST-1.0.4.1 LAYOUT MAY DIFFER. Subagent must round-trip this against the live binary; if fields needed beyond `(icon_path:u32, check_exist_sealed_data:u8, gimmick_state_list:CArray<u32>)`, identify them by checking where the struct's walked size matches what the parent record expects.

Task 4: `PassiveSkillLevel`, `ReserveSlotTargetData` (each is u32+u32, batched).

Task 5: `SocketMaterialItem`, `EnchantStatChange`, `EnchantLevelChange`, `EnchantStatData` (already implemented in scaffold; add tests for each).

Task 6: `PriceFloor`, `ItemPriceInfo`, `EquipmentBuff`, `EnchantData`. (Scaffold has these; add tests.)

Task 7: `GimmickVisualPrefabData` (scaffold has it; add test).

Task 8: `GameEventExecuteData`, `InventoryChangeData` (scaffold has them; add tests).

Task 9: `PageData`, `InspectData`, `InspectAction` (scaffold has them; add tests).

Task 10: `ItemInfoSharpnessData`, `ItemBundleData` (scaffold has them; add tests).

Task 11: `UnitData`, `MoneyUnitEntry`, `MoneyTypeDefine` (scaffold has them; add tests).

Task 12: `PrefabData`, `RepairData`, `SubItem`, `DropDefaultData` (scaffold has them; add tests).

Task 13: `SealableItemInfo` (variant by tag; scaffold has it; add tests for each tag value 0-4).

Task 14: `DockingChildData` (scaffold has it; add test using a real item that has docking data).

Task 15: `PatternDescriptionData` — POST-1.0.4.1 NEW STRUCT. Subagent must RE the structure from a live record that has a non-empty `pattern_description_data_list`. Find one item where this list is populated by sampling the live iteminfo; then parse fields from raw bytes and verify against oracle.

---

## Task 16: Main item walker + post-1.0.4.1 layout discovery

**Files:**
- Modify: `src/cdumm/engine/iteminfo_native_parser.py`
- Modify: `tests/test_iteminfo_native_parser.py`

**Step 1: Update `_ITEM_FIELDS`**

Add the post-1.0.4.1 fields the .pyi doesn't list yet. Run the OLD vendored .pyd against the live fixture to enumerate the actual field names (oracle output is a dict; all keys present in oracle but missing from `_ITEM_FIELDS` are the new fields). For each missing field, the subagent must figure out the field type by examining live bytes — the oracle only tells us the FIELD NAMES and INTERPRETED VALUES, not the byte-level layout, so this is still RE work.

**Step 2: Walk-and-fix loop**

```
While not round-trip-identical:
    1. Run parse_first_record_size on live fixture
    2. Compare to .pabgh expected size (634 bytes for record 0)
    3. If mismatch, find divergence point by walking field-by-field
    4. Add or correct field schema entry in _ITEM_FIELDS
    5. Repeat
```

Run after each schema edit:
```
py -3 -m pytest tests/test_iteminfo_native_parser.py -v
```

**Step 3: Walk all 6339 records**

The `test_native_parser_walks_every_record_to_correct_boundary` test must pass. If any single record drifts, a variant-length field has an edge case. Find that record's bytes, RE the edge.

**Step 4: Round-trip whole-file**

`test_native_parser_round_trips_byte_identical` must pass.

**Step 5: Commit**

```bash
git add src/cdumm/engine/iteminfo_native_parser.py tests/test_iteminfo_native_parser.py
git commit -m "feat(iteminfo): native parser round-trips post-2026-04-29 game patch"
```

---

## Task 17: Swap iteminfo_writer.py to use native parser

**Files:**
- Modify: `src/cdumm/engine/iteminfo_writer.py`

**Step 1: Grep for other crimson_rs iteminfo callers**

```
grep -rn "parse_iteminfo_from_bytes\|serialize_iteminfo" src/cdumm
```

Expected: only `iteminfo_writer.py` and `_vendor/crimson_rs/__init__.pyi`. If others, list them in the task report.

**Step 2: Replace the two calls**

```python
# Before: items = crimson_rs.parse_iteminfo_from_bytes(vanilla_body)
from cdumm.engine.iteminfo_native_parser import parse_iteminfo_from_bytes, serialize_iteminfo
items = parse_iteminfo_from_bytes(vanilla_body)

# Before: new_bytes = crimson_rs.serialize_iteminfo(items)
new_bytes = serialize_iteminfo(items)
```

Remove the `crimson_rs = get_crimson_rs()` and `if crimson_rs is None` guards from `iteminfo_writer.py` since the native parser doesn't need them.

**Step 3: Run existing iteminfo tests**

```
py -3 -m pytest tests/test_iteminfo_list_writer.py tests/test_iteminfo_apply_end_to_end.py tests/test_iteminfo_mixed_intents.py tests/test_iteminfo_multi_mod_compose.py -v
```

Expected: all pass. They previously passed against the .pyd; they must still pass against the native parser. (Tests skip on machines without the live fixture; that's fine.)

**Step 4: Commit**

```bash
git add src/cdumm/engine/iteminfo_writer.py
git commit -m "refactor(iteminfo): route through native parser instead of crimson_rs"
```

---

## Task 18: End-to-end Format 3 mod apply test

**Files:**
- Create: `tests/test_iteminfo_native_apply_e2e.py`

**Step 1: Write the failing test**

The test takes a Format 3 intent that sets `enchant_data_list` on a real item (one that has at least one enchant in vanilla), runs the full apply path, and verifies the output binary parses back with the user's intended changes — using the native parser's own parse on the patched bytes.

```python
def test_format3_enchant_data_list_apply_round_trip():
    from cdumm.engine.iteminfo_native_parser import (
        parse_iteminfo_from_bytes, serialize_iteminfo,
    )
    from cdumm.engine.iteminfo_writer import build_iteminfo_intent_change
    from cdumm.engine.format3_handler import Format3Intent
    from pathlib import Path

    body = Path(
        "C:/Users/faisa/AppData/Local/Temp/iteminfo_postpatch.pabgb"
    ).read_bytes()
    items = parse_iteminfo_from_bytes(body)
    target = next(it for it in items if it.get("enchant_data_list"))

    new_enchants = [{
        "level": 0,
        "enchant_stat_data": {
            "max_stat_list": [],
            "regen_stat_list": [],
            "stat_list_static": [],
            "stat_list_static_level": [],
        },
        "buy_price_list": [],
        "equip_buffs": [],
    }]
    intent = Format3Intent(
        entry=target["string_key"], key=target["key"],
        field="enchant_data_list", op="set", new=new_enchants)
    change = build_iteminfo_intent_change(body, [intent])
    assert change is not None

    new_bytes = bytes.fromhex(change["patched"])
    new_items = parse_iteminfo_from_bytes(new_bytes)
    new_target = next(it for it in new_items if it["key"] == target["key"])
    assert new_target["enchant_data_list"] == new_enchants
```

**Step 2: Run, verify pass**

```
py -3 -m pytest tests/test_iteminfo_native_apply_e2e.py -v
```

Expected: PASS.

**Step 3: Commit**

```bash
git add tests/test_iteminfo_native_apply_e2e.py
git commit -m "test(iteminfo): end-to-end Format 3 enchant_data_list apply round-trip"
```

---

## Task 19: Update changelog and ship v3.2.10

**Files:**
- Modify: `src/cdumm/gui/changelog.py`

**Step 1: Add v3.2.10 entry**

Bullet: "Iteminfo Format 3 list-of-dict mods (enchant_data_list, equip_passive_skill_list, sealable_*_info_list, etc) now apply on the latest Crimson Desert patch. The previous behavior — silent 0 byte changes with a misleading 'vendored writer failed to load' warning — was a binary-layout drift after Pearl Abyss shipped a game update; CDUMM now parses iteminfo natively in Python and stays in sync regardless of which patch the game is on."

**Step 2: Bump version**

In `pyproject.toml` and any `__init__.py` with version: `3.2.9` → `3.2.10`.

**Step 3: Build and tag**

(Faisal's normal release flow — pyinstaller, tag, push, GitHub release.)

---

## Execution Handoff

Plan complete. Two execution options:

1. Subagent-Driven (this session) — I dispatch fresh subagent per task with two-stage review (spec compliance, then code quality).

2. Parallel Session (separate) — open new session with executing-plans, batch execution with checkpoints.
