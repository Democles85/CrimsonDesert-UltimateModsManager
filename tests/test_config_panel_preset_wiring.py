"""Tests for preset selector wiring (Task 1.3)."""
from __future__ import annotations

import pytest


@pytest.fixture
def app(qtbot):
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _build_panel_with_presets(qtbot):
    from cdumm.gui.components.config_panel import ConfigPanel
    panel = ConfigPanel()
    qtbot.addWidget(panel)
    # 4 patches: 2 in [0%], 2 in [100%]. All start enabled=True.
    patches = [
        {"label": "[0%] alpha", "enabled": True},
        {"label": "[0%] beta", "enabled": True},
        {"label": "[100%] alpha", "enabled": True},
        {"label": "[100%] beta", "enabled": True},
    ]
    panel.show_mod(
        mod_id=1, name="t", author="x", version="1",
        status="active", file_count=1, patches=patches, conflicts=[],
    )
    return panel


def test_clicking_preset_radio_enables_only_that_group(qtbot, app):
    panel = _build_panel_with_presets(qtbot)
    # Find the [0%] radio and click it.
    zero_radio = next(
        b for b in panel._preset_radio_group.buttons()
        if b.text() == "0%"
    )
    zero_radio.click()
    # Indices 0,1 are [0%]; indices 2,3 are [100%].
    assert panel._toggles[0].isChecked() is True
    assert panel._toggles[1].isChecked() is True
    assert panel._toggles[2].isChecked() is False
    assert panel._toggles[3].isChecked() is False


def test_clicking_other_preset_flips_groups(qtbot, app):
    panel = _build_panel_with_presets(qtbot)
    zero_radio = next(b for b in panel._preset_radio_group.buttons() if b.text() == "0%")
    hundred_radio = next(b for b in panel._preset_radio_group.buttons() if b.text() == "100%")
    zero_radio.click()
    hundred_radio.click()
    assert panel._toggles[0].isChecked() is False
    assert panel._toggles[1].isChecked() is False
    assert panel._toggles[2].isChecked() is True
    assert panel._toggles[3].isChecked() is True


def test_clicking_custom_does_not_change_toggles(qtbot, app):
    panel = _build_panel_with_presets(qtbot)
    zero_radio = next(b for b in panel._preset_radio_group.buttons() if b.text() == "0%")
    custom_radio = next(b for b in panel._preset_radio_group.buttons() if b.text() == "Custom")
    # Set a known state via the [0%] preset
    zero_radio.click()
    # Now toggle indices 2 and 3 ON manually
    panel._toggles[2].setChecked(True)
    panel._toggles[3].setChecked(True)
    # Custom click should NOT touch any toggle
    custom_radio.click()
    assert panel._toggles[0].isChecked() is True
    assert panel._toggles[1].isChecked() is True
    assert panel._toggles[2].isChecked() is True
    assert panel._toggles[3].isChecked() is True
