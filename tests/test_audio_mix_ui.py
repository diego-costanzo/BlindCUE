"""Mixer settings in the window (3.2 / 3.9): the panel, the inspector, the Edit cue window, the outputs dialog."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

APP_DIR = Path(__file__).resolve().parents[1] / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from models.cue import Cue, MediaType
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _audio(**mix) -> Cue:
    return Cue(cue_id=8801, name="song", media_type=MediaType.AUDIO, file_path="song.wav", audio_mix=mix)


def test_panel_rows_levels_and_effects(qt_app):
    from ui.audio_mix_panel import AudioMixPanel

    panel = AudioMixPanel()
    changes = []
    panel.changed.connect(lambda: changes.append(True))
    panel.load({}, "stage")
    assert panel.values() == {} and not panel.btn_toggle.isChecked() and not changes
    panel.sl_pan.setValue(-40)
    assert panel.values() == {"pan": -0.4} and changes
    panel.btn_add.click()                         # the first free output: Hall
    panel.btn_add.click()                         # then Foldback
    assert not panel.btn_add.isEnabled()          # every output has its row
    _w, _combo, spin = panel._rows[1]
    spin.set_db(None)                             # -INF: silent there, but the row stays
    panel.spin_level.setValue(3.0)
    panel.spin_eq["low"].setValue(4.0)
    panel.spin_reverb.setValue(30)
    values = panel.values()
    assert values["sends"] == [{"out": "hall", "db": 0.0}, {"out": "foldback", "db": None}]
    assert values["level_db"] == 3.0 and values["eq"]["low"] == 4.0 and values["reverb"] == 0.3
    panel.spin_shift.setValue(-6.0)
    panel.btn_shift.click()                       # every row moves, -INF stays
    values = panel.values()
    assert values["level_db"] == -3.0 and values["sends"][0]["db"] == -6.0 and values["sends"][1]["db"] is None
    panel.set_main_output("hall")                 # the cue's own output is Hall now: its extra row goes
    assert [s["out"] for s in panel.values()["sends"]] == ["foldback"]
    panel.load(_audio(pan=0.5).audio_mix, "stage")
    assert panel.btn_toggle.isChecked() and panel.sl_pan.value() == 50 and not panel._rows


def test_panel_says_when_the_mixer_is_off(qt_app):
    from engine.audio_mixer_output import SETTING_ENABLED
    from ui.audio_mix_panel import AudioMixPanel

    panel = AudioMixPanel()
    QSettings("BlindCue", "BlindCue").setValue(SETTING_ENABLED, False)
    try:
        panel.load({"pan": 1.0}, "stage")
        assert "⚠" in panel.lbl_note.text()
    finally:
        QSettings("BlindCue", "BlindCue").remove(SETTING_ENABLED)
    panel.load({"pan": 1.0}, "stage")
    assert "⚠" not in panel.lbl_note.text()


def test_inspector_writes_the_mix_of_a_sound_cue_only(qt_app):
    from ui.inspector_panel import CueInspectorPanel

    insp = CueInspectorPanel()
    song = _audio(pan=-1.0)
    insp.load_cue(song, 0)
    assert insp.mix_panel.sl_pan.value() == -100
    insp.mix_panel.sl_pan.setValue(25)
    insp.apply_to_cue(song)
    assert song.audio_mix == {"pan": 0.25}
    film = Cue(cue_id=8802, name="film", media_type=MediaType.VIDEO, file_path="film.mp4", audio_mix={"pan": 0.5})
    insp.load_cue(film, 1)
    assert insp.mix_panel.isHidden()              # video sound stays on Qt: no mixer fields
    insp.apply_to_cue(film)
    assert film.audio_mix == {"pan": 0.5}         # kept as it was


def test_edit_window_hands_back_the_mix(qt_app):
    from ui.edit_cue_dialog import EditCueDialog

    song = _audio()
    dlg = EditCueDialog(song)
    try:
        assert dlg.changes() == {}
        dlg.mix_panel.btn_add.click()
        assert dlg.changes() == {"audio_mix": {"sends": [{"out": "hall", "db": 0.0}]}}
    finally:
        dlg.done(0)
        dlg.deleteLater()


def test_outputs_dialog_switches_the_mixer_and_allows_a_boost(qt_app):
    from engine.audio_mixer_output import SETTING_ENABLED, SETTING_LEAD, mixer_enabled
    from engine.audio_routes import TRIM_MAX_DB
    from engine.device_manager import DeviceManager
    from ui.audio_outputs_dialog import AudioOutputsDialog

    dlg = AudioOutputsDialog(DeviceManager())
    try:
        assert dlg._rows["stage"][2].maximum() == TRIM_MAX_DB
        dlg.chk_mixer.setChecked(False)
        assert not mixer_enabled()
        dlg.chk_mixer.setChecked(True)
        assert mixer_enabled()
        dlg.combo_lead.setCurrentIndex(dlg.combo_lead.count() - 1)
        assert QSettings("BlindCue", "BlindCue").value(SETTING_LEAD, type=int) == dlg.combo_lead.currentData()
    finally:
        QSettings("BlindCue", "BlindCue").remove(SETTING_ENABLED)
        QSettings("BlindCue", "BlindCue").remove(SETTING_LEAD)
        dlg.done(0)
        dlg.deleteLater()
