"""Own mixer engine (3.2 / 3.9) without Qt: settings, DSP, decoded sources, voices and buses."""

from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import numpy as np
import pytest
from engine import audio_mix
from engine.audio_mix import MixSettings, Send, spec_for
from engine.audio_mixer_core import DECLICK, MixerCore, Route
from engine.audio_mixer_dsp import (
    BLOCK,
    RATE,
    Equalizer,
    Limiter,
    Reverb,
    eq_response,
    pan_gains,
)
from engine.audio_mixer_source import PcmSource, ffmpeg_command, source_key

# ── fake decoder: frame f holds (f % 20000 + 1, -(f % 20000 + 1)) ───────────


def _pattern(start: int, n: int) -> np.ndarray:
    idx = (np.arange(start, start + n) % 20000 + 1).astype(np.int16)
    return np.stack((idx, -idx), axis=1)


class _FakeDecoder:
    def __init__(self, total: int, step: int | None = None):
        self.total = total
        self.step = step      # None: everything at once; else frames per pump()
        self.runs: list[tuple] = []

    def __call__(self, source, segment, start_sec):
        self.runs.append((segment, start_sec))
        if self.step is None:
            self._fill(source, segment, self.total - segment.start)
        return self

    def _fill(self, source, segment, n):
        n = max(0, min(n, self.total - segment.end_frame()))
        if n:
            segment.write(_pattern(segment.end_frame(), n))
        if segment.full():
            segment.done = True          # a head stops at its limit (not the end of the file)
        elif segment.end_frame() >= self.total:
            segment.eof = True
            segment.done = True
            source.note_end(segment)

    def pump(self):
        for segment, _ in self.runs:
            src = self._src
            if not segment.done:
                self._fill(src, segment, self.step)

    def cancel(self):
        pass


def _source(total=RATE * 2, step=None):
    dec = _FakeDecoder(total, step)
    src = PcmSource("x.wav", decoder=dec)
    dec._src = src
    return src, dec


class _Cue:
    def __init__(self, mix=None, out="stage", media="AUDIO"):
        self.audio_mix = mix or {}
        self.audio_output = out
        self.media_type = media


# ── settings ─────────────────────────────────────────────────────────────

def test_default_settings_store_nothing_and_need_no_mixer():
    assert audio_mix.sanitize({}) == {}
    assert audio_mix.sanitize({"pan": 0, "level_db": 0, "eq": {"low": 0}}) == {}
    assert audio_mix.cue_extras(_Cue()) == []
    assert MixSettings().qt_gain() == 1.0


def test_settings_are_validated():
    mix = MixSettings.from_dict({
        "level_db": 40, "pan": -3, "reverb": 2, "room": "cave",
        "sends": [{"out": "hall", "db": "-inf"}, {"out": "hall", "db": 3}, {"out": "stage", "db": 1},
                  {"out": "mute", "db": 0}, {"out": "foldback", "db": -99}, "junk"],
        "eq": {"low": 30, "mid": "x", "high": -4.44},
    }, main_output="stage")
    assert mix.level_db == audio_mix.LEVEL_MAX_DB
    assert mix.pan == -1.0 and mix.reverb == 1.0 and mix.room == "medium"
    # one row per output, never the main output again, never "mute"; below -60 dB is -INF
    assert mix.sends == [Send("hall", None), Send("foldback", None)]
    assert mix.eq == {"low": 12.0, "mid": 0.0, "high": -4.4}


def test_extras_decide_the_mixer():
    assert audio_mix.cue_extras(_Cue({"pan": 0.5})) == ["pan"]
    assert audio_mix.cue_extras(_Cue({"level_db": -6})) == []            # Qt can play it quieter
    assert audio_mix.cue_extras(_Cue({"level_db": 3})) == ["boost"]
    assert audio_mix.cue_extras(_Cue({"sends": [{"out": "foldback", "db": None}]})) == []  # -INF row: nothing
    assert audio_mix.cue_extras(_Cue({"sends": [{"out": "foldback", "db": -6}]})) == ["outputs"]
    assert audio_mix.cue_extras(_Cue({"eq": {"low": 3}})) == ["eq"]
    assert audio_mix.cue_extras(_Cue({"reverb": 0.3})) == ["reverb"]
    assert audio_mix.cue_extras(_Cue({"pan": 0.5}, media="VIDEO")) == []
    # a positive trim of the cue's output on this computer needs the mixer too
    assert audio_mix.cue_extras(_Cue(), out_trim_db=lambda key: 3.0) == ["boost"]
    assert audio_mix.cue_extras(_Cue(out="mute"), out_trim_db=lambda key: 3.0) == []


