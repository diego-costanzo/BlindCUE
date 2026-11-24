"""Take the user-manual screenshots by driving the real program.

    python tools/manual_screenshots.py <blindcue dir> <out dir> <lang> <media dir>

<lang> is it / en / pl, <out dir> normally blindcue/help/img/<lang>. The
text-cue and crossfade pictures are taken only when the code has those
features (tools/manual_features.py). The media dir must hold neutral,
generated files (never personal photos): poster.jpg, stage_backdrop.jpg,
opening_video.mp4, overture.mp3, finale.mp3 - tools/make_manual_media.py
creates them. Run it with USERPROFILE/HOME pointed at an empty folder so
the real autosave is never touched, and with FFmpeg on PATH (waveforms).
Then rebuild the manuals: python tools/build_manual.py
"""

from __future__ import annotations

import os
import pathlib
import sys

APP_DIR, OUT_DIR, LANG, MEDIA = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3], pathlib.Path(sys.argv[4])
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from manual_features import present  # noqa: E402

CAPTIONS = {"text_cues", "crossfade"} <= present(pathlib.Path(APP_DIR).resolve().parent)
OUT_DIR.mkdir(parents=True, exist_ok=True)
sys.argv = [sys.argv[0]]
sys.path.insert(0, APP_DIR)

from PySide6 import QtCore, QtWidgets  # noqa: E402

import i18n  # noqa: E402

i18n.saved_language = lambda: LANG

for _name in ("information", "warning", "critical", "question"):
    setattr(QtWidgets.QMessageBox, _name,
            staticmethod(lambda *a, **k: QtWidgets.QMessageBox.StandardButton.No))

OPEN_DIALOGS: list[QtWidgets.QDialog] = []


def _fake_exec(self, *a, **k):
    self.setModal(False)
    self.show()
    OPEN_DIALOGS.append(self)
    return 0


QtWidgets.QDialog.exec = _fake_exec

import main as bc_main  # noqa: E402
from models.cue import Cue, MediaType  # noqa: E402

SHOTS: list[str] = []


def pump(ms: int = 0) -> None:
    end = QtCore.QDeadlineTimer(ms)
    while True:
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 30)
        if end.hasExpired():
            break


def grab(widget, name: str) -> None:
    pump(150)
    widget.grab().save(str(OUT_DIR / f"{name}.png"))
    SHOTS.append(name)


OFF_SCREEN = QtCore.QPoint(-6000, 40)  # keep the windows out of the user's sight


def grab_dialog(opener, name: str) -> None:
    OPEN_DIALOGS.clear()
    opener()
    pump(300)
    for dlg in OPEN_DIALOGS:
        dlg.move(OFF_SCREEN)
        pump(400)
        grab(dlg, name)
        dlg.close()


def run(app) -> None:
    try:
        _run(app)
    finally:
        print("shots:", " ".join(SHOTS), flush=True)
        os._exit(0)


