"""Action cues (stage 1 / phase B): stop, fade, release loop, level, layer
opacity, operator note and checklist.

Model and show file (round-trip, old shows), the Qt-free target logic, the
player/output primitives and the director-window side. The live wiring in
main.py is checked in the real program (build/etap1/faza_b_check.py).
"""

from __future__ import annotations

import json
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
from engine.action_cues import (
    STOP_CANCEL_START,
    STOP_CLEAR,
    STOP_SILENCE,
    action_duration,
    default_action_spec,
    describe_action,
    expand_cue_ids,
    level_trim_after,
    stop_plan,
    target_layers,
)
from engine.envelope import SectionSequencer, ramp_value
from models.cue import (
    ACTION_CHECKLIST,
    ACTION_FADE,
    ACTION_KINDS,
    ACTION_LEVEL,
    ACTION_NOTE,
    ACTION_OPACITY,
    ACTION_RELEASE,
    ACTION_STOP,
    Cue,
    CueSection,
    CueStatus,
    FollowMode,
    GroupMode,
    MediaType,
    detect_layer_conflicts,
    sanitize_action_spec,
)
from models.project_manager import ProjectManager
from PySide6.QtCore import QCoreApplication
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


def _media(cid: int, mtype: MediaType = MediaType.AUDIO, layer: int = 1, **kw) -> Cue:
    return Cue(name=f"m{cid}", media_type=mtype, file_path=f"/nonexistent/m{cid}.wav",
               cue_id=cid, layer=layer, **kw)


def _action(cid: int, **spec) -> Cue:
    return Cue(name=f"a{cid}", media_type=MediaType.ACTION, file_path="", cue_id=cid,
               action_spec=spec)


# ── Model ────────────────────────────────────────────────────────────

def test_sanitize_fills_every_key_with_safe_defaults():
    spec = sanitize_action_spec(None)
    assert spec["kind"] == ACTION_NOTE  # a damaged cue must never become "fade out everything"
    assert spec["target"] == "all"
    assert set(spec) == {"kind", "target", "layer", "output", "cue_ids", "duration", "mode",
                         "level", "db", "curve", "text", "note_color", "items",
                         "goto_play", "goto_max", "seek_mode", "seek_sec",  # jump / seek (stage 2, 2.2)
                         "countdown_sec",  # countdown (stage 2, 2.5)
                         "sw_mode",  # stopwatch (stage 2, 2.11)
                         "sleep_sec",  # sleep / wake (stage 3, 3.3)
                         "wake_next"}  # wake with the next playlist track (stage 3, 3.3)


def test_sanitize_clamps_damaged_values():
    spec = sanitize_action_spec({
        "kind": "explode", "target": "everywhere", "layer": 9, "output": "z",
        "cue_ids": [3, "x", -1, 3, 7.0], "duration": "nan", "mode": "x",
        "level": 5, "db": -500, "curve": "zigzag", "note_color": "red",
        "items": ["  a ", "", None, "b"],
    })
    assert spec["kind"] == ACTION_NOTE  # unknown kind from a newer version: harmless note
    assert spec["target"] == "all"
    assert spec["layer"] == 3
    assert spec["output"] == "A"
    assert spec["cue_ids"] == [3, 7]
    assert spec["duration"] == 3.0
    assert spec["mode"] == "absolute"
    assert spec["level"] == 1.0
    assert spec["db"] == -60.0
    assert spec["curve"] == "linear"
    assert spec["note_color"] == "#f59e0b"
    assert spec["items"] == ["a", "b"]


def test_action_cue_has_no_file_and_media_cue_no_spec():
    act = Cue(name="x", media_type=MediaType.ACTION, file_path="C:/something.wav")
    assert act.file_path == ""
    assert act.action_spec["kind"] == ACTION_NOTE
    media = Cue(name="y", media_type=MediaType.AUDIO, file_path="a.wav", action_spec={"kind": "stop"})
    assert media.action_spec == {}
    assert media.to_dict()["action_spec"] == {}
    assert MediaType.ACTION.has_file is False
    assert MediaType.GROUP.has_file is False
    assert MediaType.IMAGE.has_file is True


def test_action_cue_validates_without_a_file():
    assert _action(5, kind=ACTION_STOP).validate() == []


