"""Stage 3, item 3.3: how a playlist plays - transitions, random order with a gap, loop,
remembered position, wake with the next track, gapless start (the next track opened early)."""

from __future__ import annotations

import os
import random
import subprocess
import sys
import textwrap
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from engine import playlist_flow as pf
from models.cue import Cue, GroupMode, MediaType, sanitize_action_spec
from PySide6.QtCore import QCoreApplication, QObject
from PySide6.QtMultimedia import QMediaDevices, QMediaPlayer
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


# ── Qt-free order ─────────────────────────────────────────────────────


def test_shuffle_never_repeats_within_the_gap():
    rng = random.Random(7)
    ids = list(range(1, 9))
    history: list[int] = []
    for _ in range(30):
        order = pf.shuffled(ids, history, 3, rng)
        assert sorted(order) == ids
        for cid in order:
            assert cid not in history[-3:]
            history.append(cid)


def test_shuffle_gap_longer_than_the_list_still_plays_everything():
    order = pf.shuffled([1, 2, 3], [3, 2, 1], 10, random.Random(1))
    assert sorted(order) == [1, 2, 3] and order[0] == 3   # the one heard longest ago comes first


def test_begin_remembers_the_position_and_starts_a_new_pass_at_the_end():
    ids = [11, 12, 13]
    run, first = pf.begin(None, ids, shuffle=False, gap=0, remember=True)
    assert first == 11
    pf.note_started(run, 11, ids)
    pf.note_started(run, 12, ids)
    run, again = pf.begin(run, ids, shuffle=False, gap=0, remember=True)
    assert again == 13                                    # goes on after the track that played last
    pf.note_started(run, 13, ids)
    assert pf.advance(run, 13, ids, loop=False, shuffle=False, gap=0) is None and run.done
    run, fresh = pf.begin(run, ids, shuffle=False, gap=0, remember=True)
    assert fresh == 11                                    # after the last track: from the top
    run, top = pf.begin(run, ids, shuffle=False, gap=0, remember=False)
    assert top == 11


def test_loop_wraps_with_a_new_order_and_peek_is_what_plays():
    ids = [1, 2, 3, 4]
    rng = random.Random(3)
    run, first = pf.begin(None, ids, shuffle=True, gap=2, remember=False, rng=rng)
    played = []
    current = first
    for _ in range(12):
        pf.note_started(run, current, ids)
        played.append(current)
        peeked = pf.peek_next(run, current, ids, loop=True, shuffle=True, gap=2, rng=rng)
        nxt = pf.advance(run, current, ids, loop=True, shuffle=True, gap=2, rng=rng)
        assert nxt == peeked is not None
        current = nxt
    for i, cid in enumerate(played):
        assert cid not in played[max(0, i - 2):i]          # never back within the last 2 tracks


def test_advance_when_a_later_track_already_started_moves_nothing():
    ids = [1, 2, 3]
    run, _ = pf.begin(None, ids, shuffle=False, gap=0, remember=False)
    pf.note_started(run, 1, ids)
    pf.note_started(run, 2, ids)                          # a crossfade started 2 before 1 ended
    assert pf.advance(run, 1, ids, loop=False, shuffle=False, gap=0) == 2
    assert run.current() == 2


def test_lead_and_gap_seconds():
    assert pf.lead_seconds(pf.CROSSFADE, 5.0, 60.0) == 5.0
    assert pf.lead_seconds(pf.OVERLAP, 5.0, 4.0) == 2.0       # never more than half a short track
    assert pf.lead_seconds(pf.GAP, 5.0, 60.0) == 0.0
    assert pf.gap_seconds(pf.GAP, 2.5) == 2.5 and pf.gap_seconds(pf.NONE, 2.5) == 0.0


def test_normalize_gains_turn_tracks_down_only():
    result = pf.normalize_gains([(-10.0, 1.0), (-20.0, 1.0), (-14.0, 0.5)])
    assert result.target_lufs == -20.0 and result.limited          # the quiet track sets the level
    assert result.gains_db[0] == -10.0 and result.gains_db[1] == 0.0
    # volume x gain never above 1.0: -14 LUFS at 50 % (-6 dB) reaches -20 with +0 dB of the volume
    assert all(10 ** (g / 20) * v <= 1.0001 for g, (_l, v) in zip(result.gains_db, [(0, 1.0), (0, 1.0), (0, 0.5)]))
    loud = pf.normalize_gains([(-9.0, 1.0), (-12.0, 1.0)])
    assert loud.target_lufs == -16.0 and not loud.limited


# ── Model ─────────────────────────────────────────────────────────────


