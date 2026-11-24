"""Effects on demand (stage 1 phase D, plan items 1.7 and 1.10)."""

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
from engine.show_mode import PREPARATION
from models.cue import Cue, CueStatus, MediaType
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _cue(i: int, **extra) -> Cue:
    data = {"cue_id": 9401 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
            "file_path": f"/nonexistent/c{i}.wav", "volume": 0.8}
    data.update(extra)
    return Cue.from_dict(data)


@pytest.fixture()
def window(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._cues = [
        _cue(0),
        _cue(1, adlib=True, hotkey="b"),
        _cue(2),
        _cue(3, adlib=True, hotkey="C"),
        _cue(4, adlib=True, hotkey="C"),
        _cue(5, adlib=True, hotkey="T", hotkey_mode="toggle"),
        _cue(6, adlib=True, hotkey="N", hotkey_mode="note"),
    ]
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    fired: list[int] = []
    faded: list[int] = []
    win.cue_fired.connect(lambda c: fired.append(c.cue_id))
    win.card_fade_requested.connect(faded.append)
    win.fired, win.faded = fired, faded
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


def test_model_keeps_the_effect_fields():
    cue = _cue(0, adlib=True, hotkey="xy", hotkey_mode="note")
    back = Cue.from_dict(cue.to_dict())
    assert back.adlib and back.hotkey == "X" and back.hotkey_mode == "note"
    assert Cue.from_dict({**cue.to_dict(), "hotkey_mode": "bogus"}).hotkey_mode == "trigger"
    old = {k: v for k, v in cue.to_dict().items() if k not in ("adlib", "hotkey", "hotkey_mode")}
    plain = Cue.from_dict(old)
    assert not plain.adlib and plain.hotkey == "" and plain.hotkey_mode == "trigger"


def test_go_skips_the_effects(window):
    window.set_live_mode(True)
    window._on_go()
    assert window.fired == [9401]
    assert window._cue_list.currentRow() == 2          # c1 is an effect: standby goes past it


def test_effect_key_keeps_the_pointer_and_what_plays(window):
    window.set_live_mode(True)
    window._on_go()                                     # c0 on air, standby c2
    window._on_hotkey_press("B")
    window._on_hotkey_release("B")
    assert window.fired == [9401, 9402]
    assert window._cue_list.currentRow() == 2           # the GO pointer did not move
    c0, c1 = window._cues[0], window._cues[1]
    assert c0.status == CueStatus.LIVE and c1.status == CueStatus.LIVE  # nothing demoted


def test_several_cues_on_one_key_are_steps(window):
    window.set_live_mode(True)
    for _ in range(3):
        window._on_hotkey_press("C")
        window._on_hotkey_release("C")
    assert window.fired == [9404, 9405, 9404]


def test_toggle_and_note_stop_their_effect(window):
    window.set_live_mode(True)
    window._on_hotkey_press("T")
    window._on_hotkey_release("T")
    assert window.fired == [9406] and window.faded == []
    window._on_hotkey_press("T")                        # again: stops it
    assert window.fired == [9406] and len(window.faded) == 1
    window._on_hotkey_press("N")                        # plays while held
    assert window.fired == [9406, 9407]
    window._on_hotkey_release("N")
    assert len(window.faded) == 2
    window._on_hotkey_press("N")
    window._release_all_notes()                         # the window lost the keyboard
    assert len(window.faded) == 3 and window._held_notes == {}


def test_once_ignores_a_second_press_while_it_plays(window):
    """1.7 rest: "again = nothing while it plays" - a doorbell pressed twice by accident rings once."""
    bell = _cue(7, adlib=True, hotkey="D", hotkey_mode="once")
    assert Cue.from_dict(bell.to_dict()).hotkey_mode == "once"
    window._cues.append(bell)
    window._refresh_cue_list(keep_selection=False)
    window.set_live_mode(True)
    window._on_hotkey_press("D")
    window._on_hotkey_release("D")
    assert window.fired == [9408] and window._effect_running(bell)
    window._on_hotkey_press("D")                        # still playing (or waiting): nothing
    window._on_hotkey_release("D")
    window._repeat_last_effect()                        # Ctrl+R neither
    assert window.fired == [9408] and window.faded == [] and "'c7'" in window._status_label.text()
    bell.status = CueStatus.LOADED                       # it ended
    window._live_phase_tags.pop(bell.cue_id, None)
    window._on_hotkey_press("D")
    assert window.fired == [9408, 9408]                 # rings again


def test_repeat_the_last_effect(window):
    window._repeat_last_effect()                        # not in the show: nothing
    window.set_live_mode(True)
    window._repeat_last_effect()
    assert window.fired == []
    window._on_hotkey_press("B")
    window._repeat_last_effect()                        # Ctrl+R
    assert window.fired == [9402, 9402]
    window._on_hotkey_press("N")                        # a held note is not "the last effect"
    window._on_hotkey_release("N")
    window._repeat_last_effect()
    assert window.fired == [9402, 9402, 9407, 9402]


def _key(kind, text: str, mods=Qt.KeyboardModifier.NoModifier, repeat: bool = False) -> QKeyEvent:
    return QKeyEvent(kind, Qt.Key(ord(text.upper())), mods, text, repeat)


def test_key_filter_only_in_the_show_and_never_while_typing(window, monkeypatch):
    filt = window._hotkey_filter
    target = QObject()
    monkeypatch.setattr(window, "isActiveWindow", lambda: True)
    press = QEvent.Type.KeyPress
    assert not filt.eventFilter(target, _key(press, "b"))          # Preparation: no keys
    window.set_live_mode(True)
    assert filt.eventFilter(target, _key(press, "b")) and window.fired == [9402]
    assert filt.eventFilter(target, _key(press, "b", repeat=True)) and window.fired == [9402]
    assert not filt.eventFilter(target, _key(press, "b", Qt.KeyboardModifier.ControlModifier))
    assert not filt.eventFilter(target, _key(press, "z"))          # no effect on Z
    monkeypatch.setattr(window, "_is_text_input_focused", lambda: True)
    assert not filt.eventFilter(target, _key(press, "b"))          # typing a note: a letter
    assert window.fired == [9402]


def test_tiles_in_now_playing_only_in_the_rehearsal_and_show(window):
    panel = window._live_show_panel.now_playing
    window.set_live_mode(True)
    assert panel.effects_box.isVisibleTo(window._live_show_panel)
    assert set(panel.effect_tiles) == {9402, 9404, 9405, 9406, 9407}
    assert panel.effect_tiles[9402].focusPolicy() == Qt.FocusPolicy.NoFocus
    panel.effect_tiles[9402].click()
    assert window.fired == [9402] and window._cue_list.currentRow() == 0
    window._live_show_panel.mode_tabs.tab_prep_hold.hold_completed.emit()   # held: back to Preparation
    assert window._current_mode() == PREPARATION
    assert not panel.effects_box.isVisibleTo(window._live_show_panel)


def test_show_list_marks_the_effect_key(window):
    from ui.cue_table import ROLE_EFFECT_KEY

    window.set_live_mode(True)
    table = window._live_show_panel.live_table
    marks = [table.item(r, 0).data(ROLE_EFFECT_KEY) for r in range(3)]
    assert marks == ["", "⌨ B", ""]


def test_inspector_hides_the_effect_fields_in_basic_mode(window):
    insp = window._inspector
    window._cue_list.setCurrentRow(1)
    _pump()
    insp.set_lite(False)
    assert insp.chk_adlib.isChecked() and insp.edit_hotkey.text() == "B"
    assert insp.edit_hotkey.isVisibleTo(insp)
    insp.set_lite(True)
    insp.set_expanded(False)
    assert not insp.edit_hotkey.isVisibleTo(insp) and not insp.chk_adlib.isVisibleTo(insp)


def test_engine_keeps_effects_out_of_the_order():
    from engine.show_engine import ShowEngine, chain_indices

    cues = [_cue(0, follow_mode="SIMULTANEOUS"), _cue(1, adlib=True, hotkey="B", follow_mode="SIMULTANEOUS"),
            _cue(2, follow_mode="AUTO_FOLLOW"), _cue(3, adlib=True), _cue(4)]
    assert chain_indices(cues, 0) == [0, 2]                   # SIMULT pulls the next show cue
    assert chain_indices(cues, 1) == [1]                      # an effect pulls nothing with it
    assert ShowEngine.auto_follow_target(cues, cues[2]) == 4  # Auto-GO goes past the effect
    assert ShowEngine.auto_follow_target(cues, cues[3]) == -1


def test_cue_on_a_borrowed_player_stays_on_air(window):
    from engine.show_engine import ShowEngine

    window.set_live_mode(True)
    effect, show_cue = window._cues[1], window._cues[0]
    effect.status = CueStatus.LIVE
    window.set_slot_override(effect.cue_id, 5)              # main.py put it on spare 5
    ShowEngine.promote_to_live(window._cues, show_cue, exclude_ids=set(window._slot_override))
    assert effect.status == CueStatus.LIVE                   # same layer, other player
    window._on_go()                                          # a GO on that layer
    assert effect.status == CueStatus.LIVE
    window.mark_layer_stopped(window._runtime_slot(show_cue))  # its card faded
    assert effect.status == CueStatus.LIVE and show_cue.status != CueStatus.LIVE
    window.mark_layer_stopped(5)                             # the effect's own card
    assert effect.status != CueStatus.LIVE


def test_held_key_is_released_even_with_shift_and_shortcuts_yield(window, monkeypatch):
    filt = window._hotkey_filter
    target = QObject()
    monkeypatch.setattr(window, "isActiveWindow", lambda: True)
    window.set_live_mode(True)
    assert filt.eventFilter(target, _key(QEvent.Type.KeyPress, "n")) and window.fired == [9407]
    shifted = _key(QEvent.Type.KeyRelease, "N", Qt.KeyboardModifier.ShiftModifier)
    assert filt.eventFilter(target, shifted) and window._held_notes == {}
    override = _key(QEvent.Type.ShortcutOverride, "b")
    assert filt.eventFilter(target, override) and override.isAccepted()  # not the editor's shortcut