def _run(app) -> None:
    mw = next(w for w in app.topLevelWidgets()
              if isinstance(w, QtWidgets.QMainWindow) and hasattr(w, "_cue_list"))
    mw.apply_view_variant("full")          # every start opens in Lite; the manual shows every panel
    mw.setWindowState(QtCore.Qt.WindowState.WindowNoState)   # a small screen opens it maximised
    mw.show()
    mw.resize(1880, 1000)
    mw.move(OFF_SCREEN)
    mw._output.move(OFF_SCREEN + QtCore.QPoint(0, 1100))
    pump(600)
    table = mw._cue_list
    insp = mw._inspector

    file_menu = mw.menuBar().actions()[0].menu()
    file_menu.popup(mw.mapToGlobal(QtCore.QPoint(10, 30)))
    pump(300)
    grab(file_menu, "02_menu_file")
    file_menu.hide()

    for name, kind in (("poster.jpg", MediaType.IMAGE), ("opening_video.mp4", MediaType.VIDEO),
                       ("overture.mp3", MediaType.AUDIO), ("finale.mp3", MediaType.AUDIO)):
        mw._add_cue_from_file(str(MEDIA / name), kind)
        pump(300)
    pump(4000)  # waveform analysis

    table.selectRow(0)
    pump(900)
    grab(mw, "03_list_photo")
    insp.tab_widget.setCurrentIndex(1)
    pump(300)
    grab(insp, "05_inspector_photo_picture")

    table.selectRow(1)
    pump(2500)
    insp.tab_widget.setCurrentIndex(0)
    pump(300)
    grab(mw, "01_main_window_video")
    grab(insp, "04_inspector_video_cue")

    table.selectRow(2)
    pump(3500)
    insp.tab_widget.setCurrentIndex(2)
    pump(300)
    grab(mw, "06_list_audio")

    table.clearSelection()
    sel = table.selectionModel()
    for row in (2, 3):
        sel.select(table.model().index(row, 0),
                   QtCore.QItemSelectionModel.SelectionFlag.Select
                   | QtCore.QItemSelectionModel.SelectionFlag.Rows)
    pump(400)
    mw._on_add_group()
    pump(900)
    grab(mw, "07_group")

    backdrop_row = caption_row = None
    if CAPTIONS:
        from engine.text_render import render_text_png, text_cue_name
        backdrop = Cue(name="stage_backdrop.jpg", media_type=MediaType.IMAGE,
                       file_path=str(MEDIA / "stage_backdrop.jpg"))
        backdrop.crossfade = 2.0
        backdrop.fade_in = 0.0
        caption_text = {"it": "Atto I\nNel paese delle meraviglie",
                        "en": "Act I\nIn Wonderland",
                        "pl": "Akt I\nW krainie czarów"}[LANG]
        spec = {"text": caption_text, "size": 110, "position": "bottom"}
        caption = Cue(name=text_cue_name(spec), media_type=MediaType.IMAGE,
                      file_path=render_text_png(spec))
        caption.text_spec = spec
        caption.layer = 3
        caption.fade_in = 0.5
        caption.fade_out = 0.5
        for cue in (backdrop, caption):
            mw._append_new_cue(cue)
            pump(300)
        pump(800)
        backdrop_row = next(i for i, c in enumerate(mw._cues) if c is backdrop)
        caption_row = next(i for i, c in enumerate(mw._cues) if c is caption)
        table.selectRow(caption_row)
        pump(700)
        grab(mw, "15_list_with_caption")
        grab_dialog(mw._on_edit_text_cue, "13_caption_dialog")
        table.selectRow(backdrop_row)
        pump(700)
        insp.tab_widget.setCurrentIndex(2)
        pump(300)
        grab(insp, "16_inspector_crossfade")

    out = mw._output
    out.resize(960, 540)
    table.selectRow(0)
    pump(400)
    mw.set_live_mode(True)
    pump(900)
    mw._on_go()
    pump(2200)
    grab(mw, "08_live_after_go")
    grab(out, "09_output_window")
    if CAPTIONS:
        table.selectRow(backdrop_row)
        pump(400)
        mw._on_go()
        pump(800)
        grab(out, "17_crossfade")
        pump(2000)
        table.selectRow(caption_row)
        pump(400)
        mw._on_go()
        pump(1400)
        grab(out, "14_caption_on_screen")
    mw._on_blackout()
    pump(800)
    mw.set_live_mode(False)
    pump(600)

    grab_dialog(mw.open_device_settings_dialog, "10_devices")
    grab_dialog(mw.open_remote_control_dialog, "11_remote")
    grab_dialog(mw._open_surface_mapping_dialog, "12_surfaces")


_orig_exec = QtWidgets.QApplication.exec


def _exec(self=None, *a):
    app = QtWidgets.QApplication.instance()
    QtCore.QTimer.singleShot(4000, lambda: run(app))
    return _orig_exec()


QtWidgets.QApplication.exec = _exec
bc_main.main()
