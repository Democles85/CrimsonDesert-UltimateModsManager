"""Regression test: ConfigPanel.show_mod must NOT emit
RuntimeWarning('Failed to disconnect ... from signal "finished()"').

Pre-fix evidence: every config_panel test fired this warning once when
show_mod (or show_variant_mod) called `_anim.finished.disconnect`
unconditionally even on a fresh panel. The try/except RuntimeError
caught the exception but PySide6 warnings.warn'd before raising, so
the warning leaked to test output.

The fix tracks a `_closed_handler_connected` flag, only disconnects
when True.
"""
from __future__ import annotations

import warnings

import pytest


@pytest.fixture
def app(qtbot):
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_show_mod_does_not_emit_disconnect_warning(qtbot, app):
    from cdumm.gui.components.config_panel import ConfigPanel

    panel = ConfigPanel()
    qtbot.addWidget(panel)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        panel.show_mod(
            mod_id=1, name="t", author="x", version="1",
            status="active", file_count=1,
            patches=[{"label": "p", "enabled": True}], conflicts=[],
        )
    disconnect_warnings = [
        w for w in captured
        if issubclass(w.category, RuntimeWarning)
        and "Failed to disconnect" in str(w.message)
    ]
    assert not disconnect_warnings, (
        f"Expected no Failed-to-disconnect warning, got "
        f"{len(disconnect_warnings)}: {disconnect_warnings[0].message!r}"
    )


def test_show_mod_after_close_does_not_emit_warning(qtbot, app):
    """After a close_panel + show_mod cycle, the disconnect should
    succeed cleanly (handler IS connected post-close), no warning."""
    from cdumm.gui.components.config_panel import ConfigPanel

    panel = ConfigPanel()
    qtbot.addWidget(panel)
    panel.show_mod(
        mod_id=1, name="t", author="x", version="1",
        status="active", file_count=1,
        patches=[{"label": "p", "enabled": True}], conflicts=[],
    )
    panel.close_panel()
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        panel.show_mod(
            mod_id=2, name="t2", author="x", version="1",
            status="active", file_count=1,
            patches=[{"label": "p", "enabled": True}], conflicts=[],
        )
    disconnect_warnings = [
        w for w in captured
        if issubclass(w.category, RuntimeWarning)
        and "Failed to disconnect" in str(w.message)
    ]
    assert not disconnect_warnings


def test_double_close_does_not_emit_warning(qtbot, app):
    """close_panel called twice should not double-connect or warn."""
    from cdumm.gui.components.config_panel import ConfigPanel

    panel = ConfigPanel()
    qtbot.addWidget(panel)
    panel.show_mod(
        mod_id=1, name="t", author="x", version="1",
        status="active", file_count=1,
        patches=[{"label": "p", "enabled": True}], conflicts=[],
    )
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        panel.close_panel()
        panel.close_panel()
    disconnect_warnings = [
        w for w in captured
        if issubclass(w.category, RuntimeWarning)
        and ("Failed to disconnect" in str(w.message)
             or "UniqueConnection" in str(w.message))
    ]
    assert not disconnect_warnings
