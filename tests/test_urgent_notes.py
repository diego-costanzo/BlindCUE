"""Urgent director's notes are highlighted in Italian, Polish and English, by whole words."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from ui.live_show_view import LiveCueRowDelegate


@pytest.mark.parametrize("text", [
    "ATTENZIONE: fumo in scena",
    "Buio totale prima del cambio",
    "UWAGA na kabel",
    "Poczekaj na wejście Ani",
    "czekaj na znak reżysera",
    "STOP, jeśli aktor nie wszedł",
    "Ciemno na scenie",
    "Wait for the bell",
    "Danger: pyro",
    "blackout before act 2",
])
def test_urgent_words(text):
    assert LiveCueRowDelegate.is_urgent_note(text)


@pytest.mark.parametrize("text", [
    "",
    "muzyka stopniowo ciszej",       # "stop" inside a word
    "awaiting applause",             # "wait" inside a word
    "ciemny kostium",                # a dark costume is not an alarm
    "Uwagi dla świateł w scenariuszu",  # "uwagi" = remarks, not "uwaga!"
    "Music under dialogue",
])
def test_ordinary_notes(text):
    assert not LiveCueRowDelegate.is_urgent_note(text)
