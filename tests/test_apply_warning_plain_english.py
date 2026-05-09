"""User-facing apply warnings must use plain English, not internals.

Bug 2026-05-09 (Faisal screenshot): the Apply-Completed-with-Warnings
banner shows two long jargon-heavy paragraphs that are hard to read:

    Skipped conflicting full-replace delta(s) for '0003/0.paz'
    from: Vaxis Water Physics Overhaul Mod. Each mod ships a
    complete replacement of this file, so CDUMM cannot combine
    them. Kept: 'Graphics Mod' (highest priority). To use a
    skipped mod instead, raise its priority above the kept one
    in your mod list.

    Some mods on 'ui/inputmap_common.xml' change the file size.
    CDUMM cannot byte-merge them with the others without
    truncating the new bytes mid-token. Kept: 'Better Radial
    Menus' (highest priority) at its full size; merged none of
    the others into it. Size-changing mods: 'No Intro' (243432
    bytes), 'Faster Interactions' (252704 bytes), 'Better Radial
    Menus' (252043 bytes). To use a different mod's version,
    raise its priority above 'Better Radial Menus' in your mod
    list.

Faisal's plain-language rule: end users aren't developers. Drop
internal vocabulary (delta, byte-merge, full-replace, token, byte
counts), lead with mod names not file paths, and use sentences
that read aloud naturally. The OVERLAY-merge branch was already
rewritten to a plain-English shape in v3.2.10; this regression
test pins the same shape on the BYTE-MERGE branch and the
FULL-REPLACE-skip branch which were left in the dev-style form.
"""
from __future__ import annotations

from pathlib import Path


def _src() -> str:
    return (Path(__file__).resolve().parents[1]
            / "src" / "cdumm" / "engine" / "apply_engine.py"
            ).read_text(encoding="utf-8")


def _full_replace_skip_block(src: str) -> str:
    """Return ONLY the user-facing body of the multi-full-replace
    skip-warning branch. Skip past the dev log line ('Applied
    full-replace delta for...') so the test inspects the user
    message, not the internal logger statement above it."""
    log_marker = "Applied full-replace delta for"
    log_pos = src.find(log_marker)
    assert log_pos != -1
    # Move past the logger.info(...) call entirely.
    after_log = src.find(")", log_pos)
    assert after_log != -1
    anchor = src.find("if len(full_replace_sorted) > 1:", after_log)
    assert anchor != -1
    end = src.find("# Step 2: Apply SPRS deltas", anchor)
    assert end != -1
    return src[anchor:end]


def _byte_merge_size_changed_block(src: str) -> str:
    """Return the body of the BYTE-merge size_changed branch —
    the FIRST 'if size_changed:' block. Anchor on the
    'merge_compiled_mod_files' fallback that closes it (which the
    OVERLAY branch much further down does NOT use)."""
    anchor = src.find("if size_changed:")
    assert anchor != -1
    end = src.find("merge_compiled_mod_files", anchor)
    assert end != -1
    return src[anchor:end]


# ------------------- byte-merge plain-English contract -------------------

def test_byte_merge_drops_developer_vocabulary():
    body = _byte_merge_size_changed_block(_src())
    # These tokens are the dev-style ones the user complained about.
    for jargon in ["byte-merge", "mid-token", "full size",
                   "Size-changing mods:", "Kept:"]:
        assert jargon not in body, (
            f"byte-merge warning still contains developer-style "
            f"phrase {jargon!r}; rewrite to plain English"
        )


def test_byte_merge_uses_plain_english_failure_phrase():
    body = _byte_merge_size_changed_block(_src())
    assert "could not be applied" in body, (
        "byte-merge warning must say the dropped mod 'could not be "
        "applied' so a non-developer reads it as a normal sentence"
    )


def test_byte_merge_tells_user_to_move_higher_in_mod_list():
    body = _byte_merge_size_changed_block(_src())
    assert ("move it higher" in body or "move it above" in body
            or "raise its priority" in body), (
        "byte-merge warning must tell the user the concrete UI "
        "action — move the desired mod higher in the mod list"
    )


def test_byte_merge_does_not_print_byte_counts():
    body = _byte_merge_size_changed_block(_src())
    assert "({sz} bytes)" not in body, (
        "byte-merge warning must NOT print raw byte counts; "
        "they're noise for non-developers (Faisal feedback "
        "2026-05-09)"
    )
    assert "{sz}" not in body
    assert "f\"({" not in body or "bytes)" not in body


# ------------------- full-replace skip plain-English contract -------------

def test_full_replace_skip_drops_developer_vocabulary():
    body = _full_replace_skip_block(_src())
    for jargon in ["full-replace delta", "Skipped conflicting",
                   "complete replacement of this file",
                   "Kept:", "(highest priority)"]:
        assert jargon not in body, (
            f"full-replace skip warning still contains "
            f"developer-style phrase {jargon!r}; rewrite to plain "
            f"English"
        )


def test_full_replace_skip_uses_plain_english_failure_phrase():
    body = _full_replace_skip_block(_src())
    assert "could not be applied" in body, (
        "full-replace skip warning must say the dropped mod "
        "'could not be applied' so a non-developer reads it as a "
        "normal sentence"
    )


def test_full_replace_skip_tells_user_to_move_higher_in_mod_list():
    body = _full_replace_skip_block(_src())
    assert ("move it higher" in body or "move it above" in body), (
        "full-replace skip warning must tell the user the concrete "
        "UI action — move the desired mod higher in the mod list"
    )
