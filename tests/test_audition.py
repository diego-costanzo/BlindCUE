"""Stage 5, item 5.12 (rest): listening in the "Add audio" window; testing a cue never starts the next ones.

No sound is played here: the dialog's player is replaced (the speakers of this computer are shared).
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from models.cue import Cue, CueStatus
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_listen_before_choosing(tmp_path):
    QApplication.instance() or QApplication([])
    from ui.audio_pick_dialog import AudioPickDialog

    sound = tmp_path / "bell.mp3"
    sound.write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("x")
    dlg = AudioPickDialog(None, "Aggiungi audio", str(tmp_path), "Audio (*.mp3)")
    calls = []
    dlg._player.setSource = lambda url: calls.append(("source", url.toLocalFile()))
    dlg._player.play = lambda: calls.append(("play",))
    try:
        assert not dlg.btn_listen.isEnabled()                    # nothing highlighted yet
        dlg._on_current(str(tmp_path / "notes.txt"))
        assert not dlg.btn_listen.isEnabled()                    # not a sound
        dlg._on_current(str(sound))
        assert dlg.btn_listen.isEnabled()
        dlg.btn_listen.click()
        assert [c[0] for c in calls] == ["source", "play"] and Path(calls[0][1]) == sound
        assert "bell.mp3" in dlg.lbl_status.text()
        dlg._on_current(str(tmp_path / "notes.txt"))             # another file: the sound stops
        assert dlg.lbl_status.text() == ""
    finally:
        dlg.done(0)


def test_add_audio_uses_the_listening_window(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from models.cue import MediaType
    from ui import audio_pick_dialog
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    sound = tmp_path / "bell.mp3"
    sound.write_bytes(b"x")
    asked = []
    monkeypatch.setattr(audio_pick_dialog, "pick_audio_file",
                        lambda *a, **k: asked.append(a[1]) or str(sound))
    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        win._on_add_media(MediaType.AUDIO)
        assert asked == ["Aggiungi audio"] and len(win._cues) == 1
        assert win._cues[0].layer == 2 and Path(win._cues[0].file_path) == sound
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def _show(tmp_path):
    picture = tmp_path / "p.png"
    picture.write_bytes(b"x")
    sound = tmp_path / "s.mp3"
    sound.write_bytes(b"x")
    return [Cue.from_dict({"cue_id": 9951, "name": "picture", "media_type": "IMAGE", "file_path": str(picture),
                           "hold_time": 0.2, "follow_mode": "AUTO_FOLLOW"}),
            Cue.from_dict({"cue_id": 9952, "name": "sound", "media_type": "AUDIO", "file_path": str(sound),
                           "follow_mode": "AUTO_FOLLOW"}),
            Cue.from_dict({"cue_id": 9953, "name": "next", "media_type": "AUDIO", "file_path": str(sound)})]


def test_testing_a_cue_never_starts_the_next_ones(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.edit_cue_dialog import EditCueDialog
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    fired = []
    win.cue_fired.connect(lambda cue: fired.append(cue.name))
    monkeypatch.setattr(win, "trigger_auto_follow_from", lambda cue: fired.append(f"follow {cue.name}"))
    try:
        win._cues = _show(tmp_path)
        win._refresh_cue_list(keep_selection=False)
        win._cue_list.setCurrentRow(0)
        _pump()
        # The picture plays in the preview to its end (0.2 s) and past it.
        win.start_image_preview_playback(win._cues[0])
        win._img_previz_timer.stop()
        for _ in range(40):
            win._on_img_previz_tick()
        # The "Edit cue" window's own player reaches the end of the sound.
        dlg = EditCueDialog(win._cues[1], parent=win)
        if getattr(dlg, "_player", None) is not None:
            dlg._player.signals.eof_reached.emit()
        dlg.reject()
        dlg.deleteLater()
        _pump(0.1)
        assert fired == [] and all(c.status != CueStatus.LIVE for c in win._cues)
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
    # The preview player of the main window: its end only puts the playhead back (main.py wiring).
    source = (APP_DIR / "main.py").read_text(encoding="utf-8")
    hooks = re.findall(r"test_player\.signals\.eof_reached\.connect\((\w+)\)", source)
    assert hooks == ["_reset_preview_to_in"]
    body = source.split("def _reset_preview_to_in", 1)[1].split("\n        def ", 1)[0]
    assert not re.search(r"_on_go|cue_fired|trigger_auto_follow|_fire_|_launch", body)