def test_to_dict_gives_fresh_lists_for_undo_snapshots():
    cue = _action(6, kind=ACTION_CHECKLIST, items=["a"], cue_ids=[1])
    data = cue.to_dict()
    data["action_spec"]["items"].append("b")
    data["action_spec"]["cue_ids"].append(2)
    assert cue.action_spec["items"] == ["a"]
    assert cue.action_spec["cue_ids"] == [1]


def test_every_kind_round_trips_through_dict():
    for i, kind in enumerate(ACTION_KINDS):
        cue = Cue(name=kind, media_type=MediaType.ACTION, file_path="", cue_id=500 + i,
                  action_spec=default_action_spec(kind), pre_delay=1.5,
                  follow_mode=FollowMode.AUTO_FOLLOW.value)
        back = Cue.from_dict(json.loads(json.dumps(cue.to_dict())))
        assert back.media_type == MediaType.ACTION
        assert back.action_spec == cue.action_spec
        assert back.pre_delay == 1.5
        assert back.follow_mode == FollowMode.AUTO_FOLLOW.value


def test_damaged_action_spec_in_the_file_still_loads():
    data = {"cue_id": 78, "name": "x", "media_type": "ACTION", "file_path": "", "action_spec": "junk"}
    cue = Cue.from_dict(data)
    assert cue.media_type == MediaType.ACTION
    assert cue.action_spec["kind"] == ACTION_NOTE


def test_old_show_without_action_spec_loads_unchanged():
    old = {"cue_id": 77, "name": "music", "media_type": "AUDIO", "file_path": "/x/m.mp3",
           "layer": 2, "volume": 0.8}
    cue = Cue.from_dict(old)
    assert cue.action_spec == {}
    assert cue.layer == 2 and cue.volume == 0.8


def test_show_file_round_trip_with_every_kind(tmp_path):
    audio = tmp_path / "music.wav"
    audio.write_bytes(b"RIFF")
    cues = [Cue(name="music", media_type=MediaType.AUDIO, file_path=str(audio), cue_id=900)]
    for i, kind in enumerate(ACTION_KINDS):
        spec = default_action_spec(kind)
        if kind in (ACTION_FADE, ACTION_LEVEL):
            spec.update(target="cues", cue_ids=[900])
        cues.append(Cue(name=kind, media_type=MediaType.ACTION, file_path="", cue_id=901 + i,
                        action_spec=spec, notes=f"note {i}"))
    pm = ProjectManager(autosave_dir=tmp_path / "autosave")
    show = tmp_path / "show.blindcue"
    pm.save_project(show, cues, 1)
    loaded, idx, _settings = pm.load_project(show)
    assert idx == 1
    assert [c.to_dict() for c in loaded][1:] == [
        {**c.to_dict(), "status": CueStatus.LOADED.value} for c in cues[1:]
    ]
    for cue in loaded[1:]:
        assert cue.file_path == ""  # never resolved to the show folder
        assert cue.status == CueStatus.LOADED


def test_bundled_show_skips_action_cues(tmp_path):
    audio = tmp_path / "music.wav"
    audio.write_bytes(b"RIFF")
    cues = [Cue(name="music", media_type=MediaType.AUDIO, file_path=str(audio), cue_id=950),
            _action(951, kind=ACTION_STOP)]
    pm = ProjectManager(autosave_dir=tmp_path / "autosave")
    show = tmp_path / "bundle.blindcue"
    pm.save_project_bundled(show, cues, 0)
    loaded, _idx, _settings = pm.load_project(show)
    assert loaded[1].media_type == MediaType.ACTION
    assert loaded[1].file_path == ""
    assert pm.uses_media_archive(show, loaded)


def test_action_cues_do_not_count_as_layer_conflicts():
    music = _media(10, layer=1, follow_mode=FollowMode.SIMULTANEOUS.value)
    stop = _action(11, kind=ACTION_STOP)
    stop.follow_mode = FollowMode.SIMULTANEOUS.value
    image = _media(12, MediaType.IMAGE, layer=2)
    assert detect_layer_conflicts([music, stop, image]) == {}


# ── Targets, level math, summaries ───────────────────────────────────

def test_expand_cue_ids_includes_group_children():
    grp = Cue(name="g", media_type=MediaType.GROUP, file_path="", cue_id=20)
    inner = Cue(name="g2", media_type=MediaType.GROUP, file_path="", cue_id=21, parent_id=20)
    kid = _media(22, parent_id=21)
    other = _media(23)
    assert expand_cue_ids([grp, inner, kid, other], [20]) == {20, 21, 22}


