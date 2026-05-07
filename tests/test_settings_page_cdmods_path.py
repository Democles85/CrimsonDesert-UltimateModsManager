"""Tests for the cdmods_path settings UI (Task 3.3).

The Settings page must expose a "Mod storage location" section so users
can override where CDUMM keeps its CDMods/ directory (sources, vanilla
snapshots, deltas, cdumm.db). Useful when the game is on a small drive
but the user wants mod backups on a bigger one.

This task only persists the chosen path and updates the displayed label;
the actual on-disk migration of CDMods/ contents is Task 3.4.
"""
from __future__ import annotations

import pytest

pytest_qt = pytest.importorskip("pytestqt")

from cdumm.i18n import load as load_translations

# tr() looks up strings in a module-level dict that starts empty. Load
# English once so UI labels come out as text, not raw keys.
load_translations("en")


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_settings_page_has_cdmods_path_field(qtbot, app, db, tmp_path):
    """The settings page renders a 'Mod storage location' section with
    a label that shows the currently resolved CDMods/ path."""
    from cdumm.gui.pages.settings_page import SettingsPage

    page = SettingsPage()
    qtbot.addWidget(page)
    page.set_managers(db=db, game_dir=tmp_path)

    assert hasattr(page, "_cdmods_path_label"), (
        "SettingsPage must expose _cdmods_path_label so the UI shows "
        "the user where their CDMods/ directory lives.")
    assert page._cdmods_path_label.text(), (
        "the label must be populated with the resolved path on load")


def test_setting_cdmods_path_persists_to_db(qtbot, app, db, tmp_path):
    """Calling _on_cdmods_path_changed writes the new override to the
    config table so subsequent get_cdmods_root() calls pick it up."""
    from cdumm.gui.pages.settings_page import SettingsPage
    from cdumm.storage.config import Config

    page = SettingsPage()
    qtbot.addWidget(page)
    page.set_managers(db=db, game_dir=tmp_path)

    new_path = tmp_path / "new_cdmods"
    new_path.mkdir()
    page._on_cdmods_path_changed(new_path)

    assert Config(db).get("cdmods_path") == str(new_path), (
        "the chosen path must be persisted under the cdmods_path "
        "config key so get_cdmods_root() picks it up next launch.")


def test_label_updates_after_path_change(qtbot, app, db, tmp_path):
    """The displayed path label must reflect the newly chosen folder
    immediately, not require a page refresh."""
    from cdumm.gui.pages.settings_page import SettingsPage

    page = SettingsPage()
    qtbot.addWidget(page)
    page.set_managers(db=db, game_dir=tmp_path)

    new_path = tmp_path / "new_cdmods"
    new_path.mkdir()
    page._on_cdmods_path_changed(new_path)

    assert str(new_path) in page._cdmods_path_label.text()


def test_settings_page_works_without_db(qtbot, app):
    """The page must construct cleanly even before set_managers() is
    called — main_window builds the page first, then wires it up."""
    from cdumm.gui.pages.settings_page import SettingsPage

    page = SettingsPage()
    qtbot.addWidget(page)
    # No crash, label exists but may be empty until set_managers fires.
    assert hasattr(page, "_cdmods_path_label")
