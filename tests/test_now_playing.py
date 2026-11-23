"""Now playing, the right column of the show (stage 1 C2a step 8)."""

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
from models.cue import Cue, CueStatus, FollowMode, MediaType
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication
from ui.now_playing import NOTE, STILL, TIMED


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
def window(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    kinds = [MediaType.AUDIO, MediaType.VIDEO, MediaType.IMAGE]
    win._cues = [Cue.from_dict({"cue_id": 9101 + i, "name": f"c{i}", "media_type": kinds[i].value,
                                "file_path": f"/nonexistent/c{i}", "layer": i + 1}) for i in range(3)]
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    try:
        yield win
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def _play(win, idx: int, duration: float, pos: float) -> None:
    cue = win._cues[idx]
    cue.status = CueStatus.LIVE
    slot = win._runtime_slot(cue)
    win._live_clocks.start(slot, cue.cue_id, cue.media_type != MediaType.IMAGE, duration)
    if duration:
        win._live_clocks.progress(slot, pos, 0.0, duration)


def test_nothing_playing(window):
    window._refresh_now_playing()
    panel = window._live_show_panel.now_playing
    assert not panel.cards() and panel.lbl_empty.isVisibleTo(panel)


def test_cards_for_what_plays_with_time_left_and_fixed_places(window):
    _play(window, 1, 100.0, 40.0)
    _play(window, 2, 0.0, 0.0)
    window._on_live_clock_tick()
    panel = window._live_show_panel.now_playing
    cards = panel.cards()
    assert list(cards) == [9102, 9103]
    assert cards[9102].kind == TIMED and cards[9103].kind == STILL
    assert cards[9102].lbl_remaining.text() == "-01:00" and cards[9102].lbl_elapsed.text() == "00:40"
    _play(window, 0, 60.0, 1.0)                      # a new cue: after the others
    window._on_live_clock_tick()
    assert list(panel.cards()) == [9102, 9103, 9101]
    first = panel.cards()[9102]
    window._cues[1].status = CueStatus.LOADED        # ended: its card goes, the others stay
    window._on_live_clock_tick()
    assert 9102 not in panel.cards() and first is not panel.cards().get(9101)


def test_ends_soon_is_a_sign_not_only_a_colour(window):
    _play(window, 0, 60.0, 57.0)
    window._on_live_clock_tick()
    card = window._live_show_panel.now_playing.cards()[9101]
    assert card.lbl_remaining.text().startswith("⚠ ")
    window._cues[0].follow_mode = FollowMode.AUTO_FOLLOW.value   # it hands over by itself
    window._on_live_clock_tick()
    assert not card.lbl_remaining.text().startswith("⚠")


def test_card_buttons_ask_for_their_layer(window):
    _play(window, 0, 60.0, 5.0)
    window._on_live_clock_tick()
    asked: list = []
    window.layer_play_pause_requested.connect(lambda layer: asked.append(("pause", layer)))
    window.layer_clear_requested.connect(lambda layer: asked.append(("clear", layer)))
    card = window._live_show_panel.now_playing.cards()[9101]
    card.btn_pause.click()
    window.set_live_layer_paused(1, True)
    assert window._live_show_panel.now_playing.cards()[9101].lbl_state.text() == "PAUSA"
    card.btn_fade.click()
    assert asked == [("pause", 1), ("clear", 1)]
    assert window._cues[0].status != CueStatus.LIVE


def test_plain_note_is_a_card_in_the_show(window):
    window._cues.append(Cue.from_dict({"cue_id": 9199, "name": "note", "media_type": MediaType.ACTION.value,
                                       "file_path": "", "action_spec": {"kind": "note", "text": "Czekaj"}}))
    window._refresh_cue_list(keep_selection=False)
    window.set_live_mode(True)
    window.show_operator_note(window._cues[3])
    banner = window._note_banner
    assert banner.is_shown() and banner.isHidden()   # up, but on its card
    card = window._live_show_panel.now_playing.cards()[9199]
    assert card.kind == NOTE and "Czekaj" in card.lbl_title.text()
    card.btn_fade.click()                             # OK
    assert not banner.is_shown() and 9199 not in window._live_show_panel.now_playing.cards()


def test_paused_is_its_own_word_in_the_list_and_for_readers(window):
    from ui.cue_table import ROLE_PAUSED

    _play(window, 0, 60.0, 5.0)
    window.set_live_mode(True)
    window.set_live_layer_paused(1, True)
    item = window._live_show_panel.live_table.item(0, 5)
    assert item.data(ROLE_PAUSED) is True
    assert item.data(Qt.ItemDataRole.AccessibleTextRole) == "in pausa"
    window.set_live_layer_paused(1, False)
    assert item.data(ROLE_PAUSED) is False


def test_announcements_are_throttled_and_urgent_ones_win(window):
    window._announced = []
    window._announce_last = 0.0
    window.announce("GO #1")                       # at once
    window.announce("GO #2")                       # waits (0.5 s)
    window.announce("Blocked", assertive=True)     # replaces the waiting one
    window.announce("GO #3")                       # a polite one never replaces an urgent one
    _pump(0.7)
    assert window._announced == [("GO #1", False), ("Blocked", True)]


def test_jumps_level_and_ramps_on_the_card(window):
    _play(window, 0, 120.0, 30.0)
    window._on_live_clock_tick()
    seeks: list = []
    trims: list = []
    window.layer_seek_requested.connect(lambda layer, pos: seeks.append((layer, pos)))
    window.layer_trim_requested.connect(lambda layer, trim: trims.append((layer, trim)))
    card = window._live_show_panel.now_playing.cards()[9101]
    assert card.btn_back.isVisibleTo(card) and card.btn_fwd.isVisibleTo(card)
    card.btn_back.hold_completed.emit()
    card.btn_fwd.hold_completed.emit()
    assert seeks == [(1, 20.0), (1, 40.0)]
    card.slider.setValue(40)
    assert trims == [(1, 0.4)] and card.lbl_trim.text() == "40 %"
    window.note_level_ramp(1, 0.2, 2.0, window._cues[0])
    window._on_live_clock_tick()
    assert card.lbl_state.text().startswith("↘ a 20 %") and card.slider.value() == 20


def test_hold_makes_the_auto_go_wait_once(window):
    window._cues[0].follow_mode = FollowMode.AUTO_FOLLOW.value
    _play(window, 0, 60.0, 5.0)
    window._cue_list.setCurrentRow(1)
    window._sync_live_view()
    panel = window._live_show_panel
    assert panel.btn_hold_auto.isVisibleTo(panel)
    panel.btn_hold_auto.click()
    assert 9101 in window._held_auto_go and "Auto-GO" in panel.lbl_standby_banner.text()
    window.trigger_auto_follow_from(window._cues[0])        # #1 ends: #2 does not start
    assert window._cues[1].status != CueStatus.LIVE and 9101 not in window._held_auto_go


def test_output_preview_runs_only_in_the_show(window):
    panel = window._live_show_panel.now_playing
    assert not window._preview_timer.isActive()
    window.set_live_mode(True)
    assert window._preview_timer.isActive() and panel.lbl_preview.pixmap() is not None
    panel.btn_preview.click()                       # fold it: no more frames
    assert not window._preview_timer.isActive() and not panel.lbl_preview.isVisibleTo(panel)
    panel.btn_preview.click()
    window.set_live_mode(False)
    assert not window._preview_timer.isActive()