def test_target_all_takes_live_and_waiting_layers():
    live = {1: _media(1, MediaType.VIDEO), 2: _media(2)}
    waiting = {3: _media(3, MediaType.IMAGE, layer=3)}
    spec = {"kind": ACTION_FADE, "target": "all"}
    assert target_layers(spec, [], live, waiting) == [1, 2, 3]
    # a level change only touches what sounds now
    assert target_layers({"kind": ACTION_LEVEL}, [], live, waiting) == [1, 2]
    # opacity only touches pictures
    assert target_layers({"kind": ACTION_OPACITY}, [], live, waiting) == [1]


def test_target_layer_respects_output_routing():
    live = {2: _media(2), 5: _media(5)}
    spec = {"kind": ACTION_STOP, "target": "layer", "layer": 2, "output": "B"}
    assert target_layers(spec, [], live, dual_active=True) == [5]
    # with one projector, output B is played on output A
    assert target_layers(spec, [], live, dual_active=False) == [2]
    assert target_layers({**spec, "layer": 3}, [], live, dual_active=True) == []


def test_target_cues_follows_group_children():
    grp = Cue(name="g", media_type=MediaType.GROUP, file_path="", cue_id=30)
    kid = _media(31, parent_id=30)
    stranger = _media(32, layer=2)
    live = {1: kid, 2: stranger}
    spec = {"kind": ACTION_FADE, "target": "cues", "cue_ids": [30]}
    assert target_layers(spec, [grp, kid, stranger], live) == [1]


def test_stop_plan_touches_only_the_chosen_cue_on_a_shared_layer():
    music = _media(33)        # playing on L1, not chosen
    late = _media(34)         # waiting on L1 in its Pre-Delay, chosen
    other = _media(35, layer=2)
    cues = [music, late, other]
    spec = {"kind": ACTION_FADE, "target": "cues", "cue_ids": [34]}
    # the chosen cue only waits: cancel its start, the music plays on
    assert stop_plan(spec, cues, {1: music, 2: other}, {1: late}) == {1: STOP_CANCEL_START}
    # the chosen cue plays and a non-target waits to replace it: silence, keep the start
    assert stop_plan({**spec, "cue_ids": [33]}, cues, {1: music}, {1: late}) == {1: STOP_SILENCE}
    # both chosen, or nothing waiting: clear
    assert stop_plan({**spec, "cue_ids": [33, 34]}, cues, {1: music}, {1: late}) == {1: STOP_CLEAR}
    assert stop_plan({**spec, "cue_ids": [35]}, cues, {1: music, 2: other}, {}) == {2: STOP_CLEAR}
    # everything / one layer always clear what is there
    assert stop_plan({"kind": ACTION_STOP, "target": "all"}, cues, {1: music}, {1: late}) == \
        {1: STOP_CLEAR}


def test_notes_have_no_targets():
    live = {1: _media(1)}
    assert target_layers({"kind": ACTION_NOTE}, [], live) == []
    assert target_layers({"kind": ACTION_CHECKLIST}, [], live) == []


def test_level_trim_absolute_and_relative():
    absolute = {"kind": ACTION_LEVEL, "mode": "absolute", "level": 0.4}
    assert level_trim_after(absolute, 1.0, 0.8) == pytest.approx(0.5)
    relative = {"kind": ACTION_LEVEL, "mode": "relative", "db": -6.0}
    assert level_trim_after(relative, 1.0, 0.8) == pytest.approx(0.501, abs=1e-3)
    # two -6 dB changes make -12 dB
    assert level_trim_after(relative, 0.501, 0.8) == pytest.approx(0.251, abs=1e-3)
    # never above +12 dB
    assert level_trim_after({**relative, "db": 20.0}, 3.0, 0.8) == 4.0
    # a silent cue cannot be scaled up by an absolute change
    assert level_trim_after(absolute, 0.7, 0.0) == 0.7


def test_action_duration_only_for_timed_kinds():
    assert action_duration({"kind": ACTION_FADE, "duration": 3}) == 3.0
    assert action_duration({"kind": ACTION_LEVEL, "duration": 2}) == 2.0
    assert action_duration({"kind": ACTION_STOP, "duration": 3}) == 0.0
    assert action_duration({"kind": ACTION_NOTE, "duration": 3}) == 0.0


