"""Test della configurazione delle uscite video (singolo schermo / span).

Verificano il modello e la logica di routing senza aprire media reali:

  1. Normalizzazione e serializzazione di ``OutputConfig``.
  2. ``OutputWindow``: lo span è esplicito, annullabile e non fatale.
  3. ``DeviceManager``: span disponibile solo con schermi esterni, fallback
     sicuro, persistenza della scelta.

Esecuzione:
    QT_QPA_PLATFORM=offscreen pytest -q tests/test_output_modes.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

import engine.device_manager as dm_module  # noqa: E402
from engine.device_manager import DeviceManager  # noqa: E402
from models.output_config import (  # noqa: E402
    OutputConfig,
    OutputMode,
    normalize_output_mode,
)
from ui.output_window import OutputWindow  # noqa: E402


class _FakeSettings:
    """In-memory replacement for QSettings so tests never touch user config."""

    store: dict[str, object] = {}

    def __init__(self, *args, **kwargs) -> None:
        pass

    def value(self, key: str, default: object = None) -> object:
        return _FakeSettings.store.get(key, default)

    def setValue(self, key: str, value: object) -> None:
        _FakeSettings.store[key] = value


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    _FakeSettings.store.clear()
    monkeypatch.setattr(dm_module, "QSettings", _FakeSettings)
    yield _FakeSettings


# ── Modello ────────────────────────────────────────────────────────────

def test_normalize_output_mode_accepts_only_known_values():
    assert normalize_output_mode("span") == OutputMode.SPAN.value
    assert normalize_output_mode(OutputMode.SPAN) == OutputMode.SPAN.value
    assert normalize_output_mode("SPAN") == OutputMode.SPAN.value
    assert normalize_output_mode(" due ") == OutputMode.SINGLE.value
    assert normalize_output_mode(None) == OutputMode.SINGLE.value
    assert normalize_output_mode("") == OutputMode.SINGLE.value


def test_output_config_roundtrip():
    cfg = OutputConfig(mode="span")
    assert cfg.is_span is True
    assert cfg.to_dict() == {"mode": "span"}

    restored = OutputConfig.from_dict(cfg.to_dict())
    assert restored.mode == OutputMode.SPAN.value

    assert OutputConfig.from_dict(None).mode == OutputMode.SINGLE.value
    assert OutputConfig.from_dict({"mode": "bogus"}).mode == OutputMode.SINGLE.value
    assert OutputConfig.from_dict(cfg).mode == OutputMode.SPAN.value


# ── OutputWindow ───────────────────────────────────────────────────────

def test_span_without_screens_returns_false_and_keeps_state():
    win = OutputWindow()
    try:
        assert win.enter_span_mode([]) is False
        assert win.is_spanning() is False
        assert win.spanned_screens() == []
    finally:
        win.force_close()


def test_enter_span_mode_marks_window_and_configure_screen_clears_it():
    app = QApplication.instance()
    screen = app.primaryScreen()
    win = OutputWindow()
    try:
        assert win.enter_span_mode([screen]) is True
        assert win.is_spanning() is True
        assert win.spanned_screens() == [screen]

        win.configure_screen(screen, is_external=False)
        assert win.is_spanning() is False
    finally:
        win.force_close()


# ── DeviceManager ──────────────────────────────────────────────────────

def test_output_mode_defaults_to_single():
    mgr = DeviceManager()
    assert mgr.get_output_mode() == OutputMode.SINGLE.value


def test_span_unavailable_without_external_screens():
    mgr = DeviceManager()
    assert mgr.is_span_available() is False
    assert mgr.set_output_mode("span") is False
    assert mgr.get_output_mode() == OutputMode.SINGLE.value
    assert mgr.span_warning() is not None


def test_set_output_mode_single_always_succeeds():
    mgr = DeviceManager()
    assert mgr.set_output_mode("single") is True
    assert mgr.get_output_mode() == OutputMode.SINGLE.value


def test_span_applies_and_persists_when_external_screen_exists(monkeypatch):
    app = QApplication.instance()
    screen = app.primaryScreen()
    monkeypatch.setattr(
        DeviceManager, "get_external_screens", staticmethod(lambda: [screen])
    )

    mgr = DeviceManager()
    out = OutputWindow()
    try:
        mgr.register_output_window(out)
        assert mgr.is_span_available() is True

        assert mgr.set_output_mode("span") is True
        assert mgr.get_output_mode() == OutputMode.SPAN.value
        assert out.is_spanning() is True
        assert _FakeSettings.store.get("output/mode") == OutputMode.SPAN.value

        assert mgr.set_output_mode("single") is True
        assert mgr.get_output_mode() == OutputMode.SINGLE.value
        assert out.is_spanning() is False
        assert _FakeSettings.store.get("output/mode") == OutputMode.SINGLE.value
    finally:
        out.force_close()


def test_saved_span_mode_restored_on_registration(monkeypatch):
    app = QApplication.instance()
    screen = app.primaryScreen()
    monkeypatch.setattr(
        DeviceManager, "get_external_screens", staticmethod(lambda: [screen])
    )
    _FakeSettings.store["output/mode"] = "span"

    mgr = DeviceManager()
    out = OutputWindow()
    try:
        assert mgr.get_output_mode() == OutputMode.SPAN.value
        mgr.register_output_window(out)
        assert out.is_spanning() is True
    finally:
        out.force_close()
