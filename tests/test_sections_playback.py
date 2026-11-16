"""Regressione: la modalità delle sezioni deve valere a ogni passaggio.

Bug storico: la sezione marcata "Salta" veniva rispettata al primo giro e poi
ignorata, perché (a) il sequencer ripartiva dall'ultima sezione suonata invece
che dalla prima e (b) un secondo report di posizione in ritardo sullo stesso
confine faceva avanzare il sequencer due volte, bruciando un'iterazione o un
taglio.

Esecuzione:
    QT_QPA_PLATFORM=offscreen pytest -q tests/test_sections_playback.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from engine.envelope import SectionSequencer  # noqa: E402
from models.cue import CueSection  # noqa: E402


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _abc() -> list[CueSection]:
    """A normale, B da saltare, C normale (30 s totali)."""
    return [
        CueSection(label="A", start=0.0, end=10.0),
        CueSection(label="B", start=10.0, end=20.0, skip=True),
        CueSection(label="C", start=20.0, end=None),
    ]


# ── Sequencer ─────────────────────────────────────────────────────────

class TestSkipIsHonouredEveryPass:
    def test_second_pass_still_skips(self) -> None:
        seq = SectionSequencer()
        seq.configure(_abc(), 0.0, 30.0)

        assert seq.advance_at_boundary() == ("JUMP", 2, 20.0)
        assert seq.advance_at_boundary()[0] == "EOF"
        assert seq.current_index == 2, "dopo EOF l'indice resta sull'ultima sezione"

        seq.restart()
        assert seq.current_index == 0, "il replay deve ripartire dalla prima sezione utile"
        assert seq.advance_at_boundary() == ("JUMP", 2, 20.0), "B deve restare saltata"

    def test_loop_repeats_then_cut(self) -> None:
        seq = SectionSequencer()
        seq.configure(
            [
                CueSection(label="A", start=0.0, end=4.0, loops=2),
                CueSection(label="B", start=4.0, end=8.0, skip=True),
                CueSection(label="C", start=8.0, end=None),
            ],
            0.0,
            20.0,
        )
        assert seq.advance_at_boundary() == ("JUMP", 0, 0.0)   # prima ripetizione
        assert seq.advance_at_boundary() == ("JUMP", 2, 8.0)   # taglio della sezione B
        assert seq.advance_at_boundary()[0] == "EOF"

    def test_marking_playing_section_as_skip_leaves_it(self) -> None:
        seq = SectionSequencer()
        seq.configure(_abc(), 0.0, 30.0)
        assert seq.current_index == 0

        changed = _abc()
        changed[0].skip = True
        seq.update_live_sections(changed, 30.0)

        assert seq.current_index == 2, "non deve continuare a suonare la sezione appena saltata"

    def test_scrub_inside_skipped_section_snaps_forward(self) -> None:
        seq = SectionSequencer()
        seq.configure(_abc(), 0.0, 30.0)
        assert seq.section_index_for_time(15.0) == 2, "15 s cade in B, che è da saltare"
        assert seq.section_index_for_time(5.0) == 0

    def test_jump_onto_skipped_section_moves_forward(self) -> None:
        seq = SectionSequencer()
        seq.configure(_abc(), 0.0, 30.0)
        assert seq.jump_to(1) == 20.0
        assert seq.current_index == 2


# ── Latch sui confini (doppio avanzamento) ────────────────────────────

class _StubAudio:
    def setVolume(self, value: float) -> None:  # noqa: N802 - API Qt
        self.volume = value

    def setMuted(self, muted: bool) -> None:  # noqa: N802 - API Qt
        self.muted = muted


class _StubDeck:
    """Minimal QMediaPlayer stand-in: only what the boundary logic touches."""

    def __init__(self) -> None:
        self.pos = 0

    def playbackState(self):  # noqa: N802 - API Qt
        return QMediaPlayer.PlaybackState.PlayingState

    def setPosition(self, ms: int) -> None:  # noqa: N802 - API Qt
        self.pos = ms

    def position(self) -> int:
        return self.pos

    def pause(self) -> None:
        pass


class TestBoundaryLatch:
    def test_preview_does_not_advance_twice(self, qt_app) -> None:
        from engine.player_test import TestPlayer

        player = TestPlayer()
        try:
            player.is_playing = lambda: True  # type: ignore[assignment]
            player.configure_automation(
                sections=[
                    CueSection(label="A", start=0.0, end=4.0, loops=2),
                    CueSection(label="B", start=4.0, end=8.0, skip=True),
                    CueSection(label="C", start=8.0, end=None),
                ]
            )
            player._driver_timer.stop()

            player._check_boundaries(3990)
            assert player._sequencer.iteration == 1, "prima ripetizione della sezione A"

            # Report di posizione in ritardo: non deve contare come un nuovo confine.
            player._check_boundaries(3990)
            assert player._sequencer.iteration == 1
            assert player._sequencer.current_index == 0

            player._check_boundaries(20)          # il seek è atterrato: latch riarmato
            player._check_boundaries(3990)        # vero secondo confine
            assert player._sequencer.current_index == 2, "B deve essere saltata"
        finally:
            player.shutdown()

    def test_live_does_not_advance_twice(self, qt_app) -> None:
        from engine.player_live import LivePlayer

        player = LivePlayer()
        try:
            deck = _StubDeck()
            player._deck_pair = lambda idx=None: (deck, _StubAudio())  # type: ignore[assignment]
            player.configure_automation(
                sections=[
                    CueSection(label="A", start=0.0, end=4.0, loops=2),
                    CueSection(label="B", start=4.0, end=8.0, skip=True),
                    CueSection(label="C", start=8.0, end=None),
                ]
            )
            player._driver_timer.stop()

            player._check_boundaries(3990)
            assert player._sequencer.iteration == 1

            player._check_boundaries(3990)
            assert player._sequencer.iteration == 1, "un confine non va conteggiato due volte"

            player._check_boundaries(20)
            player._check_boundaries(3990)
            assert player._sequencer.current_index == 2
        finally:
            player._driver_timer.stop()
            player.shutdown()

    def test_preview_ignores_stale_end_of_media(self, qt_app) -> None:
        from engine.player_test import TestPlayer

        player = TestPlayer()
        try:
            player.is_playing = lambda: True  # type: ignore[assignment]
            player.configure_automation(
                sections=[
                    CueSection(label="A", start=0.0, end=4.0, loops=2),
                    CueSection(label="B", start=4.0, end=8.0, skip=True),
                    CueSection(label="C", start=8.0, end=None),
                ]
            )
            player._driver_timer.stop()

            player._check_boundaries(3990)  # primo confine: riavvia A, disarmato
            assert player._sequencer.iteration == 1

            # EndOfMedia in ritardo dallo stesso bordo: non deve contare.
            player._on_media_status_changed(QMediaPlayer.MediaStatus.EndOfMedia)
            assert player._sequencer.iteration == 1
            assert player._sequencer.current_index == 0
        finally:
            player.shutdown()

    def test_live_ignores_stale_end_of_media(self, qt_app) -> None:
        from engine.player_live import LivePlayer

        player = LivePlayer()
        try:
            deck = _StubDeck()
            player._deck_pair = lambda idx=None: (deck, _StubAudio())  # type: ignore[assignment]
            player.configure_automation(
                sections=[
                    CueSection(label="A", start=0.0, end=4.0, loops=2),
                    CueSection(label="B", start=4.0, end=8.0, skip=True),
                    CueSection(label="C", start=8.0, end=None),
                ]
            )
            player._driver_timer.stop()

            player._check_boundaries(3990)
            assert player._sequencer.iteration == 1

            player._on_deck_status(0, QMediaPlayer.MediaStatus.EndOfMedia)
            assert player._sequencer.iteration == 1
            assert player._sequencer.current_index == 0
        finally:
            player._driver_timer.stop()
            player.shutdown()