def test_playlist_fields_round_trip_and_old_shows_load():
    group = Cue(name="Przerwa", media_type=MediaType.GROUP, file_path="", group_mode=GroupMode.SEQUENCE.value)
    group.playlist = True
    group.playlist_transition = "crossfade"
    group.playlist_transition_sec = 4.5
    group.playlist_shuffle, group.playlist_shuffle_gap = True, 5
    group.playlist_loop, group.playlist_remember = True, True
    back = Cue.from_dict(group.to_dict())
    assert (back.playlist_transition, back.playlist_transition_sec, back.playlist_shuffle,
            back.playlist_shuffle_gap, back.playlist_loop, back.playlist_remember) == \
        ("crossfade", 4.5, True, 5, True, True)
    old = Cue.from_dict({"cue_id": 4401, "name": "old", "media_type": "GROUP", "file_path": "", "playlist": True,
                         "playlist_transition": "explode", "playlist_transition_sec": "x"})
    assert old.playlist_transition == "none" and old.playlist_transition_sec == 3.0 and not old.playlist_loop
    plain = Cue(name="a", media_type=MediaType.AUDIO, file_path="a.wav").to_dict()
    assert "playlist_transition" not in plain                      # written for playlists only


def test_resume_action_wakes_with_the_next_track():
    from engine.action_cues import describe_action

    spec = sanitize_action_spec({"kind": "resume", "sleep_sec": 4, "wake_next": True})
    assert spec["wake_next"] is True
    assert sanitize_action_spec({"kind": "resume"})["wake_next"] is False
    assert "brano successivo" in describe_action(spec, [])


# ── Window ────────────────────────────────────────────────────────────


@pytest.fixture()
def window(qt_app, tmp_path, monkeypatch):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    files = []
    for name in ("one.wav", "two.wav", "three.wav", "four.wav"):
        path = tmp_path / name
        path.write_bytes(b"RIFF")
        files.append(str(path))
    monkeypatch.setattr(win, "_ask_playlist", lambda n, answer: answer(True))
    win._on_files_dropped_on_list(files, -1)
    win.fired = []
    win.cue_fired.connect(lambda c: win.fired.append(c.cue_id))
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


def test_new_playlist_remembers_and_the_card_edits_it(window):
    group = window._cues[0]
    assert group.playlist and group.playlist_remember                # new playlists go on at the next GO
    window._cue_list.setCurrentRow(0)
    window._update_inspector(group)
    box = window._inspector.playlist_box
    assert not box.isHidden()
    box.combo_transition.setCurrentIndex(box.combo_transition.findData("gap"))
    box.spin_seconds.setValue(2.0)
    box.chk_loop.setChecked(True)
    assert group.playlist_transition == "gap" and group.playlist_transition_sec == 2.0 and group.playlist_loop
    window._commit_undo_point()
    window._on_undo()
    assert not window._cues[0].playlist_loop


def test_go_follows_the_random_order_and_remembers_the_track(window):
    group = window._cues[0]
    tracks = window._cues[1:]
    group.playlist_shuffle = True
    window._playlist_rng = random.Random(5)
    window._fire_group_cue(0, group)
    order = window._playlist_runs[group.cue_id].order
    assert sorted(order) == sorted(t.cue_id for t in tracks)
    assert window.fired == [order[0]]
    first = next(t for t in tracks if t.cue_id == order[0])
    window.trigger_auto_follow_from(first)                          # its end starts the next in that order
    assert window.fired == order[:2]
    window._fire_group_cue(0, group)                                # stopped, then GO on the playlist again
    assert window.fired[-1] == order[2]                             # goes on after the track that played last


def test_loop_wraps_and_the_last_track_hands_over(window):
    group = window._cues[0]
    tracks = window._cues[1:]
    window._fire_group_cue(0, group)
    for track in tracks[:-1]:
        window.trigger_auto_follow_from(track)
    assert window.fired == [t.cue_id for t in tracks]
    assert not window._hands_over_by_itself(tracks[-1])             # no loop: it stops after the last
    group.playlist_loop = True
    assert window._hands_over_by_itself(tracks[-1])
    window.trigger_auto_follow_from(tracks[-1])
    assert window.fired[-1] == tracks[0].cue_id                     # list order: from the top again


def test_gap_and_lead_answers(window):
    group = window._cues[0]
    tracks = window._cues[1:]
    group.playlist_transition, group.playlist_transition_sec = "gap", 2.5
    window._fire_group_cue(0, group)
    assert window.playlist_gap_after(tracks[0]) == 2.5
    assert window.playlist_gap_after(tracks[-1]) == 0.0             # the playlist ends there
    group.playlist_transition = "crossfade"
    mode, seconds, nxt = window.playlist_lead(tracks[0])
    assert (mode, seconds, nxt.cue_id) == ("crossfade", 2.5, tracks[1].cue_id)
    window._held_auto_go.add(tracks[0].cue_id)                      # "hold" on the next bar: no early start
    assert window.playlist_lead(tracks[0]) is None
    assert window.playlist_skip_to_next(tracks[1]) and window.fired[-1] == tracks[2].cue_id