def test_describe_action_texts():
    cues = [_media(40), _media(41)]
    cues[1].q_label = "Q-5"
    assert describe_action({"kind": ACTION_FADE, "target": "layer", "layer": 2, "duration": 3}) == \
        "Dissolvi in 3.0 s: Layer 2"
    assert describe_action({"kind": ACTION_STOP, "target": "cues", "cue_ids": [41, 99]}, cues) == \
        "Stop: cue #2 Q-5, ?"
    assert describe_action({"kind": ACTION_LEVEL, "mode": "relative", "db": -10, "duration": 2}) == \
        "Livello -10.0 dB in 2.0 s: tutto in onda"
    assert describe_action({"kind": ACTION_NOTE, "text": "Aspetta Anna\nseconda riga"}) == \
        "Nota: Aspetta Anna"
    assert describe_action({"kind": ACTION_CHECKLIST, "items": ["a", "b"]}) == "Checklist: 2 voci"
    assert describe_action({"kind": ACTION_RELEASE}) == "Rilascia loop: tutto in onda"


def test_ramp_value_shapes_and_endpoints():
    for curve in ("linear", "log", "scurve"):
        assert ramp_value(1.0, 0.0, 0.0, curve) == pytest.approx(1.0)
        assert ramp_value(1.0, 0.0, 1.0, curve) == pytest.approx(0.0)
        assert ramp_value(0.2, 0.8, 1.0, curve) == pytest.approx(0.8)
        values = [ramp_value(1.0, 0.25, p / 10, curve) for p in range(11)]
        assert values == sorted(values, reverse=True)
    assert ramp_value(0.0, 1.0, 0.5, "linear") == pytest.approx(0.5)


def test_sequencer_release_lets_the_vamp_finish_and_move_on():
    seq = SectionSequencer()
    seq.configure([CueSection("A", 0.0, 2.0, loops=0), CueSection("B", 2.0, 4.0)], 0.0, 4.0)
    assert seq.advance_at_boundary() == ("JUMP", 0, 0.0)  # vamp repeats
    assert seq.release_current_loop()
    assert seq.advance_at_boundary() == ("CONTINUE", 1, None)  # then moves on
    assert not seq.release_current_loop()  # B plays once: nothing to release
    assert seq.advance_at_boundary()[0] == "EOF"


# ── Player and output primitives ─────────────────────────────────────

def test_ramp_level_follows_the_clock(qt_app):
    from engine.player_live import LivePlayer

    lp = LivePlayer()
    _, audio = lp._deck_pair()
    lp.ramp_level(1.0, 0.0)
    assert audio.volume() == pytest.approx(1.0)
    t0 = time.monotonic()
    lp.ramp_level(0.0, 1.0, "linear")
    mid = None
    while lp._level_timer is not None and time.monotonic() - t0 < 3.0:
        QCoreApplication.processEvents()
        if mid is None and time.monotonic() - t0 >= 0.5:
            mid = audio.volume()
        time.sleep(0.002)
    took = time.monotonic() - t0
    assert 0.95 <= took <= 1.4, f"ramp took {took:.3f} s"
    assert lp.level_trim() == 0.0
    assert audio.volume() == pytest.approx(0.0, abs=1e-6)
    assert mid is not None and 0.35 <= mid <= 0.65, f"level at 0.5 s: {mid}"
    lp.stop()
    assert lp.level_trim() == 1.0  # a stop forgets the level change
    lp.deleteLater()


def test_ramp_level_yields_to_a_stop_fade(qt_app):
    from engine.player_live import LivePlayer

    lp = LivePlayer()
    _, audio = lp._deck_pair()
    lp.set_volume(50)
    assert audio.volume() == pytest.approx(0.5)
    lp.fade_out(10.0)  # a stop fade owns the volume from now on
    lp.ramp_level(2.0, 0.0)
    assert audio.volume() <= 0.51  # not pushed back up to 100 %
    lp.stop()
    lp.deleteLater()


def test_pause_holds_a_level_ramp(qt_app):
    """Pause All pauses the players: a running level change waits with them (1.15)."""
    from engine.player_live import LivePlayer

    lp = LivePlayer()
    lp.ramp_level(1.0, 0.0)
    lp.ramp_level(0.0, 0.6, "linear")
    _pump(0.2)
    lp.pause()
    held = lp.level_trim()
    _pump(0.8)                       # longer than the whole ramp
    assert lp.level_trim() == pytest.approx(held, abs=1e-6)
    assert 0.4 < held < 0.9
    lp.play()
    _pump(0.1)
    assert 0.0 < lp.level_trim() < held   # goes on from where it was, not finished
    _pump(0.6)
    assert lp.level_trim() == pytest.approx(0.0, abs=1e-6)
    lp.stop()
    lp.deleteLater()