def test_qt_gain_and_shift_all_rows():
    mix = MixSettings.from_dict({"level_db": -6, "sends": [{"out": "hall", "db": None}, {"out": "foldback", "db": 10}]})
    assert mix.qt_gain() == pytest.approx(10 ** (-6 / 20))
    moved = mix.shifted(5)
    assert moved.level_db == -1.0
    assert moved.sends[0].db is None            # -INF stays -INF
    assert moved.sends[1].db == audio_mix.LEVEL_MAX_DB
    assert MixSettings.from_dict({"level_db": None}).qt_gain() == 0.0


def test_spec_rows():
    spec = spec_for(_Cue({"level_db": -6, "pan": 0.4, "sends": [{"out": "foldback", "db": 0},
                                                                 {"out": "hall", "db": None}]}))
    assert spec.pan == 0.4
    assert [k for k, _ in spec.sends] == ["stage", "foldback"]
    assert spec.sends[0][1] == pytest.approx(10 ** (-6 / 20))
    muted_main = spec_for(_Cue({"sends": [{"out": "foldback", "db": 0}]}, out="mute"))
    assert [k for k, _ in muted_main.sends] == ["foldback"]


def test_cue_keeps_mix_settings_and_old_shows_load_unchanged():
    from models.cue import Cue, MediaType

    old = Cue(name="a", media_type=MediaType.AUDIO, file_path="a.wav")
    data = old.to_dict()
    assert data["audio_mix"] == {}
    data.pop("audio_mix")
    assert Cue.from_dict(data).audio_mix == {}
    cue = Cue(name="b", media_type=MediaType.AUDIO, file_path="b.wav",
              audio_mix={"pan": -0.5, "sends": [{"out": "foldback", "db": -3}]})
    again = Cue.from_dict(cue.to_dict())
    assert again.audio_mix == {"pan": -0.5, "sends": [{"out": "foldback", "db": -3.0}]}


# ── DSP ──────────────────────────────────────────────────────────────────

def test_pan_law():
    assert pan_gains(0.0) == pytest.approx((1.0, 1.0))
    assert pan_gains(-1.0) == pytest.approx((1.0, 0.0), abs=1e-9)
    assert pan_gains(1.0) == pytest.approx((0.0, 1.0), abs=1e-9)
    left, right = pan_gains(0.5)
    assert right == 1.0 and 0.3 < left < 0.8


def _tone(freq, n, amp=0.25):
    t = np.arange(n) / RATE
    s = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    return np.stack((s, s), axis=1)


def _run_blocks(proc, x):
    out = [proc(x[i:i + BLOCK]) for i in range(0, len(x), BLOCK)]
    return np.concatenate(out, axis=0)


def test_equalizer_matches_its_design_and_is_transparent_when_flat():
    eq = Equalizer()
    x = _tone(1000, BLOCK * 8)
    assert np.array_equal(_run_blocks(eq.process, x), x)  # flat: untouched
    eq.set_gains((6.0, 0.0, -6.0))
    for freq, want_db in ((60.0, 6.0), (1000.0, None), (12000.0, -6.0)):
        y = _run_blocks(eq.process, _tone(freq, BLOCK * 12))
        got = 20 * np.log10(np.sqrt(np.mean(y[-BLOCK * 4:, 0] ** 2)) / (0.25 / np.sqrt(2)))
        design = 20 * np.log10(abs(eq_response((6.0, 0.0, -6.0), np.array([freq]))[0]))
        assert got == pytest.approx(design, abs=0.3)
        if want_db is not None:
            assert got == pytest.approx(want_db, abs=0.8)


def test_reverb_tail_rings_and_dies():
    rv = Reverb(0.8)
    x = np.zeros((BLOCK, 2), dtype=np.float32)
    x[0] = 0.5
    first = rv.process(x)
    assert np.max(np.abs(first)) > 0
    assert rv.ringing()
    silent = np.zeros_like(x)
    energies = [float(np.sum(rv.process(silent) ** 2)) for _ in range(rv.partitions + 3)]
    assert energies[5] < energies[0]          # decays
    assert energies[-1] == pytest.approx(0.0, abs=1e-12)
    assert not rv.ringing()