def test_same_loudness_for_the_whole_playlist(window, monkeypatch):
    group = window._cues[0]
    tracks = window._cues[1:]
    for track, lufs in zip(tracks[:3], (-10.0, -20.0, -14.0), strict=True):
        track.loudness_lufs = lufs
    measured: list[str] = []

    class _Pool:                                                    # the 4th track is measured "in the background"
        def start(self, scanner):
            measured.append(scanner.file_path)
            scanner.signals.finished.emit(scanner.file_path, -12.0, -1.0, -4.0)

    monkeypatch.setattr(window, "_thread_pool", _Pool())
    window._cue_list.setCurrentRow(0)
    window._update_inspector(group)
    assert not window._inspector.playlist_box.btn_normalize.isHidden()
    window._inspector.playlist_box.btn_normalize.click()
    assert measured == [tracks[3].file_path]
    assert [t.auto_gain_db for t in tracks] == [-10.0, 0.0, -6.0, -8.0]   # all at -20 LUFS (the quietest)
    assert all(t.normalize_audio for t in tracks) and "-20.0" in window._status_label.text()
    window._on_undo()
    assert not any(c.normalize_audio for c in window._cues[1:])


def test_several_sounds_on_the_quick_add_zone_become_a_playlist(window, tmp_path):
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    more = []
    for name in ("five.wav", "six.wav"):
        path = tmp_path / name
        path.write_bytes(b"RIFF")
        more.append(QUrl.fromLocalFile(str(path)))
    mime = QMimeData()
    mime.setUrls(more)
    event = QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier)
    window._cue_list.setCurrentRow(0)
    window._drop_zone.dropEvent(event)
    groups = [c for c in window._cues if c.media_type == MediaType.GROUP]
    assert len(groups) == 2 and all(g.playlist for g in groups)     # asked "one playlist?" (answered yes)
    assert len(window._cues) == 8


# ── Player ────────────────────────────────────────────────────────────


class _Audio(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.level = 0.8

    def volume(self) -> float:
        return self.level

    def setVolume(self, value: float) -> None:  # noqa: N802 - Qt API
        self.level = value


class _Deck(QObject):
    def playbackState(self):  # noqa: N802 - Qt API
        return QMediaPlayer.PlaybackState.PlayingState

    def stop(self) -> None:
        pass


def test_overlap_tail_holds_its_level_then_fades(qt_app):
    from engine import player_live

    audio = _Audio()
    tail = player_live._TailFade(_Deck(), audio, 0.6, hold_sec=0.4)
    _pump(0.25)
    assert audio.level == pytest.approx(0.8)                        # still at its level (overlap)
    _pump(0.3)
    assert audio.level < 0.6
    _pump(0.3)
    assert tail not in player_live._TAILS


_GAPLESS = textwrap.dedent(
    """
    import faulthandler, os, sys, time, wave
    sys.path.insert(0, sys.argv[1])
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from engine.player_live import LivePlayer

    tracks = []
    for name in ("a.wav", "b.wav"):
        path = os.path.join(sys.argv[2], name)
        with wave.open(path, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
            w.writeframes(b"\\0\\0\\0\\0" * int(48000 * 1.2))
        tracks.append(path)

    app = QApplication(sys.argv)
    lp = LivePlayer()
    state = {"eof": None, "pre": None, "adopted": False, "gap": None}

    def on_pos(sec):
        if state["pre"] is None and sec > 0.2:
            state["pre"] = lp.preload_next(tracks[1], 0.0)
        if state["eof"] is not None and state["gap"] is None and sec > 0.0 and state["adopted"]:
            state["gap"] = time.monotonic() - state["eof"]
            print("GAP-MS", int(state["gap"] * 1000))
            QTimer.singleShot(200, app.quit)

    def on_eof():
        if state["eof"] is not None:
            return
        state["eof"] = time.monotonic()
        lp.stop()                       # what main._finalize_cue_exit does
        pre = lp._preload
        lp.load(tracks[1])
        state["adopted"] = pre is not None and lp._player is pre[0]
        print("ADOPTED", state["adopted"])
        lp.play()

    lp.signals.position_changed.connect(on_pos)
    lp.signals.eof_reached.connect(on_eof)
    faulthandler.dump_traceback_later(40, exit=True)
    QTimer.singleShot(50, lambda: (lp.load(tracks[0]), lp.play()))
    QTimer.singleShot(15000, app.quit)
    app.exec()
    lp.shutdown()
    print("DONE")
    """
)


def test_next_track_opened_in_advance_is_taken_over(qt_app, tmp_path):
    if not QMediaDevices.audioOutputs():
        pytest.skip("no audio output device")
    script = tmp_path / "gapless.py"
    script.write_text(_GAPLESS, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(script), str(APP_DIR), str(tmp_path)],
                          capture_output=True, text=True, timeout=90)
    out = proc.stdout + proc.stderr
    assert "ADOPTED True" in proc.stdout, out
    assert "GAP-MS" in proc.stdout and "DONE" in proc.stdout, out
    print(next(line for line in proc.stdout.splitlines() if line.startswith("GAP-MS")))  # seen with -s