def test_pause_holds_a_layer_opacity_fade(qt_app):
    from ui.output_window import OutputWindow

    out = OutputWindow()
    try:
        out.fade_layer_master(2, 0.0, 0.6, "linear")
        _pump(0.2)
        out.set_master_fades_paused(True)
        held = out.layer_master_opacity(2)
        _pump(0.8)
        assert out.layer_master_opacity(2) == pytest.approx(held, abs=1e-6)
        assert 0.4 < held < 0.9
        out.fade_layer_master(3, 0.5, 0.2)          # a fade started during the pause runs
        _pump(0.4)
        assert out.layer_master_opacity(3) == pytest.approx(0.5, abs=1e-3)
        out.set_master_fades_paused(False)
        _pump(0.1)
        assert 0.0 < out.layer_master_opacity(2) < held
        _pump(0.6)
        assert out.layer_master_opacity(2) == pytest.approx(0.0, abs=1e-6)
    finally:
        out.force_close()
        out.deleteLater()


def test_release_loop_on_a_plain_cue(qt_app):
    from engine.player_live import LivePlayer

    lp = LivePlayer()
    assert lp.release_loop() is False
    lp.set_loop(True, 0)
    lp._duration_sec = 2.0  # as reported by the backend for a 2 s file
    assert lp.release_loop() is True
    assert lp._is_looping is False
    # Qt's own whole-file loop ignores the new count: our OUT point ends the pass
    assert lp._end_ms == 1960
    lp.deleteLater()


def test_release_loop_keeps_looping_while_the_length_is_unknown(qt_app):
    from engine.player_live import LivePlayer

    lp = LivePlayer()
    lp.set_loop(True, 0)
    assert lp.release_loop() is False  # no length yet: cannot tell where the pass ends
    assert lp._is_looping is True
    lp.deleteLater()


def test_release_loop_never_starts_the_fade_out_in_the_past(qt_app):
    from engine.player_live import LivePlayer

    lp = LivePlayer()
    lp.configure_automation(fade_out=5.0)
    lp.set_loop(True, 0)
    lp._duration_sec = 2.0
    assert lp.release_loop() is True
    assert lp._fade_out_sec <= 1.96  # at most what is left of this pass
    lp.deleteLater()


def test_layer_opacity_fades_and_resets(qt_app):
    from ui.output_window import OutputWindow

    out = OutputWindow()
    try:
        out.fade_layer_master(2, 0.3, 0.0)
        assert out.layer_master_opacity(2) == pytest.approx(0.3)
        assert out.layer_master_opacity(1) == pytest.approx(1.0)
        out.fade_layer_master(2, 1.0, 0.3, "scurve")
        _pump(0.5)
        assert out.layer_master_opacity(2) == pytest.approx(1.0)
        out.fade_layer_master(3, 0.0, 0.0)
        out.clear_layer(3)
        assert out.layer_master_opacity(3) == pytest.approx(1.0)
        out.fade_layer_master(1, 0.2, 0.0)
        out.panic_blackout()
        assert out.layer_master_opacity(1) == pytest.approx(1.0)
    finally:
        out.force_close()
        out.deleteLater()


# ── Director window ──────────────────────────────────────────────────

