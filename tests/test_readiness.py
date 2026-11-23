"""Readiness check before the show (stage 1 C2a step 7)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from engine.readiness import (
    CHECKLIST,
    INFO,
    MEDIA,
    OK,
    POWER,
    PROBLEM,
    SCREEN,
    SHOW,
    SKIPPED,
    SPEAKERS,
    VOLUME,
    Facts,
    checks,
    page_rows,
    problems,
)
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication

GOOD = Facts(screen_name="LG (screen 2)", screen_external=True, screen_count=2, speakers="Realtek",
             heard=True, media_total=3, power=(False, 100), checklist=(7, 7), show_name="Kapturek")


def _states(facts: Facts) -> dict[str, str]:
    return {c.key: c.state for c in checks(facts)}


# ── Pure rows ────────────────────────────────────────────────────────


def test_everything_right_and_in_the_walking_order():
    rows = checks(GOOD)
    assert [c.key for c in rows] == [SCREEN, VOLUME, SPEAKERS, MEDIA, POWER, CHECKLIST, SHOW]
    assert not problems(rows) and rows[-1].state == INFO


def test_each_problem_is_said():
    from dataclasses import replace

    bad = replace(GOOD, screen_external=False, master_level=0.4, master_muted=True,
                  speakers_missing="JBL", missing=("#6 'brak.mp3'",), power=(True, 54), checklist=(2, 7))
    states = _states(bad)
    assert all(states[k] == PROBLEM for k in (SCREEN, VOLUME, SPEAKERS, MEDIA, POWER, CHECKLIST))
    assert [c.key for c in page_rows(checks(bad), full=False)] == [SCREEN, VOLUME, SPEAKERS, MEDIA, POWER,
                                                                    CHECKLIST]


def test_tone_not_tried_is_not_checked_and_no_battery_no_row():
    from dataclasses import replace

    states = _states(replace(GOOD, heard=None, power=None, checklist=None))
    assert states[SPEAKERS] == SKIPPED and POWER not in states and states[CHECKLIST] == INFO
    assert _states(replace(GOOD, heard=False))[SPEAKERS] == PROBLEM
    assert _states(GOOD)[SPEAKERS] == OK


def test_later_entries_show_only_what_is_wrong():
    assert page_rows(checks(GOOD), full=False) == []
    assert len(page_rows(checks(GOOD), full=True)) == 7


# ── Window ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


@pytest.fixture()
def window(qt_app, tmp_path):
    from models.cue import Cue, MediaType
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    QSettings("BlindCue", "BlindCue").setValue("live/readiness_check", True)
    output = OutputWindow()
    win = MainWindow(output)
    files = []
    for i in range(3):
        f = tmp_path / f"c{i}.wav"
        f.write_bytes(b"RIFF")
        files.append(f)
    win._cues = [Cue.from_dict({"cue_id": 9001 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
                                "file_path": str(files[i])}) for i in range(3)]
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    try:
        yield win
    finally:
        QSettings("BlindCue", "BlindCue").setValue("live/readiness_check", False)
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_entering_shows_the_page_first_and_a_start_goes_in(window):
    window._enter_show_from_key()                               # Ctrl+L
    page = window._readiness_page
    assert window._readiness_visible() and not window.is_live_mode()
    assert not window._mode_tabs.is_live()
    keys = [r.key for r in page.rows]
    assert keys[:2] == [SCREEN, VOLUME] and SHOW in keys           # full check: every row
    assert page.start_buttons and page.start_buttons[0].text().startswith("▶ ")
    # No projector here: a problem, so Enter / Space checks again instead of starting.
    assert page.default_button() is page.btn_recheck
    window._on_go_shortcut()                                    # Space on the page
    assert not window.is_live_mode() and not window._played_ids  # never a GO
    page.start_buttons[0].click()
    assert window.is_live_mode() and window._central_stack.currentIndex() == 1
    assert window._live_show_panel.btn_ready_warn.isVisibleTo(window._live_show_panel)


def test_later_entry_shows_only_problems_and_none_means_no_page(window, monkeypatch):
    window._readiness_full_due = False
    window._enter_show_from_key()
    assert window._readiness_visible()
    assert all(r.state == PROBLEM for r in window._readiness_page.rows)
    window._readiness_page.btn_stay.click()
    assert not window._readiness_visible() and not window.is_live_mode()
    monkeypatch.setattr(window, "_readiness_rows", lambda: checks(GOOD))
    window._enter_show_from_key()
    assert window.is_live_mode()                                # nothing to say: straight in


def test_volume_fix_and_checklist_on_the_page(window):
    window._set_master(level=0.4, muted=True)
    window._add_default_checklist()
    assert window._cues[0].action_spec["kind"] == "checklist" and len(window._cues[0].action_spec["items"]) == 7
    window._enter_show_from_key()
    page = window._readiness_page
    assert "volume" in page.row_buttons
    page.row_buttons["volume"].click()
    assert window._master_level == 1.0 and not window._master_muted
    row = next(r for r in page.rows if r.key == CHECKLIST)
    assert row.state == PROBLEM and len(row.items) == 7
    page.checklist_toggled.emit(row.cue_id, 0, True)
    assert 0 in window._checklist_ticks[row.cue_id]


def test_review_from_the_show_goes_back_to_it(window):
    window._enter_show_from_key()
    window._readiness_page.start_buttons[0].click()
    window._show_readiness(review=True)
    page = window._readiness_page
    assert window._readiness_visible() and not page.start_buttons
    page.btn_stay.click()
    assert window.is_live_mode() and window._central_stack.currentIndex() == 1


def test_new_show_starts_with_the_default_checklist(window, monkeypatch):
    monkeypatch.setattr(window, "_confirm_save_if_modified", lambda *a: True)
    window._on_new_show()
    assert len(window._cues) == 1 and window._cues[0].action_spec["kind"] == "checklist"
    assert window._readiness_full_due


def test_turned_off_goes_straight_in(window):
    QSettings("BlindCue", "BlindCue").setValue("live/readiness_check", False)
    window._enter_show_from_key()
    assert window.is_live_mode()