def test_limiter_never_passes_the_threshold_and_leaves_quiet_sound_alone():
    lim = Limiter(threshold_db=-1.0)
    quiet = _tone(440, BLOCK * 4, amp=0.3)
    out = _run_blocks(lim.process, quiet)
    assert np.allclose(out[32:], quiet[:-32], atol=1e-6)  # only delayed by one 32-frame step
    loud = _tone(440, BLOCK * 8, amp=3.0)
    out = _run_blocks(lim.process, loud)
    assert float(np.max(np.abs(out))) <= 10 ** (-1 / 20) + 1e-4


# ── sources ──────────────────────────────────────────────────────────────

def test_source_reads_seeks_and_ends():
    src, dec = _source(total=RATE)
    buf = np.zeros((1000, 2), dtype=np.int16)
    got, state = src.read(0, buf)
    assert (got, state) == (1000, "ok") and buf[0, 0] == 1 and buf[999, 1] == -1000
    got, state = src.read(RATE - 400, buf)
    assert (got, state) == (400, "end")
    assert len(dec.runs) == 1          # the seek stayed inside what was decoded
    assert src.read(RATE, buf) == (0, "end")
    assert src.duration_frames() == RATE


def test_source_waits_for_a_slow_decoder_and_starts_new_segments_far_away():
    src, dec = _source(total=RATE * 30, step=500)
    buf = np.zeros((1000, 2), dtype=np.int16)
    assert src.read(0, buf) == (0, "wait")
    dec.pump()
    assert src.read(0, buf) == (500, "wait")
    dec.pump()
    assert src.read(0, buf) == (1000, "ok")
    src.read(RATE * 20, buf)           # far ahead: a second FFmpeg run from there
    assert len(dec.runs) == 2 and dec.runs[1][1] == pytest.approx(20.0)


def test_prefetched_head_plays_and_the_whole_file_takes_over_without_a_seam():
    src, dec = _source(total=RATE * 10)
    head = src.prefetch(RATE, 0.5)                 # the cue starts at 1 s: half a second decoded ahead
    assert head.length == RATE // 2 and head.done and not head.eof
    buf = np.zeros((1000, 2), dtype=np.int16)
    assert src.read(RATE, buf) == (1000, "ok") and len(dec.runs) == 1
    src.ensure(RATE, whole=True)                   # GO: the whole file from the head's start
    assert len(dec.runs) == 2 and dec.runs[1][0].start == RATE and dec.runs[1][0].limit is None
    across = RATE + RATE // 2 - 300                # a block over the end of the head
    assert src.read(across, buf) == (1000, "ok")
    assert np.array_equal(buf, _pattern(across, 1000))
    src.prune(keep_frames=[across])                # the whole segment stays where a voice stands
    assert len(src._segments) == 2
    assert src.prefetch(RATE, 0.5) is None         # already there: no second FFmpeg run


def test_source_key_and_ffmpeg_command():
    assert source_key("a.wav", 1.0, False) == source_key("a.wav", 1.0, True)
    cmd = ffmpeg_command("ffmpeg", "song.mp3", 12.5, 1.5, True)
    assert cmd[cmd.index("-ss") + 1] == "12.5000"
    assert "atempo=1.5000" in cmd[cmd.index("-af") + 1]
    assert "-ss" not in ffmpeg_command("ffmpeg", "song.mp3", 0.0, 1.0, True)


# ── voices and buses ─────────────────────────────────────────────────────

def _core_with_voice(total=RATE * 2, spec=None, loops=1):
    core = MixerCore()
    src, _ = _source(total)
    voice = core.add_voice()
    core.set_source(voice, src, 0)
    core.set_spec(voice, spec or audio_mix.MixSpec())
    core.set_loops(voice, loops)
    return core, voice


def test_voice_plays_through_the_stage_bus_unchanged():
    core, voice = _core_with_voice()
    core.play(voice)
    out = core.render()
    want = _pattern(0, BLOCK).astype(np.float32) / 32768.0
    got = out["default"]
    # one 32-frame limiter step late, the 64-frame start ramp, else bit-exact
    assert np.allclose(got[32 + DECLICK:], want[DECLICK:BLOCK - 32], atol=1e-6)
    assert voice.frame == BLOCK and voice.started