@pytest.fixture()
def window(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    fired: list[Cue] = []
    win.cue_fired.connect(fired.append)
    win._fired = fired
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


def test_go_on_an_action_keeps_the_layer_live(window):
    music = _media(60, layer=1)
    music.status = CueStatus.LIVE
    act = _action(61, kind=ACTION_FADE)
    act.layer = 1  # the action's own (unused) layer equals the music's
    window._cues = [music, act]
    window._refresh_cue_list()
    window._fire_cue_chain(1)
    assert window._fired == [act]
    assert music.status == CueStatus.LIVE  # not demoted by the action
    assert act.status != CueStatus.LIVE


def test_auto_go_skips_a_cue_started_by_hand(window):
    """GO given by hand during an Auto-GO wait must not start that cue twice (1.15)."""
    act = _action(84, kind=ACTION_NOTE)
    act.follow_mode = FollowMode.AUTO_FOLLOW.value
    nxt = _media(85, layer=2)
    window._cues = [act, nxt]
    window._refresh_cue_list()
    window._fire_cue_chain(0)            # the action waits for its Auto-GO
    window._fire_cue_chain(1)            # the operator starts the next cue meanwhile
    started = list(window._fired)
    window.trigger_auto_follow_from(act)
    assert window._fired == started      # no second start
    window._fire_cue_chain(0)            # another run: the Auto-GO works again
    window.trigger_auto_follow_from(act)
    assert window._fired[-1] is nxt


def test_released_loop_scene_ends_after_its_pass(window):
    from engine.show_engine import ShowEngine

    grp = Cue(name="g", media_type=MediaType.GROUP, file_path="", cue_id=90)
    grp.group_mode = GroupMode.LOOP.value
    a, b, after = _media(91), _media(92), _media(93)
    a.parent_id = b.parent_id = 90
    window._cues = [grp, a, b, after]
    window._refresh_cue_list()
    assert ShowEngine.auto_follow_target(window._cues, b) == 1          # wraps to a
    assert window.release_loop_scene_of(a) is True
    assert window.release_loop_scene_of(a) is False                     # once is enough
    assert window.release_loop_scene_of(after) is False                 # not in a loop scene
    assert ShowEngine.auto_follow_target(window._cues, a, window._released_groups) == 2
    assert ShowEngine.auto_follow_target(window._cues, b, window._released_groups) == -1
    window._fire_cue_chain(0)                                           # the scene runs again
    assert 90 not in window._released_groups

    # released while its last child plays: the GO goes past the scene, not back to a
    window._fire_cue_chain(2)                                           # b fires: GO wraps to a
    assert window._go_target_index() == 1
    assert window.release_loop_scene_of(b) is True
    assert window._go_target_index() == 3
    window._fire_cue_chain(1)                                           # a by hand: loops again
    assert 90 not in window._released_groups
    assert window.release_loop_scene_of(a) is True
    window._fire_cue_chain(2)                                           # last child after a release
    assert window._go_target_index() == 3                               # no wrap to a


def test_auto_go_never_pulls_the_go_pointer_back(window):
    """After the operator moved past a released Loop Scena, its last child's
    Auto-GO must not send the GO back to the action that released it."""
    grp = Cue(name="g", media_type=MediaType.GROUP, file_path="", cue_id=96)
    grp.group_mode = GroupMode.LOOP.value
    a, b = _media(97), _media(98)
    a.parent_id = b.parent_id = 96
    rel = _action(99, kind=ACTION_RELEASE)
    after = _media(100)
    window._cues = [grp, a, b, rel, after]
    window._refresh_cue_list()
    window._released_groups.add(96)
    window._cue_list.setCurrentRow(4)          # the operator's GO is on "after"
    window.trigger_auto_follow_from(a)          # a ends: b starts by itself
    assert window._go_target_index() == 4


def test_go_label_waits_when_the_target_is_the_exclusive_cue(window, tmp_path):
    excl = _media(95)
    excl.file_path = str(tmp_path / "x.wav")
    Path(excl.file_path).write_bytes(b"x")   # the label checks the file first
    excl.exclusive = True
    window._cues = [excl]
    window._refresh_cue_list()
    window._cue_list.setCurrentRow(0)
    excl.status = CueStatus.LIVE
    window._update_go_button_text()
    assert window._go_label()[0].startswith("⏳ GO in attesa")


def test_group_studio_keeps_action_cues_as_actions(window):
    """The group timeline studio shows actions as ACT and writes back only their start."""
    from ui.group_timeline_editor import GroupTimelineStudioDialog

    grp = Cue(name="g", media_type=MediaType.GROUP, file_path="", cue_id=86)
    act = _action(87, kind=ACTION_FADE, duration=2.0)
    act.parent_id = 86
    act.volume, act.in_point, act.layer = 0.7, 0.0, 1
    dlg = GroupTimelineStudioDialog(grp, [act], window)
    try:
        assert dlg.list_items.item(0).text().startswith("[ACT]")
        dlg._clips[0].start_sec = 1.5
        dlg._clips[0].volume = 0.2
        dlg._clips[0].layer = 3
        dlg._clips[0].in_point = 4.0
        dlg._on_save_and_apply()
        assert act.pre_delay == 1.5
        assert (act.volume, act.layer, act.in_point) == (0.7, 1, 0.0)
    finally:
        dlg.deleteLater()


def test_action_in_a_group_does_not_go_live(window):
    grp = Cue(name="g", media_type=MediaType.GROUP, file_path="", cue_id=62)
    act = _action(63, kind=ACTION_STOP)
    act.parent_id = 62
    window._cues = [grp, act]
    window._refresh_cue_list()
    window._fire_cue_chain(0)
    assert window._fired == [act]
    assert act.status != CueStatus.LIVE


def test_add_action_cue_appends_and_opens_the_action_tab(window):
    from ui.inspector_panel import _ACTION_TAB

    window._on_add_action_cue(ACTION_LEVEL)
    cue = window._cues[-1]
    assert cue.media_type == MediaType.ACTION
    assert cue.action_spec["kind"] == ACTION_LEVEL
    assert window._inspector.tab_widget.isTabVisible(_ACTION_TAB)
    assert window._inspector.tab_widget.currentIndex() == _ACTION_TAB
    assert not window._inspector.card_layer.isVisibleTo(window._inspector)


def test_inspector_edits_reach_the_cue(window):
    window._cues = [_media(70), _media(71)]
    window._refresh_cue_list()
    window._on_add_action_cue(ACTION_FADE)
    cue = window._cues[-1]
    editor = window._inspector.action_editor
    editor.combo_target.setCurrentIndex(editor.combo_target.findData("cues"))
    item = editor.list_cues.item(1)
    assert item.data(256) == 71  # Qt.UserRole
    from PySide6.QtCore import Qt
    item.setCheckState(Qt.CheckState.Checked)
    editor.spin_duration.setValue(4.5)
    assert cue.action_spec["target"] == "cues"
    assert cue.action_spec["cue_ids"] == [71]
    assert cue.action_spec["duration"] == 4.5


def test_space_and_delete_stay_in_the_target_list(window):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    window._cues = [_media(72), _media(73)]
    window._refresh_cue_list()
    window._on_add_action_cue(ACTION_FADE)
    editor = window._inspector.action_editor
    editor.combo_target.setCurrentIndex(editor.combo_target.findData("cues"))
    lst = editor.list_cues
    lst.setCurrentRow(0)
    for key in (Qt.Key.Key_Space, Qt.Key.Key_Delete):
        override = QKeyEvent(QEvent.Type.ShortcutOverride, key, Qt.KeyboardModifier.NoModifier)
        override.ignore()
        QApplication.sendEvent(lst, override)
        assert override.isAccepted(), "the window shortcut (GO / delete cue) would fire"
    QApplication.sendEvent(lst, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space,
                                          Qt.KeyboardModifier.NoModifier, " "))
    assert lst.item(0).checkState() == Qt.CheckState.Checked
    QApplication.sendEvent(lst, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete,
                                          Qt.KeyboardModifier.NoModifier))
    assert len(window._cues) == 3
    assert window._cues[-1].action_spec["cue_ids"] == [72]


