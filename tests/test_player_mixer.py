"""Own mixer decks inside the live player (3.2 / 3.9), without a sound card.

The service runs without its audio thread: the test renders the mixer
blocks itself, in real time, while the Qt events are processed.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

APP_DIR = Path(__file__).resolve().parents[1] / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import numpy as np
import pytest
from engine import audio_mix, player_live, player_mixer
from engine.audio_mixer_core import Route
from engine.audio_mixer_dsp import BLOCK, RATE
from engine.audio_mixer_output import SETTING_ENABLED, MixerService
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

MS = QMediaPlayer.MediaStatus
PB = QMediaPlayer.PlaybackState


class _Decoder:
    """Synthetic file: *seconds* of a constant level 0.25 (missing files fail like FFmpeg)."""

    def __init__(self, seconds: float = 2.0):
        self.total = int(seconds * RATE)

    def __call__(self, source, segment, start_sec):
        if "missing" in source.path:
            segment.error = "No such file"
            source.error = segment.error
            segment.done = True
            return self
        n = self.total - segment.start
        if n > 0:
            segment.write(np.full((n, 2), 8192, dtype=np.int16))
        segment.eof = segment.done = True
        source.note_end(segment)
        return self

    def cancel(self):
        pass


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def mixer(qt_app):
    service = MixerService(start_output=False)
    service.decoder = _Decoder()
    MixerService._instance = service
    service.core.set_routes({"stage": Route("dev-a"), "hall": Route("dev-a"), "foldback": Route("dev-b")})
    yield service
    service.shutdown()


def _run(service, seconds: float) -> list[dict]:
    """Process Qt events and render the mixer at real-time pace (one block per 21 ms)."""
    out = []
    start = time.monotonic()
    blocks = 0
    while time.monotonic() - start < seconds:
        QCoreApplication.processEvents()
        due = int((time.monotonic() - start) * RATE / BLOCK)
        while blocks < due:
            out.append(service.core.render(BLOCK))
            blocks += 1
        time.sleep(0.002)
    return out


def _peak(blocks: list[dict], bus: str) -> float:
    return max((float(np.max(np.abs(b[bus]))) for b in blocks if bus in b), default=0.0)


def _spec(**kw):
    return audio_mix.MixSpec(**kw)


def test_mixer_deck_speaks_like_a_media_player(mixer):
    from PySide6.QtCore import QUrl

    player = player_mixer.MixerMediaPlayer(service=mixer)
    audio = player_mixer.MixerAudioOutput()
    player.setAudioOutput(audio)
    statuses, positions, durations = [], [], []
    player.mediaStatusChanged.connect(statuses.append)
    player.positionChanged.connect(positions.append)
    player.durationChanged.connect(durations.append)
    player.setSource(QUrl.fromLocalFile(os.path.abspath("song.wav")))
    player.setPosition(0)                      # as LivePlayer.load() does: decoding starts at the IN point
    _run(mixer, 0.05)
    assert statuses[:2] == [MS.LoadingMedia, MS.LoadedMedia]
    assert durations and durations[-1] == 2000 and player.duration() == 2000
    player.setLoops(1)
    player.play()
    assert player.playbackState() == PB.PlayingState
    _run(mixer, 0.3)
    assert MS.BufferedMedia in statuses and max(positions) > 150
    player.pause()
    _run(mixer, 0.05)
    held = player.position()
    _run(mixer, 0.1)
    assert player.position() == held and player.playbackState() == PB.PausedState
    player.setPosition(1900)
    assert player.position() == 1900
    player.play()
    _run(mixer, 0.25)
    assert statuses[-1] == MS.EndOfMedia and player.playbackState() == PB.StoppedState
    player.deleteLater()


def test_a_missing_file_is_an_error(mixer):
    from PySide6.QtCore import QUrl

    player = player_mixer.MixerMediaPlayer(service=mixer)
    errors = []
    player.errorOccurred.connect(lambda err, msg: errors.append(msg))
    player.setSource(QUrl.fromLocalFile(os.path.abspath("missing.wav")))
    player.play()
    _run(mixer, 0.1)
    assert player.mediaStatus() == MS.InvalidMedia and errors


def test_live_player_switches_decks_per_cue(mixer):
    lp = player_live.LivePlayer()
    qt_deck = lp._player
    lp.use_mixer(_spec(pan=-1.0))
    lp.load(os.path.abspath("song.wav"))
    assert lp.uses_mixer() and isinstance(lp._player, player_mixer.MixerMediaPlayer)
    lp.play()
    blocks = _run(mixer, 0.3)
    assert _peak(blocks, "dev-a") > 0.2
    assert max(float(np.max(np.abs(b["dev-a"][:, 1]))) for b in blocks if "dev-a" in b) == 0.0  # hard left
    lp.load(os.path.abspath("song.wav"))          # no use_mixer(): back to Qt Multimedia
    assert not lp.uses_mixer() and isinstance(lp._player, QMediaPlayer) and lp._player is not qt_deck
    lp.shutdown()


def test_fades_output_gain_and_stop(mixer):
    lp = player_live.LivePlayer()
    lp.set_output_gain(0.0)                    # the cue's main output muted by the map ...
    lp.use_mixer(_spec(sends=(("foldback", 1.0),)))
    lp.load(os.path.abspath("song.wav"))
    lp.configure_automation(base_volume=1.0)
    lp.play()
    blocks = _run(mixer, 0.2)
    assert _peak(blocks, "dev-b") > 0.2        # ... the mixer row still plays (its own route)
    lp.fade_out(0.2, stop_after=True)
    _run(mixer, 0.4)
    assert lp._player.playbackState() == PB.StoppedState
    blocks = _run(mixer, 0.1)
    assert _peak(blocks, "dev-b") < 1e-3
    lp.shutdown()


def test_out_point_holds_exactly_and_ends_the_cue(mixer):
    lp = player_live.LivePlayer()
    ended = []
    lp.signals.eof_reached.connect(lambda: ended.append(True))
    lp.use_mixer(_spec())
    lp.load(os.path.abspath("song.wav"), start=0.0, end=0.5)
    lp.configure_automation(base_volume=1.0)
    lp.set_loop(False)
    lp.play()
    voice = lp._player._voice
    # Render far ahead at once (as the audio thread does at a start): the voice must stop at 0.5 s.
    for _ in range(40):
        mixer.core.render(BLOCK)
    assert voice.held and voice.frame == RATE // 2
    _run(mixer, 0.1)
    assert ended
    lp.shutdown()


def test_section_loop_through_the_standby_deck_plays_one_voice_at_a_time(mixer, tmp_path):
    from models.cue import CueSection

    song = tmp_path / "song.wav"
    song.write_bytes(b"")   # the live player pre-cues its standby deck only for a file that exists
    lp = player_live.LivePlayer()
    ended = []
    lp.signals.eof_reached.connect(lambda: ended.append(True))
    lp.use_mixer(_spec())
    lp.load(str(song), start=0.0, end=1.0)
    lp.configure_automation(base_volume=1.0, sections=[
        CueSection(label="A", start=0.0, end=0.4, loops=2), CueSection(label="B", start=0.4, end=None)])
    lp.set_loop(False)
    lp.play()
    blocks = _run(mixer, 2.0)
    assert ended                                    # A twice, then B to the OUT point, then the end
    assert lp._standby_player is not None and isinstance(lp._standby_player, player_mixer.MixerMediaPlayer)
    # The file is a constant 0.25: two decks sounding together would reach 0.5.
    assert 0.2 < _peak(blocks, "dev-a") < 0.3
    lp.shutdown()


def test_crossfade_tail_and_panic(mixer):
    lp = player_live.LivePlayer()
    lp.use_mixer(_spec())
    lp.load(os.path.abspath("song.wav"))
    lp.configure_automation(base_volume=1.0)
    lp.play()
    _run(mixer, 0.15)
    assert lp.hand_over_tail(1.0)
    assert player_live.tails_count() == 1
    tail_voice = player_live._TAILS[0]._player._voice
    _run(mixer, 0.3)
    assert 0.0 < tail_voice.gain < 1.0          # fading on its own
    player_live.stop_all_tails()
    player_mixer.panic()
    _run(mixer, 0.1)
    assert player_live.tails_count() == 0 and tail_voice.state == "stopped"
    lp.shutdown()


def test_reverb_tail_after_a_cue_and_vu_peak(mixer):
    lp = player_live.LivePlayer()
    lp.use_mixer(_spec(reverb=0.5, room="small"))
    lp.load(os.path.abspath("song.wav"))
    lp.configure_automation(base_volume=1.0)
    lp.play()
    _run(mixer, 0.2)
    assert lp.take_peak() > 0.2
    lp.stop()
    blocks = _run(mixer, 0.1)
    assert mixer.core.tails_count() == 1 and _peak(blocks, "dev-a") > 0
    player_live.stop_all_tails()               # PANIC / Blackout cut the ringing room
    _run(mixer, 0.05)
    assert mixer.core.tails_count() == 0
    lp.shutdown()


def test_spec_for_launch_and_the_switch(mixer, monkeypatch):
    from models.cue import Cue, MediaType

    monkeypatch.setattr(player_mixer, "find_ffmpeg", lambda: "ffmpeg")
    plain = Cue(cue_id=7101, name="plain", media_type=MediaType.AUDIO, file_path="a.wav")
    panned = Cue(cue_id=7102, name="left", media_type=MediaType.AUDIO, file_path="a.wav", audio_mix={"pan": -1})
    assert player_mixer.spec_for_launch(plain) is None
    assert player_mixer.spec_for_launch(panned).pan == -1.0
    notes = []
    QSettings("BlindCue", "BlindCue").setValue(SETTING_ENABLED, False)
    try:
        assert player_mixer.spec_for_launch(panned, notify=notes.append) is None
        assert player_mixer.spec_for_launch(panned, notify=notes.append) is None
        assert notes == ["mixer_off"]          # said once per cue
    finally:
        QSettings("BlindCue", "BlindCue").remove(SETTING_ENABLED)


def test_device_manager_routes_the_mixer(mixer, monkeypatch):
    from engine.device_manager import DeviceManager

    mgr = DeviceManager()
    mgr.register_mixer(mixer)
    routes = mixer.core.routes()
    assert set(routes) == {"stage", "hall", "foldback"}
    assert routes["foldback"].muted                  # foldback not set here: muted by its rule
    mgr.set_output_rule("stage", trim_db=6.0)        # above 0 dB: only the mixer plays it
    assert mixer.core.routes()["stage"].gain == pytest.approx(10 ** (6 / 20))
    mgr.set_output_rule("stage", trim_db=0.0)
