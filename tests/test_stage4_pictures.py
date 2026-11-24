"""Stage 4 small items: preview never on the projector in the show, thumbnails in
the editing list, a picture shorter than its passages, the "slide" passage,
the output windows (to the front, clear).

Run:
    QT_QPA_PLATFORM=offscreen pytest -q tests/test_stage4_pictures.py
"""

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

import pytest  # noqa: E402
from models.cue import Cue, CueStatus, MediaType  # noqa: E402
from PySide6.QtCore import QCoreApplication, QSettings  # noqa: E402
from PySide6.QtGui import QColor, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _pump_until(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


@pytest.fixture()
def picture_file(tmp_path, qt_app) -> str:
    path = tmp_path / "photo.png"
    pm = QPixmap(320, 180)
    pm.fill(QColor("green"))
    pm.save(str(path))
    return str(path)


def _picture(cue_id: int, path: str, **extra) -> Cue:
    data = {"cue_id": cue_id, "name": f"p{cue_id}", "media_type": "IMAGE", "file_path": path, "layer": 1}
    data.update(extra)
    return Cue.from_dict(data)


@pytest.fixture()
def window(qt_app, picture_file):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    out = OutputWindow()
    out.resize(640, 360)
    out.show()
    win = MainWindow(out)
    win._clock_timer.stop()
    win._cues = [_picture(8801, picture_file), _picture(8802, picture_file, layer=2),
                 Cue.from_dict({"cue_id": 8803, "name": "s", "media_type": "AUDIO", "file_path": "/x/s.wav",
                                "layer": 3})]
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    _pump()
    try:
        yield win
    finally:
        win._force_closing = True
        out.force_close()
        win.close()
        _pump()
        win.deleteLater()
        out.deleteLater()
        _pump()


# ── 4.4: the preview never stays on the projector after entering the show ──

def test_entering_the_show_takes_the_preview_off_the_projector(window):
    out = window._output
    window._preview_panel.btn_live_mirror.setChecked(True)          # "show on the projector"
    _pump()
    assert window._live_mirror_active and out._image_containers[1].isVisible()
    window.set_live_mode(True, checked=True)
    assert not window._preview_panel.btn_live_mirror.isChecked() and not window._live_mirror_active
    assert _pump_until(lambda: not out._image_containers[1].isVisible(), 2.0), "the preview stayed"
    # Moving the next cue in the show never pushes it to the projector.
    window._cue_list.setCurrentRow(1)
    _pump(0.1)
    assert not out._image_containers[2].isVisible()
    window._live_mirror_active = True                                # even if it were somehow on
    window._mirror_active_cue_to_live()
    window._on_preview_video_frame_for_mirror(None)
    assert not out._image_containers[2].isVisible()


def test_entering_the_rehearsal_too(window):
    out = window._output
    window._preview_panel.btn_live_mirror.setChecked(True)
    _pump()
    assert out._image_containers[1].isVisible()
    window._rehearsal = True
    window.set_live_mode(True, checked=True)
    assert not window._live_mirror_active
    assert _pump_until(lambda: not out._image_containers[1].isVisible(), 2.0)


def test_what_is_on_air_stays_when_the_preview_goes(window, picture_file):
    out = window._output
    on_air = window._cues[1]
    on_air.status = CueStatus.LIVE
    out.show_image(2, picture_file)                                  # the show put it there
    window._preview_panel.btn_live_mirror.setChecked(True)
    window._cue_list.setCurrentRow(0)
    _pump()
    window.set_live_mode(True, checked=True)
    _pump(0.4)
    assert out._image_containers[2].isVisible()                      # the cue on air stays
    assert not out._image_containers[1].isVisible()                  # the preview went


# ── 4.4: a picture shorter than its passages + 0.5 s ───────────────────────

def test_picture_timing_rules():
    from engine.picture_timing import min_hold_seconds, too_short, transition_seconds

    assert transition_seconds(1.0, 0.5, 0.0) == 1.5
    assert transition_seconds(0.0, 0.5, 1.0) == 1.5          # crossfade and fade in overlap at the start
    assert min_hold_seconds(1.0, 1.0, 0.0) == 2.5
    assert too_short(2.0, 1.0, 1.0, 0.0)
    assert not too_short(2.5, 1.0, 1.0, 0.0)
    assert not too_short(0.0, 3.0, 3.0, 0.0)                 # no time = until the next cue


def test_the_list_check_reports_it(picture_file):
    from engine.list_check import PICTURE_TOO_SHORT, list_problems

    cues = [_picture(1, picture_file, hold_time=1.0, fade_in=0.5, fade_out=0.5),
            _picture(2, picture_file, hold_time=3.0, fade_in=0.5, fade_out=0.5),
            _picture(3, picture_file, hold_time=1.0, fade_in=0.5, fade_out=0.5, enabled=False)]
    assert list_problems(cues) == [(0, PICTURE_TOO_SHORT)]


def test_the_inspector_warns(window):
    cue = window._cues[0]
    cue.hold_time, cue.fade_in, cue.fade_out = 1.0, 0.5, 0.5
    window._update_inspector(cue)
    hint = window._inspector.lbl_hold_hint
    assert "⚠" in hint.text() and "1.5" in hint.toolTip()
    window._inspector.spin_hold_time.setValue(4.0)
    assert "⚠" not in hint.text()


def test_the_edit_window_warns(qt_app, picture_file):
    from ui.edit_cue_dialog import EditCueDialog

    cue = _picture(8810, picture_file, hold_time=1.0, fade_in=0.5, fade_out=0.5)
    dlg = EditCueDialog(cue)
    try:
        assert dlg.lbl_timing.isVisibleTo(dlg) and "1.5" in dlg.lbl_timing.text()
        dlg.sp_hold.setValue(3.0)
        assert not dlg.lbl_timing.isVisibleTo(dlg)
        dlg.cb_xfade_style.setCurrentIndex(dlg.cb_xfade_style.findData("slide"))
        assert dlg.changes() == {"hold_time": 3.0, "crossfade_style": "slide"}
    finally:
        dlg.deleteLater()


# ── 4.4 (MultiPlay): the "slide" passage ───────────────────────────────────

def test_crossfade_style_is_saved_and_checked():
    cue = Cue(name="a", media_type=MediaType.IMAGE, file_path="a.png")
    assert cue.crossfade_style == "dissolve"
    cue.crossfade_style = "slide"
    assert Cue.from_dict(cue.to_dict()).crossfade_style == "slide"
    data = cue.to_dict()
    data["crossfade_style"] = "explode"
    assert Cue.from_dict(data).crossfade_style == "dissolve"


def test_slide_pushes_the_old_picture_out_and_brings_the_new_one_in(qt_app, picture_file):
    from ui.output_window import OutputWindow

    out = OutputWindow()
    out.resize(640, 360)
    out.show()
    _pump()
    try:
        out.show_image(1, picture_file)
        base = out._image_containers[1].pos().x()
        width = out._scene.sceneRect().width()
        out.begin_crossfade(1, 0.4, "slide")
        out.show_image(1, picture_file, scale=0.5)                 # the new picture, laid out during the slide
        ghost = out._xfade_ghosts[1]
        assert out._slide_shifts[1] == pytest.approx(width)
        new_base = out._image_containers[1].pos().x() - width      # the layout kept the offset
        _pump(0.15)
        assert ghost.pos().x() < out._scene.sceneRect().left()     # the old one moves out to the left
        assert 0 < out._slide_shifts.get(1, 0.0) < width
        assert _pump_until(lambda: 1 not in out._xfade_ghosts, 3.0)
        assert out._slide_shifts.get(1, 0.0) == 0.0
        assert out._image_containers[1].pos().x() == pytest.approx(new_base)  # in place at the end
        assert base is not None
    finally:
        out.force_close()
        out.deleteLater()
        _pump()


def test_a_slide_onto_an_empty_layer_still_slides_in(qt_app, picture_file):
    from ui.output_window import OutputWindow

    out = OutputWindow()
    out.resize(640, 360)
    out.show()
    _pump()
    try:
        out.begin_crossfade(2, 0.3, "slide")
        assert 2 not in out._xfade_ghosts and out._slide_shifts.get(2, 0.0) > 0
        out.begin_crossfade(3, 0.3)                                # a dissolve with nothing: nothing
        assert 3 not in out._xfade_timers
        out.clear_layer(2)                                         # PANIC / clear end a slide at once
        assert out._slide_shifts.get(2, 0.0) == 0.0
    finally:
        out.force_close()
        out.deleteLater()
        _pump()


def test_the_inspector_sets_the_style(window):
    cue = window._cues[0]
    window._update_inspector(cue)
    insp = window._inspector
    # (the fields sit on a tab that is not the current one: isHidden is their own switch)
    assert not insp.combo_crossfade_style.isHidden() and insp.chk_hold_last_frame.isHidden()
    insp.combo_crossfade_style.setCurrentIndex(insp.combo_crossfade_style.findData("slide"))
    window._apply_inspector_to_cue()
    assert cue.crossfade_style == "slide"


def test_the_inspector_offers_hold_last_frame_for_a_video(window):
    video = Cue.from_dict({"cue_id": 8820, "name": "v", "media_type": "VIDEO", "file_path": "/x/v.mp4"})
    window._cues.append(video)
    window._refresh_cue_list(keep_selection=False)
    window._cue_list.setCurrentRow(3)
    window._update_inspector(video)
    insp = window._inspector
    assert not insp.chk_hold_last_frame.isHidden() and insp.chk_hold_last_frame.isEnabled()
    assert not insp.combo_crossfade_style.isHidden()
    insp.chk_hold_last_frame.setChecked(True)
    window._apply_inspector_to_cue()
    assert video.hold_last_frame is True


# ── 4.4 (MultiPlay): output windows ────────────────────────────────────────

def test_clear_outputs_fades_the_pictures_and_keeps_the_sound(window, picture_file):
    out = window._output
    picture, _other, sound = window._cues
    picture.status = sound.status = CueStatus.LIVE
    out.show_image(1, picture_file)
    out.show_image(2, picture_file)                                 # left over by a preview: no cue
    asked: list[int] = []
    window.layer_clear_requested.connect(asked.append)
    window.clear_outputs()
    assert asked == [1]                                             # main.py fades the cue on air
    assert picture.status == CueStatus.LOADED and sound.status == CueStatus.LIVE
    assert not out._image_containers[2].isVisible()                 # the leftover is gone at once


def test_bring_outputs_to_front(window):
    window.bring_outputs_to_front()
    assert "1" in window._status_label.text()


def test_no_screen_numbers_while_something_is_on_air(window):
    shown: list[bool] = []
    window._show_screen_numbers = lambda: shown.append(True)
    window._cues[0].status = CueStatus.LIVE
    window._identify_screens_from_menu()
    assert shown == [] and "in onda" in window._status_label.text()
    window._cues[0].status = CueStatus.LOADED
    window._identify_screens_from_menu()
    assert shown == [True]


def test_the_devices_menu_has_the_output_commands(window):
    texts = []
    for menu_act in window.menuBar().actions():
        if menu_act.menu() is None:
            continue
        for act in menu_act.menu().actions():
            if act.menu() is not None:
                texts += [a.text() for a in act.menu().actions()]
    assert any("Identifica gli schermi" in t for t in texts)
    assert any("primo piano" in t for t in texts) and any("Pulisci le uscite" in t for t in texts)


# ── 4.4: thumbnails in the editing list ────────────────────────────────────

def test_thumbnails_follow_the_setting_and_the_profile():
    from ui.thumbnails import thumbnails_wanted

    assert thumbnails_wanted("auto", "standard") and thumbnails_wanted("auto", "performance")
    assert not thumbnails_wanted("auto", "eco")
    assert thumbnails_wanted("on", "eco") and not thumbnails_wanted("off", "performance")


def test_a_picture_gets_a_thumbnail_in_the_background(qt_app, picture_file):
    from ui.thumbnails import ThumbnailCache

    cache = ThumbnailCache()
    got: list[bool] = []
    cache.ready.connect(lambda: got.append(True))
    assert cache.get(picture_file, "IMAGE") is None                  # made in the background
    assert _pump_until(lambda: bool(got), 5.0)
    pix = cache.get(picture_file, "IMAGE")
    assert pix is not None and pix.width() <= 128 and pix.height() <= 72
    assert cache.get(picture_file, "AUDIO") is None and cache.get("/nope.png", "IMAGE") is None
    assert _pump_until(lambda: cache.pending() == 0, 5.0)            # a missing file: no thumbnail, no retry
    assert cache.get("/nope.png", "IMAGE") is None and cache.pending() == 0
    cache.set_paused(True)
    assert cache.get(picture_file + "x", "IMAGE") is None and cache.pending() == 0


def test_the_list_draws_thumbnails_only_when_on(window):
    from ui.cue_table import ROLE_THUMB_PATH

    item = window._cue_list.item(0, 2)
    assert item.data(ROLE_THUMB_PATH) == window._cues[0].file_path
    assert window._cue_list.item(2, 2).data(ROLE_THUMB_PATH) == ""   # a sound has none
    window._set_thumbnails_on(False)
    assert window._cue_list.thumbnail_source is None
    assert QSettings("BlindCue", "BlindCue").value("ui/list_thumbnails") == "off"
    window._set_thumbnails_on(True)
    source = window._cue_list.thumbnail_source
    assert source is not None
    assert _pump_until(lambda: source(window._cues[0].file_path, "IMAGE") is not None, 5.0)
    window._cue_list.viewport().repaint()                            # the delegate draws it
    window.set_live_mode(True, checked=True)
    assert source(window._cues[0].file_path, "IMAGE") is None        # never in the show