def test_default_name_follows_the_kind(window):
    window._on_add_action_cue(ACTION_FADE)
    cue = window._cues[-1]
    assert cue.name == "Dissolvi e ferma"
    editor = window._inspector.action_editor
    editor.combo_kind.setCurrentIndex(editor.combo_kind.findData(ACTION_LEVEL))
    assert cue.name == "Cambio livello"
    window._inspector.edit_cue_name.setText("Musica sotto il dialogo")
    window._apply_inspector_to_cue()
    editor.combo_kind.setCurrentIndex(editor.combo_kind.findData(ACTION_OPACITY))
    assert cue.name == "Musica sotto il dialogo"  # a name of your own is kept
    assert "L1" not in str(cue)


def test_mark_layer_stopped_demotes_only_that_layer(window):
    a = _media(80, layer=1)
    b = _media(81, layer=2)
    a.status = b.status = CueStatus.LIVE
    window._cues = [a, b]
    window.mark_layer_stopped(2)
    assert a.status == CueStatus.LIVE
    assert b.status == CueStatus.LOADED


def test_note_shows_and_goes_away_on_the_next_go(window):
    note = _action(90, kind=ACTION_NOTE, text="Aspetta Anna", note_color="#ef4444")
    window._cues = [note, _media(91)]
    window._refresh_cue_list()
    window.show_operator_note(note)
    banner = window._note_banner
    assert banner.isVisibleTo(window)
    assert banner.cue_id() == 90
    assert "Aspetta Anna" in banner.lbl_text.text()
    window._dismiss_note_on_go()
    assert not banner.isVisibleTo(window)