def test_pan_and_two_outputs_with_their_own_levels():
    spec = audio_mix.MixSpec(pan=-1.0, sends=(("stage", 1.0), ("foldback", 0.5)))
    core, voice = _core_with_voice(spec=spec)
    core.set_routes({"stage": Route("dev-a"), "foldback": Route("dev-b", gain=2.0)})
    core.play(voice)
    core.render()
    out = core.render()
    a, b = out["dev-a"], out["dev-b"]
    assert np.max(np.abs(a[:, 1])) == 0.0                 # hard left: nothing on the right
    assert np.allclose(b[:, 0], a[:, 0] * 1.0, atol=1e-5)  # 0.5 x 2.0 (trim above 0 dB) = 1.0


def test_muted_output_and_rerouting_while_playing():
    spec = audio_mix.MixSpec(sends=(("stage", 1.0), ("foldback", 1.0)))
    core, voice = _core_with_voice(spec=spec)
    core.set_routes({"stage": Route("dev-a"), "foldback": Route("dev-b", muted=True)})
    core.play(voice)
    out = core.render()
    assert "dev-b" not in out
    core.set_routes({"stage": Route("dev-a"), "foldback": Route("dev-a")})  # both on one device: summed
    core.render()
    out = core.render()
    assert np.max(np.abs(out["dev-a"])) > 0


def test_pause_resume_seek_and_stop():
    core, voice = _core_with_voice()
    core.play(voice)
    core.render()
    core.pause(voice)
    core.render()                     # the 1.3 ms ramp, then paused
    assert voice.state == "paused"
    paused_at = voice.frame
    assert paused_at == BLOCK + DECLICK
    out = core.render()
    assert np.max(np.abs(out.get("default", np.zeros(1)))) < 1e-3  # only the limiter's last step
    core.seek(voice, RATE)
    assert voice.position_frame() == RATE
    core.play(voice)
    core.render()
    assert voice.frame == RATE + BLOCK
    core.stop(voice)
    assert voice.position_frame() == 0             # reported at once, like Qt (the ramp comes next block)
    core.render()
    assert voice.state == "stopped" and voice.frame == 0


def test_pause_then_seek_stays_paused_on_the_new_place():
    # LivePlayer's standby deck: active_p.pause() then setPosition(next target) in the same tick.
    core, voice = _core_with_voice()
    core.play(voice)
    core.render()
    core.pause(voice)
    core.seek(voice, RATE // 2)
    assert voice.position_frame() == RATE // 2
    core.render()
    assert voice.state == "paused" and voice.frame == RATE // 2
    out = core.render()
    assert np.max(np.abs(out.get("default", np.zeros((1, 2)))[64:])) == 0.0   # silent while paused
    core.play(voice)
    core.render()
    assert voice.state == "playing" and voice.frame == RATE // 2 + BLOCK
    core.pause(voice)
    core.play(voice)                       # paused and played again before the pause was heard
    core.render()
    assert voice.state == "playing" and voice.frame == RATE // 2 + 2 * BLOCK


def test_end_of_file_and_loops():
    core, voice = _core_with_voice(total=BLOCK * 3 + 100)
    core.play(voice)
    for _ in range(4):
        core.render()
    assert voice.ended and voice.state == "stopped"
    core2, looping = _core_with_voice(total=BLOCK * 2 + 100, loops=-1)
    core2.play(looping)
    for _ in range(10):
        core2.render()
    assert looping.state == "playing" and not looping.ended
    core3, twice = _core_with_voice(total=BLOCK + 100, loops=2)
    core3.play(twice)
    for _ in range(6):
        core3.render()
    assert twice.ended


def test_level_glides_and_peak_is_reported():
    core, voice = _core_with_voice()
    voice.gain = 0.0
    core.play(voice)
    out = core.render()
    assert np.max(np.abs(out["default"])) == 0.0
    voice.gain = 1.0
    out = core.render()
    ramp = np.abs(out["default"][:, 0])
    assert ramp[100] < ramp[-1]
    assert core.take_peak(voice) > 0 and core.take_peak(voice) == 0.0


def test_reverb_tail_rings_after_stop_and_panic_cuts_it():
    spec = audio_mix.MixSpec(reverb=0.8, room="small", pan=-1.0)  # the test pattern is L = -R: mono 0
    core, voice = _core_with_voice(spec=spec)
    core.play(voice)
    for _ in range(3):
        core.render()
    core.stop(voice)
    core.render()
    assert core.tails_count() == 1
    out = core.render()
    assert np.max(np.abs(out["default"])) > 1e-4   # the room still rings
    core.cut_tails()
    core.render()
    assert core.tails_count() == 0
