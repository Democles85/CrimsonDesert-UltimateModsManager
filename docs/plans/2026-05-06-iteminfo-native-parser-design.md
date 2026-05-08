# Iteminfo Native Parser Design

Date: 2026-05-06
Author: Faisal + Claude (brainstormed jointly, finalized by Claude on Faisal's authorization)

## Problem

CDUMM's Format 3 list-of-dict mods (enchant_data_list, equip_passive_skill_list,
sealable_*_info_list, etc) for iteminfo route through the vendored
`crimson_rs.pyd` Rust extension. Pearl Abyss shipped a Crimson Desert game
update on 2026-04-29 that added 10 bytes per iteminfo record. The vendored
parser misaligns and produces 0 byte changes with the misleading "vendored
writer failed to load" warning.

The vendored .pyd contains contributions from a hostile party. Going forward we
do not pull additional contributions from that party. The fix has to be a
native CDUMM Python parser, written clean-room.

## Goals

1. Round-trip Faisal's live iteminfo.pabgb byte-identical (parse + serialize
   produces the original bytes back).
2. Pluggable schema so future game patches are a small edit, not a rewrite.
3. End-to-end test: a Format 3 mod targeting `enchant_data_list` applies
   correctly through the new parser.

## Non-goals

- Replacing crimson_rs for non-iteminfo functions (PAMT, PAPGT, paloc,
  PackGroupBuilder). Those keep using the .pyd for now.
- Performance parity with Rust. Python is acceptably fast at apply time.
- Supporting older Crimson Desert versions. Targets the current live version.

## Clean-room methodology (Phoenix BIOS pattern)

- The implementer works ONLY from raw byte observations and the legitimately-
  ours `__init__.pyi` type stub (Potter420 MIT, predates the hostile party's
  contributions in field count).
- The implementer does NOT consult the existing .pyd's outputs while writing
  code. The .pyd is consulted ONLY by test code as a regression oracle, after
  the implementer has produced a candidate parse.
- Each subagent task prompt explicitly forbids importing crimson_rs, reading
  crimson_rs source, or copying patterns from any third-party project's code.

## Architecture

```
src/cdumm/engine/
  iteminfo_native_parser.py     ← new module (this design)
    _Reader, _Writer            ← cursor-tracking byte primitives
    _read_<Struct>, _write_<Struct>  ← per-nested-struct walkers
    _ITEM_FIELDS                ← schema-as-data (list of tuples)
    _read_item, _write_item     ← generic walker driven by _ITEM_FIELDS
    parse_iteminfo_from_bytes()  ← public API (replaces crimson_rs)
    serialize_iteminfo()         ← public API (replaces crimson_rs)

src/cdumm/engine/iteminfo_writer.py
  build_iteminfo_intent_change() ← swap two crimson_rs calls -> new module

tests/
  test_iteminfo_native_parser.py  ← round-trip on live bytes
  test_iteminfo_native_primitives.py ← per-primitive unit tests
  test_iteminfo_native_nested_structs.py ← per-nested-struct verification
  test_iteminfo_native_apply_e2e.py ← Format 3 mod apply round-trip
```

## Schema representation

`_ITEM_FIELDS` is a list of tuples:

```python
_ITEM_FIELDS = [
    ("key", "u32"),
    ("string_key", "cstring"),
    ("is_blocked", "u8"),
    # ...
    ("item_icon_list", "carray", _read_ItemIconData, _write_ItemIconData),
    # ...
]
```

The generic walker dispatches on the second tuple element. Adding a new field
in a future game patch is a one-line edit, not a code change.

## Subagent task plan (subagent-driven-development)

Tasks 1-15 are independent, can run in parallel where useful. Each gets fresh
context, must implement reader + writer + test, must not consult crimson_rs.

1. Primitive readers/writers (already done in current scaffold)
2. OccupiedEquipSlotData
3. ItemIconData (LIKELY HAS NEW FIELDS — RE work)
4. PassiveSkillLevel + ReserveSlotTargetData (small, batched)
5. SocketMaterialItem + EnchantStatChange + EnchantLevelChange + EnchantStatData
6. PriceFloor + ItemPriceInfo + EquipmentBuff + EnchantData
7. GimmickVisualPrefabData
8. GameEventExecuteData + InventoryChangeData
9. PageData + InspectData + InspectAction
10. ItemInfoSharpnessData + ItemBundleData
11. UnitData + MoneyUnitEntry + MoneyTypeDefine
12. PrefabData + RepairData + SubItem + DropDefaultData
13. SealableItemInfo (variant by tag)
14. DockingChildData
15. PatternDescriptionData (post-1.0.4.1 — RE from scratch)

Task 16: Main item walker. Wire all readers/writers via _ITEM_FIELDS. Drive
to round-trip-identity on live iteminfo. THIS IS WHERE NEW POST-1.0.4.1
LAYOUT DISCOVERY HAPPENS — when round-trip diverges, identify new field(s),
add to schema, retry.

Task 17: Swap iteminfo_writer.py to use new parser. Run existing iteminfo
tests, verify all green.

Task 18: End-to-end test. Take a real Format 3 mod (UnLuckyLust's
enchant_data_list mod), run apply through the new parser, verify the output
binary parses back with the user's intended changes.

## Test pyramid

- Layer 1: Primitive unit tests (read u8 → 0; write u8(0) → \x00; etc).
  Confirms _Reader/_Writer correctness.
- Layer 2: Per-nested-struct tests. Each parses one example record from the
  live binary and the parsed dict matches what crimson_rs.pyd produces for
  the same bytes (oracle check). Per-struct = ~15 tests.
- Layer 3: Whole-file round-trip integration. parse + serialize on 5MB live
  iteminfo produces byte-identical output. Three of these:
  - first record only (fast feedback)
  - every record walks to its .pabgh boundary
  - full file round-trip identity

## Wiring

In `src/cdumm/engine/iteminfo_writer.py`:

```python
# Before:
items = crimson_rs.parse_iteminfo_from_bytes(vanilla_body)
# ...
new_bytes = crimson_rs.serialize_iteminfo(items)

# After:
from cdumm.engine.iteminfo_native_parser import (
    parse_iteminfo_from_bytes, serialize_iteminfo,
)
items = parse_iteminfo_from_bytes(vanilla_body)
# ...
new_bytes = serialize_iteminfo(items)
```

The .pyd file stays in `_vendor/crimson_rs/` for now because other modules
may use its non-iteminfo functions. Grep for other callers of
`crimson_rs.parse_iteminfo_from_bytes` or `crimson_rs.serialize_iteminfo`
to confirm only iteminfo_writer.py is affected before swapping.

## Roll-out

Direct swap, no feature flag. Round-trip identity test is the safety gate.
If it passes on the build server and locally, it ships in v3.2.10. Hotfix
path is available if a regression slips.

## Performance budget

- Apply already takes minutes for large mod sets.
- 5MB iteminfo parse + serialize in Rust: ~0.3s.
- Same in Python: target under 10s. Use `struct.unpack_from` and avoid
  allocating intermediate bytes.
- Acceptance: parse + serialize completes in under 10s on Faisal's machine.

## Out-of-scope (deferred)

- Schema versioning (current design is single-version; multi-version dicts
  added when we encounter a second concurrently-supported version)
- crimson_rs full removal (PAMT, PAPGT, paloc, PackGroupBuilder migration)
- vehicleinfo, characterinfo, etc native parsers (other tables already work
  via CDUMM's schema walker; replace one .pabgb-table at a time)
