"""Test della doppia uscita indipendente (uscita A / uscita B).

Coprono la logica introdotta per pilotare due proiettori separati e
indipendenti, ciascuno con i propri 3 layer, senza toccare media reali:

  1. Normalizzazione del target di uscita e mappatura runtime layer (A=1-3, B=4-6).
  2. Serializzazione di ``Cue.output_target``.
  3. Transizioni di stato separate per uscita (``demote`` / ``promote`` / ``clear``).
  4. Conflitti di layer calcolati sulla chiave ``(output_target, layer)``.
  5. ``DeviceManager``: disponibilità, fallback e mascheramento della finestra B.

Esecuzione:
    QT_QPA_PLATFORM=offscreen pytest -q tests/test_dual_output.py
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
from engine.show_engine import ShowEngine, demote_live_on_layer  # noqa: E402
from models.cue import (  # noqa: E402
    Cue,
    CueStatus,
    FollowMode,
    GroupMode,
    MediaType,
    detect_layer_conflicts,
    layer_label,
    normalize_output_target,
    resolve_output_target,
    runtime_layer,
)
from models.output_config import OutputMode  # noqa: E402


class _FakeSettings:
    """In-memory replacement for QSettings so tests never touch user config."""

    store: dict[str, object] = {}

    def __init__(self, *args, **kwargs) -> None:
        pass

    def value(self, key: str, default: object = None) -> object:
        return _FakeSettings.store.get(key, default)

    def setValue(self, key: str, value: object) -> None:
        _FakeSettings.store[key] = value


class _FakeScreen:
    """Minimal QScreen stand-in: only ``name()`` is read by the manager."""

    def __init__(self, name: str) -> None:
        self._name = name

    def name(self) -> str:
        return self._name


class _FakeOutputWindow:
    """Records the routing calls made by ``DeviceManager``."""

    def __init__(self) -> None:
        self.configured: list[tuple[object, bool]] = []
        self.span_targets: list[object] | None = None
        self.target_screen: object | None = None
        self.hidden = False

    def configure_screen(self, screen: object, is_external: bool = True) -> None:
        self.configured.append((screen, is_external))
        self.hidden = False

    def enter_span_mode(self, screens: list[object]) -> bool:
        self.span_targets = list(screens)
        return True

    def is_spanning(self) -> bool:
        return bool(self.span_targets)

    def set_target_screen(self, screen: object) -> None:
        self.target_screen = screen

    def hide(self) -> None:
        self.hidden = True


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    _FakeSettings.store.clear()
    monkeypatch.setattr(dm_module, "QSettings", _FakeSettings)
    yield _FakeSettings


def _cue(
    cue_id: int,
    name: str = "Cue",
    *,
    layer: int = 1,
    output_target: str = "A",
    media_type: MediaType = MediaType.VIDEO,
    follow: FollowMode = FollowMode.MANUAL,
    parent_id: int | None = None,
    group_mode: GroupMode = GroupMode.STEP,
) -> Cue:
    return Cue.from_dict(
        {
            "cue_id": cue_id,
            "name": name,
            "media_type": media_type.value,
            "file_path": f"/nonexistent/{name}.mp4",
            "layer": layer,
            "output_target": output_target,
            "follow_mode": follow.value,
            "parent_id": parent_id,
            "group_mode": group_mode.value,
        }
    )


# ── Modello: target e runtime layer ───────────────────────────────────

def test_normalize_output_target_falls_back_to_a():
    assert normalize_output_target("B") == "B"
    assert normalize_output_target("b") == "B"
    assert normalize_output_target(" B ") == "B"
    assert normalize_output_target("A") == "A"
    assert normalize_output_target(None) == "A"
    assert normalize_output_target("") == "A"
    assert normalize_output_target("x") == "A"


def test_runtime_layer_maps_a_to_1_3_and_b_to_4_6():
    assert [runtime_layer(n) for n in (1, 2, 3)] == [1, 2, 3]
    assert [runtime_layer(n, "B") for n in (1, 2, 3)] == [4, 5, 6]
    assert [runtime_layer(n, "b") for n in (1, 2, 3)] == [4, 5, 6]


def test_layer_label_marks_output_b():
    assert layer_label(2) == "Layer 2"
    assert layer_label(2, "A") == "Layer 2"
    assert layer_label(2, "B") == "Layer 2 · Uscita B"


def test_cue_serializes_output_target():
    cue = _cue(1, "Bumper", layer=2, output_target="B")
    assert cue.output_target == "B"
    assert cue.to_dict()["output_target"] == "B"

    restored = Cue.from_dict(cue.to_dict())
    assert restored.output_target == "B"

    # Unknown values on load must land on output A, never crash the project.
    legacy = Cue.from_dict(
        {"cue_id": 99, "name": "Old", "media_type": "VIDEO", "file_path": "x.mp4"}
    )
    assert legacy.output_target == "A"


def test_resolve_output_target_collapses_b_when_dual_is_off():
    # With a single projector, a cue assigned to B is shown on A instead of
    # landing on the hidden second window.
    assert resolve_output_target("B", dual_active=True) == "B"
    assert resolve_output_target("B", dual_active=False) == "A"
    assert resolve_output_target("A", dual_active=False) == "A"
    assert resolve_output_target("b", dual_active=False) == "A"


def test_layer_conflicts_reported_when_dual_is_off():
    group = _cue(30, "GRP", media_type=MediaType.GROUP,
                 group_mode=GroupMode.SIMULTANEOUS, layer=1)
    a_child = _cue(31, "A2", layer=2, output_target="A", parent_id=30)
    b_child = _cue(32, "B2", layer=2, output_target="B", parent_id=30)

    assert detect_layer_conflicts([group, a_child, b_child]) == {}

    # Single projector: A·L2 and B·L2 physically overlap.
    conflicts = detect_layer_conflicts(
        [group, a_child, b_child], dual_active=False
    )
    assert a_child.cue_id in conflicts
    assert b_child.cue_id in conflicts


def test_demote_across_outputs_when_dual_is_off():
    a_cue = _cue(41, "A1", layer=2, output_target="A")
    b_cue = _cue(42, "B1", layer=2, output_target="B")
    a_cue.status = CueStatus.LIVE

    demote_live_on_layer(
        [a_cue, b_cue], layer=2, keep_cue_id=42,
        output_target="B", dual_active=False,
    )

    assert a_cue.status == CueStatus.LOADED, "sul proiettore unico i layer coincidono"


# ── ShowEngine: transizioni separate per uscita ───────────────────────

def test_demote_does_not_cross_outputs():
    a_cue = _cue(1, "A1", layer=2, output_target="A")
    b_cue = _cue(2, "B1", layer=2, output_target="B")
    a_cue.status = CueStatus.LIVE
    b_cue.status = CueStatus.LIVE

    demote_live_on_layer([a_cue, b_cue], layer=2, keep_cue_id=2, output_target="B")

    assert a_cue.status == CueStatus.LIVE, "l'uscita A non va toccata dal GO su B"
    assert b_cue.status == CueStatus.LIVE, "la cue appena andata live resta LIVE"


def test_promote_to_live_keeps_same_layer_on_other_output():
    a_cue = _cue(1, "A1", layer=2, output_target="A")
    b_cue = _cue(2, "B1", layer=2, output_target="B")
    a_cue.status = CueStatus.LIVE

    ShowEngine.promote_to_live([a_cue, b_cue], b_cue)

    assert b_cue.status == CueStatus.LIVE
    assert a_cue.status == CueStatus.LIVE


def test_clear_layer_respects_output_target():
    a_cue = _cue(1, "A1", layer=1, output_target="A")
    b_cue = _cue(2, "B1", layer=1, output_target="B")
    a_cue.status = CueStatus.LIVE
    b_cue.status = CueStatus.LIVE

    ShowEngine.clear_layer([a_cue, b_cue], layer=1, output_target="B")
    assert b_cue.status == CueStatus.LOADED
    assert a_cue.status == CueStatus.LIVE

    # ``None`` clears the layer on both outputs (full layer panic).
    ShowEngine.clear_layer([a_cue, b_cue], layer=1)
    assert a_cue.status == CueStatus.LOADED
    assert b_cue.status == CueStatus.LOADED


# ── Conflitti di layer: chiave (output_target, layer) ─────────────────

def test_same_layer_on_different_outputs_is_not_a_conflict():
    group = _cue(10, "GRP", media_type=MediaType.GROUP,
                 group_mode=GroupMode.SIMULTANEOUS, layer=1)
    a_child = _cue(11, "A2", layer=2, output_target="A", parent_id=10)
    b_child = _cue(12, "B2", layer=2, output_target="B", parent_id=10)

    conflicts = detect_layer_conflicts([group, a_child, b_child])

    assert conflicts == {}, "A·L2 e B·L2 sono uscite diverse: nessun conflitto"


def test_real_conflict_on_same_output_is_reported():
    group = _cue(20, "GRP", media_type=MediaType.GROUP,
                 group_mode=GroupMode.SIMULTANEOUS, layer=1)
    first = _cue(21, "One", layer=2, output_target="A", parent_id=20)
    second = _cue(22, "Two", layer=2, output_target="A", parent_id=20)

    conflicts = detect_layer_conflicts([group, first, second])

    assert first.cue_id in conflicts
    assert second.cue_id in conflicts
    assert "Layer 2" in conflicts[first.cue_id].reason


# ── DeviceManager: disponibilità e fallback ──────────────────────────

def _patch_screens(monkeypatch, screens: list[_FakeScreen]) -> None:
    monkeypatch.setattr(
        DeviceManager, "get_external_screens", staticmethod(lambda: list(screens))
    )


def test_dual_unavailable_without_two_external_screens(monkeypatch):
    _patch_screens(monkeypatch, [_FakeScreen("P1")])
    mgr = DeviceManager()
    assert mgr.is_dual_available() is False
    assert mgr.dual_warning() is not None
    assert mgr.set_output_mode(OutputMode.DUAL.value) is False
    assert mgr.get_output_mode() == OutputMode.SINGLE.value


def test_dual_requires_registered_secondary_window(monkeypatch):
    _patch_screens(monkeypatch, [_FakeScreen("P1"), _FakeScreen("P2")])
    mgr = DeviceManager()
    primary = _FakeOutputWindow()
    mgr.register_output_window(primary)

    assert mgr.is_dual_available() is True
    assert mgr.set_output_mode(OutputMode.DUAL.value) is False
    assert mgr.get_output_mode() == OutputMode.SINGLE.value, "fallback sicuro a singolo"


def test_dual_configures_both_projector_windows(monkeypatch):
    _patch_screens(monkeypatch, [_FakeScreen("P1"), _FakeScreen("P2")])
    mgr = DeviceManager()
    primary = _FakeOutputWindow()
    secondary = _FakeOutputWindow()
    mgr.register_output_window(primary)
    mgr.register_secondary_output_window(secondary)

    assert mgr.set_output_mode(OutputMode.DUAL.value) is True
    assert mgr.get_output_mode() == OutputMode.DUAL.value
    assert primary.configured[-1][1] is True
    assert secondary.configured[-1][1] is True
    assert _FakeSettings.store.get("output/mode") == OutputMode.DUAL.value

    # Leaving dual hides the second projector so it cannot keep a stale frame.
    assert mgr.set_output_mode(OutputMode.SINGLE.value) is True
    assert secondary.hidden is True
    assert _FakeSettings.store.get("output/mode") == OutputMode.SINGLE.value


def test_saved_dual_mode_restored_when_secondary_registers(monkeypatch):
    _patch_screens(monkeypatch, [_FakeScreen("P1"), _FakeScreen("P2")])
    _FakeSettings.store["output/mode"] = OutputMode.DUAL.value

    mgr = DeviceManager()
    primary = _FakeOutputWindow()
    secondary = _FakeOutputWindow()
    mgr.register_output_window(primary)
    assert mgr.get_output_mode() == OutputMode.DUAL.value
    mgr.register_secondary_output_window(secondary)

    assert mgr.get_output_mode() == OutputMode.DUAL.value
    assert primary.configured
    assert secondary.configured


def test_losing_a_screen_during_dual_falls_back_to_single(monkeypatch):
    _patch_screens(monkeypatch, [_FakeScreen("P1"), _FakeScreen("P2")])
    mgr = DeviceManager()
    primary = _FakeOutputWindow()
    secondary = _FakeOutputWindow()
    mgr.register_output_window(primary)
    mgr.register_secondary_output_window(secondary)
    assert mgr.set_output_mode(OutputMode.DUAL.value) is True

    # One projector is unplugged mid-show.
    _patch_screens(monkeypatch, [_FakeScreen("P1")])
    mgr._on_screens_changed()

    assert mgr.get_output_mode() == OutputMode.SINGLE.value
    assert secondary.hidden is True


# ── Rilevamento proiettori e assegnazione A/B ─────────────────────────

def test_external_projectors_are_assigned_to_both_outputs(monkeypatch):
    p1, p2 = _FakeScreen("P1"), _FakeScreen("P2")
    _patch_screens(monkeypatch, [p1, p2])

    mgr = DeviceManager()

    assert mgr.get_output_screen("A") is p1
    assert mgr.get_output_screen("B") is p2
    assert mgr.get_dual_screens() == [p1, p2]


def test_single_projector_goes_to_output_a(monkeypatch):
    p1 = _FakeScreen("P1")
    _patch_screens(monkeypatch, [p1])

    mgr = DeviceManager()

    assert mgr.get_output_screen("A") is p1
    assert mgr.get_output_screen("B") is None
    assert mgr.is_dual_available() is False


def test_no_projector_uses_director_screen(monkeypatch):
    _patch_screens(monkeypatch, [])

    mgr = DeviceManager()

    assert mgr.get_output_screen("B") is None
    # The single output is the director screen: nothing to route.
    assert mgr.is_span_available() is False


def test_swapping_projectors_swaps_outputs(monkeypatch):
    p1, p2 = _FakeScreen("P1"), _FakeScreen("P2")
    _patch_screens(monkeypatch, [p1, p2])

    mgr = DeviceManager()
    assert mgr.set_output_screen("A", p2) is True

    assert mgr.get_output_screen("A") is p2
    assert mgr.get_output_screen("B") is p1
    assert mgr.get_dual_screens() == [p2, p1]


def test_output_b_rejected_with_a_single_projector(monkeypatch):
    p1 = _FakeScreen("P1")
    _patch_screens(monkeypatch, [p1])

    mgr = DeviceManager()

    assert mgr.set_output_screen("B", p1) is False
    assert mgr.get_output_screen("B") is None


def test_dual_uses_the_projectors_chosen_by_the_operator(monkeypatch):
    p1, p2 = _FakeScreen("P1"), _FakeScreen("P2")
    _patch_screens(monkeypatch, [p1, p2])

    mgr = DeviceManager()
    window_a = _FakeOutputWindow()
    window_b = _FakeOutputWindow()
    mgr.register_output_window(window_a)
    mgr.register_secondary_output_window(window_b)

    assert mgr.set_output_screen("A", p2) is True
    assert mgr.set_output_mode(OutputMode.DUAL.value) is True

    assert window_a.configured[-1][0] is p2
    assert window_b.configured[-1][0] is p1


# ── Capacità audio: cuffia PFL solo con due schede ────────────────────

def test_audio_routing_requires_a_second_output_device(monkeypatch):
    monkeypatch.setattr(
        DeviceManager, "get_available_audio_devices", staticmethod(lambda: [])
    )
    mgr = DeviceManager()
    assert mgr.audio_output_count() == 0
    assert mgr.has_multiple_audio_outputs() is False

    monkeypatch.setattr(
        DeviceManager,
        "get_available_audio_devices",
        staticmethod(lambda: [object()]),
    )
    assert mgr.has_multiple_audio_outputs() is False

    monkeypatch.setattr(
        DeviceManager,
        "get_available_audio_devices",
        staticmethod(lambda: [object(), object()]),
    )
    assert mgr.has_multiple_audio_outputs() is True
