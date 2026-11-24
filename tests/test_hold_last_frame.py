"""Stage 4.4: "hold the last frame" of a video (explicit held state).

The video pauses HOLD_MARGIN_MS before its end (the FFmpeg backend clears the
picture at EndOfMedia), its frame becomes a still on the layer and the player
stops. The cue stays LIVE but has ended: it never blocks a GO, a stop never
points the GO back at it, its card says "last frame", Undo GO brings it back
as the picture.

Run:
    QT_QPA_PLATFORM=offscreen pytest -q tests/test_hold_last_frame.py
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
from models.cue import Cue, CueSection, CueStatus  # noqa: E402
from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtMultimedia import QMediaPlayer  # noqa: E402
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


def _video(cue_id: int = 7701, **extra) -> Cue:
    data = {"cue_id": cue_id, "name": f"v{cue_id}", "media_type": "VIDEO", "file_path": "/x/v.mp4"}
    data.update(extra)
    return Cue.from_dict(data)


def _frame(color: str = "red") -> QImage:
    img = QImage(160, 90, QImage.Format.Format_RGB32)
    img.fill(QColor(color))
    return img


# ── The cue ──────────────────────────────────────────────────────────────────

def test_the_choice_is_saved_and_old_shows_load():
    cue = _video(hold_last_frame=True)
    assert Cue.from_dict(cue.to_dict()).hold_last_frame is True
    data = cue.to_dict()
    del data["hold_last_frame"]
    assert Cue.from_dict(data).hold_last_frame is False


def test_wants_hold_only_for_a_video_with_an_end():
    from ui.held_frames import wants_hold

    assert wants_hold(_video(hold_last_frame=True))
    assert not wants_hold(_video())
    assert not wants_hold(_video(hold_last_frame=True, loop=True, loop_count=0))   # endless loop: no end
    assert wants_hold(_video(hold_last_frame=True, loop=True, loop_count=2))
    endless = _video(hold_last_frame=True)
    endless.sections = [CueSection(label="A", start=0.0, end=2.0, loops=0)]
    assert not wants_hold(endless)
    picture = Cue.from_dict({"cue_id": 7702, "name": "p", "media_type": "IMAGE", "file_path": "/x/p.png",
                             "hold_last_frame": True})
    assert not wants_hold(picture)


# ── The player stops short of the end ────────────────────────────────────────

class _PlayingDeck:
    """QMediaPlayer stand-in that plays (never at EndOfMedia)."""

    def __init__(self) -> None:
        self.pause_calls = 0
        self.pos = 0

    def playbackState(self):  # noqa: N802 - Qt API
        return QMediaPlayer.PlaybackState.PlayingState

    def mediaStatus(self):  # noqa: N802 - Qt API
        return QMediaPlayer.MediaStatus.BufferedMedia

    def pause(self) -> None:
        self.pause_calls += 1

    def position(self) -> int:
        return self.pos


@pytest.fixture()
def player(qt_app):
    from engine.player_live import LivePlayer

    lp = LivePlayer()
    deck = _PlayingDeck()
    lp._deck_pair = lambda idx=None: (deck, lp._audio)  # type: ignore[assignment]
    lp._deck = deck
    fired: list[bool] = []
    lp.signals.eof_reached.connect(lambda: fired.append(True))
    lp._fired = fired
    try:
        yield lp
    finally:
        lp._driver_timer.stop()
        lp.shutdown()


def test_a_held_video_pauses_short_of_its_end(player):
    from engine.player_live import HOLD_MARGIN_MS

    player._duration_sec = 10.0
    player.set_hold_last_frame(True)
    player._check_boundaries(10_000 - HOLD_MARGIN_MS - 30)
    assert player._fired == []
    player._check_boundaries(10_000 - HOLD_MARGIN_MS + 1)
    assert player._fired == [True] and player._deck.pause_calls == 1   # paused, not at EndOfMedia


def test_the_out_point_counts_and_only_the_last_loop_holds(player):
    from engine.player_live import HOLD_MARGIN_MS

    player._end_ms = 4_000
    player._is_looping, player._loop_count = True, 2
    player.set_hold_last_frame(True)
    player._execute_jump_ms = lambda ms: None  # type: ignore[assignment]
    player._check_boundaries(4_000 - HOLD_MARGIN_MS + 1)                 # first pass: loops on
    assert player._fired == []
    player._check_boundaries(4_000 - 10)
    assert player._current_loop_iteration == 1 and player._fired == []
    player._finished = False
    player._check_boundaries(4_000 - HOLD_MARGIN_MS + 1)                 # last pass: holds
    assert player._fired == [True]


def test_without_hold_nothing_changes(player):
    player._duration_sec = 10.0
    player._check_boundaries(9_900)
    assert player._fired == []                     # the end is EndOfMedia, as before


def test_a_held_video_does_not_fade_its_picture_out_at_the_end(player):
    seen: list[float] = []
    player.set_opacity_callback(seen.append)
    player.configure_automation(is_video=True, base_volume=1.0, base_opacity=1.0, fade_in=0.0,
                                fade_out=2.0, fade_curve="linear", volume_points=[], opacity_points=[],
                                sections=[])
    player._duration_sec = 10.0
    player._end_ms = 10_000
    player.set_hold_last_frame(True)
    player._last_emitted_opacity = None
    player._apply_envelope_at(9.5)
    assert seen and seen[-1] == pytest.approx(1.0)        # the frame stays visible
    player.set_hold_last_frame(False)
    player._last_emitted_opacity = None
    player._apply_envelope_at(9.5)
    assert seen[-1] < 0.5                                  # an ordinary video still fades out


def test_load_and_stop_forget_the_hold(player):
    player.set_hold_last_frame(True)
    player.stop()
    assert not player.holds_last_frame()


# ── The output keeps the frame as a still ────────────────────────────────────

@pytest.fixture()
def output(qt_app):
    from ui.output_window import OutputWindow

    out = OutputWindow()
    out.resize(640, 360)
    out.show()
    _pump(0.05)
    try:
        yield out
    finally:
        out.force_close()
        out.deleteLater()
        _pump()


def test_the_frame_replaces_the_video_with_its_layout_and_opacity(output):
    output.show_video_widget(scale=0.5, pos_x=0.2, opacity=0.6, layer=2)
    assert output._video_containers[2].isVisible()
    assert output.hold_video_frame(2, _frame())
    assert not output._video_containers[2].isVisible()
    assert output._image_containers[2].isVisible()
    item = output._layer_pixmaps[2]
    assert not item.pixmap().isNull() and item.opacity() == pytest.approx(0.6, abs=0.01)
    layout = output._image_layouts[2]
    assert layout["scale"] == 0.5 and layout["pos_x"] == 0.2
    assert not output.hold_video_frame(1, QImage())          # no frame: nothing to keep


# ── The controller (main.py's side) ──────────────────────────────────────────

class _FakePlayer:
    def __init__(self, frame: QImage | None) -> None:
        self.frame = frame
        self.stops = 0
        self.hold = None
        self.tails: list[float] = []

    def current_frame_image(self):
        return self.frame

    def stop(self) -> None:
        self.stops += 1

    def set_hold_last_frame(self, on: bool) -> None:
        self.hold = on

    def hand_over_tail(self, seconds: float) -> bool:
        self.tails.append(seconds)
        return True


class _FakeWindow:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def set_last_frame_held(self, cue_id, slot, on, kept=None) -> None:
        self.calls.append((cue_id, slot, on, kept is not None))


def _controller(output, frame=None):
    from ui.held_frames import HeldFrameController

    players = {1: _FakePlayer(frame if frame is not None else _frame())}
    win = _FakeWindow()
    ctl = HeldFrameController(window=win, players=players, out_window=lambda slot: output,
                              local_layer=lambda slot: slot)
    return ctl, players[1], win


def test_freeze_keeps_the_frame_and_stops_the_player(output):
    ctl, lp, win = _controller(output)
    cue = _video(hold_last_frame=True)
    ctl.arm(cue, lp)
    assert lp.hold is True
    output.show_video_widget(layer=1)
    assert ctl.freeze(cue, 1)
    assert ctl.holds(1, cue.cue_id) and lp.stops == 1
    assert output._image_containers[1].isVisible()
    assert win.calls[-1] == (cue.cue_id, 1, True, True)
    assert ctl.ended(cue, 1)                                   # after the Post-Delay: still held


def test_no_frame_or_no_wish_means_the_old_behaviour(output):
    ctl, lp, _win = _controller(output)
    assert not ctl.freeze(_video(), 1)                         # not asked for
    lp.frame = None
    assert not ctl.freeze(_video(hold_last_frame=True), 1)     # EndOfMedia already cleared it
    assert not ctl.holds(1) and lp.stops == 0


def test_fade_and_release_and_clear(output):
    ctl, lp, win = _controller(output)
    cue = _video(hold_last_frame=True)
    output.show_video_widget(layer=1)
    ctl.freeze(cue, 1)
    done: list[bool] = []
    ctl.fade_out(1, 0.1, callback=lambda: done.append(True))
    assert not ctl.holds(1) and win.calls[-1][2] is False
    _pump(0.5)
    assert done == [True] and not output._image_containers[1].isVisible()
    ctl.state.hold(1, cue.cue_id, _frame())
    ctl.clear_all()
    assert ctl.state.slots() == {}


def test_undo_go_brings_it_back_as_the_frame_never_played_again(output):
    ctl, lp, _win = _controller(output)
    cue = _video(hold_last_frame=True)
    output.show_video_widget(layer=1)
    ctl.freeze(cue, 1)
    ctl.release(1)                                             # another cue took the layer
    output.show_video_widget(layer=1)                          # ... a video plays there now
    stops = lp.stops
    assert ctl.restore(cue, 1, seconds=1.0)
    assert lp.tails == [1.0] and lp.stops == stops + 1          # its sound fades out on its own
    assert ctl.holds(1, cue.cue_id) and output._image_containers[1].isVisible()
    assert not output._video_containers[1].isVisible()
    assert not ctl.restore(_video(cue_id=7799, hold_last_frame=True), 1)   # never held: nothing kept


def test_only_the_last_frames_are_kept():
    from ui.held_frames import HeldFrames

    state = HeldFrames(keep=2)
    for cid in (1, 2, 3):
        state.hold(cid, cid, object())
    assert state.frame_of(1) is None and state.frame_of(3) is not None


# ── Undo GO ──────────────────────────────────────────────────────────────────

def test_undo_plan_brings_a_held_frame_back():
    from engine.undo_go import FADE, LIFT, RESTORE, UndoRecord, undo_plan

    held = _video(7710, hold_last_frame=True)
    held.status = CueStatus.LOADED
    picture = Cue.from_dict({"cue_id": 7711, "name": "p", "media_type": "IMAGE", "file_path": "/x/p.png"})
    video = _video(7712)
    for c in (picture, video):
        c.status = CueStatus.LIVE
    rec = UndoRecord(first_id=7711, started=0.0, ids=[7711, 7712],
                     replaced={7711: 7710, 7712: 7710}, held={7710})
    steps = {s.cue_id: s for s in undo_plan([held, picture, video], rec, set())}
    assert steps[7711].how == RESTORE and steps[7711].restore_id == 7710
    assert steps[7712].how == FADE and steps[7712].restore_id == 7710 and steps[7712].cut_id is None
    # The GO that started a video now holding its frame: taken off like a picture.
    held.status = CueStatus.LIVE
    rec2 = UndoRecord(first_id=7710, started=0.0, ids=[7710])
    assert undo_plan([held], rec2, set(), held_now={7710})[0].how == LIFT
    assert undo_plan([held], rec2, set())[0].how == FADE        # playing: faded as before


# ── The window: an explicit state, never "playing" ───────────────────────────

@pytest.fixture()
def window(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    out = OutputWindow()
    win = MainWindow(out)
    win._clock_timer.stop()
    win._cues = [_video(7720 + i, hold_last_frame=True, layer=1) for i in range(2)]
    win._cues[0].exclusive = True
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(1)
    win._commit_undo_point()
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


def _hold(win, idx: int = 0) -> Cue:
    cue = win._cues[idx]
    cue.status = CueStatus.LIVE
    win._update_live_layer_label(cue)
    win.set_last_frame_held(cue.cue_id, 1, True, (_frame(), 1.0))
    return cue


def test_a_held_exclusive_cue_does_not_block_the_go(window):
    cue = window._cues[0]
    cue.status = CueStatus.LIVE
    assert window._exclusive_blocker() is cue
    _hold(window)
    assert window._exclusive_blocker() is None


def test_a_stop_never_points_the_go_back_at_a_held_cue(window):
    cue = window._cues[0]
    cue.status = CueStatus.LIVE
    window._last_manual_go_cue = cue
    assert window._stopped_manual_go_index() == 0
    _hold(window)
    assert window._stopped_manual_go_index() is None


def test_its_card_says_last_frame_without_a_clock(window):
    from ui.now_playing import STILL

    cue = _hold(window)
    window._on_live_clock_tick()
    card = window._live_show_panel.now_playing.cards()[cue.cue_id]
    assert card.kind == STILL and "ultimo fotogramma" in card.lbl_state.text()
    assert window._live_clocks.cue_time(cue.cue_id) is None
    bar = window._live_status._layer_labels[1]
    assert bar._phase == "HOLD" and not bar._is_seekable()


def test_ctrl_z_keeps_the_held_state(window):
    cue = _hold(window)
    window._cues[1].name = "changed"
    window._commit_undo_point()
    window._on_undo()
    again = next(c for c in window._cues if c.cue_id == cue.cue_id)
    assert again.status == CueStatus.LIVE and window.is_last_frame_held(again)
    assert window._live_clocks.cue_time(cue.cue_id) is None      # the label refresh gave no clock back


def test_released_or_stopped_it_is_an_ordinary_cue_again(window):
    cue = _hold(window)
    window.set_last_frame_held(cue.cue_id, 1, False)
    assert not window.is_last_frame_held(cue)
    _hold(window)
    cue.status = CueStatus.LOADED                                # PANIC / Fade All demote it
    assert not window.is_last_frame_held(cue)


def test_the_projector_gets_the_frame_again_not_an_empty_video(window):
    cue = _hold(window)
    window._push_cue_to_output(cue)
    assert window._output._image_containers[1].isVisible()
    assert not window._output._video_containers[1].isVisible()


def test_undo_go_steps_treat_a_held_frame_as_a_picture(window):
    from engine.undo_go import LIFT, UndoRecord

    cue = _hold(window)
    window._undo_go = UndoRecord(first_id=cue.cue_id, started=time.monotonic(), ids=[cue.cue_id])
    assert window._undo_go_steps()[0].how == LIFT