def test_every_hand_given_go_moves_past_the_note(window):
    note = _action(93, kind=ACTION_NOTE, text="x")
    window._cues = [note, _media(94)]
    window._refresh_cue_list()
    banner = window._note_banner
    window.show_operator_note(note)
    window.trigger_auto_follow_from(note)  # an Auto-GO keeps the note up
    assert banner.is_shown()
    window._on_live_row_forced(1)  # right-click "start now" (also remote GO paths)
    assert not banner.is_shown()


def test_a_note_covers_an_open_checklist_which_comes_back(window):
    check = _action(96, kind=ACTION_CHECKLIST, items=["mic"])
    note = _action(97, kind=ACTION_NOTE, text="Aspetta")
    window._cues = [check, note]
    window._refresh_cue_list()
    banner = window._note_banner
    window.show_operator_note(check)
    window.show_operator_note(note)
    assert banner.cue_id() == 97
    window._dismiss_note_on_go()  # the note goes, the checklist returns
    assert banner.cue_id() == 96 and banner.is_checklist()


def test_note_text_is_plain_text(window):
    from PySide6.QtCore import Qt

    note = _action(98, kind=ACTION_CHECKLIST, text="<b>x</b>", items=["Luci & suono"])
    window._cues = [note]
    window.show_operator_note(note)
    banner = window._note_banner
    assert banner.lbl_text.textFormat() == Qt.TextFormat.PlainText
    assert banner._boxes[0].text() == "Luci && suono"  # shown as "Luci & suono", no shortcut


def test_deleting_a_waiting_action_cancels_it_and_leaves_the_layers(window):
    act = _action(99, kind=ACTION_FADE)
    music = _media(100, layer=1)
    music.status = CueStatus.LIVE
    window._cues = [act, music]
    window._refresh_cue_list()
    window._live_phase_tags[99] = "PRE -2.0s"
    cancelled, cleared = [], []
    window.action_cancel_requested.connect(cancelled.append)
    window.layer_clear_requested.connect(cleared.append)
    window._cue_list.setCurrentRow(0)
    window._on_delete_cue()
    assert cancelled == [99]
    assert cleared == []
    assert music.status == CueStatus.LIVE


def test_an_old_checklist_stays_until_closed_and_never_returns_by_itself(window):
    from PySide6.QtCore import Qt

    check = _action(92, kind=ACTION_CHECKLIST, items=["mic", "projector"])
    window._cues = [check]
    window._refresh_cue_list()
    window.show_operator_note(check)
    banner = window._note_banner
    window._dismiss_note_on_go()
    assert banner.isVisibleTo(window)  # a GO does not hide a checklist
    boxes = banner._boxes
    assert [b.text() for b in boxes] == ["mic", "projector"]
    assert all(b.focusPolicy() == Qt.FocusPolicy.NoFocus for b in boxes)  # Space stays GO
    boxes[0].setChecked(True)
    banner.dismiss()
    assert not banner.isVisibleTo(window)
    window.set_live_mode(True)  # the checklist was taken out (2026-11-24): the show never brings it back
    assert not banner.isVisibleTo(window)
    window.set_live_mode(False)


def test_summaries_translate_to_polish_and_english():
    import i18n

    try:
        i18n.set_language("pl")
        assert i18n.tr(describe_action({"kind": ACTION_LEVEL, "mode": "relative", "db": -10,
                                        "duration": 2})) == "Poziom -10.0 dB w 2.0 s: wszystko, co gra"
        assert i18n.tr(describe_action({"kind": ACTION_FADE, "target": "layer", "layer": 2,
                                        "duration": 3})) == "Wygaś w 3.0 s: Warstwa 2"
        i18n.set_language("en")
        assert i18n.tr(describe_action({"kind": ACTION_FADE, "duration": 3})) == \
            "Fade out in 3.0 s: everything playing"
        assert i18n.tr(describe_action({"kind": ACTION_STOP})) == "Stop: everything playing"
    finally:
        i18n.set_language("it")


def test_action_done_reports_nothing_to_do(window):
    act = _action(95, kind=ACTION_FADE)
    window._cues = [act]
    window.action_cue_done(act, [])
    assert "niente da fare" in window._status_label.text() or "nic" in window._status_label.text()
