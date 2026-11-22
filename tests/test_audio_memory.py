"""Speakers chosen on this computer are remembered (2026-11-22).

The choice lives in the settings of the computer, never in the show, so a
show opened elsewhere uses that computer's choice or the Windows default.
Remembered speakers that are unplugged (a projector's HDMI audio) give way to
the Windows default with a notice, and are used again when they come back.
Fake devices and in-memory settings: the real registry is never touched.
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

import engine.device_manager as dm  # noqa: E402


class FakeDevice:
    def __init__(self, dev_id: bytes, name: str) -> None:
        self._id, self._name = dev_id, name

    def id(self) -> bytes:
        return self._id

    def description(self) -> str:
        return self._name

    def isNull(self) -> bool:
        return False

    def isDefault(self) -> bool:
        return self is FakeMedia.default


REALTEK = FakeDevice(b"{0.0.0}.{realtek}", "Speakers (Realtek)")
PROJECTOR = FakeDevice(b"{0.0.0}.{hdmi-lg}", "24EA53 (HD Audio)")
USB = FakeDevice(b"{0.0.0}.{usb-port-1}", "USB DAC")


class FakeMedia:
    """Stands in for QMediaDevices: what Windows exposes right now."""
    outputs: list[FakeDevice] = []
    default: FakeDevice = REALTEK

    @classmethod
    def audioOutputs(cls):
        return list(cls.outputs)

    @classmethod
    def defaultAudioOutput(cls):
        return cls.default


class FakeSettings:
    store: dict[str, object] = {}

    def __init__(self, *_a) -> None:
        pass

    def value(self, key, default=None, **_k):
        return self.store.get(key, default)

    def setValue(self, key, value) -> None:
        self.store[key] = value

    def remove(self, key) -> None:
        self.store.pop(key, None)


class FakePlayer:
    def __init__(self) -> None:
        self.device = None

    def set_audio_device(self, device) -> None:
        self.device = device


@pytest.fixture()
def manager(monkeypatch):
    QApplication.instance() or QApplication([])
    FakeSettings.store = {}
    FakeMedia.outputs = [REALTEK, PROJECTOR]
    FakeMedia.default = REALTEK
    monkeypatch.setattr(dm, "QSettings", FakeSettings)

    def make():
        mgr = dm.DeviceManager()
        # After construction: every audio query goes through the fake.
        monkeypatch.setattr(dm, "QMediaDevices", FakeMedia)
        mgr._master_device = mgr._resolve_audio("master")
        mgr._monitor_device = mgr._resolve_audio("monitor")
        player = FakePlayer()
        mgr.register_live_players([player])
        notices: list[str] = []
        mgr.audio_notice.connect(notices.append)
        return mgr, player, notices

    return make


def test_nothing_chosen_follows_the_windows_default(manager):
    mgr, player, _ = manager()
    assert mgr.get_master_audio_device() is REALTEK
    assert not mgr.is_audio_remembered("master")
    assert mgr.audio_notice_text() == ""
    assert player.device is REALTEK


def test_chosen_speakers_are_stored_for_this_computer(manager):
    mgr, player, notices = manager()
    mgr.choose_master_audio(PROJECTOR)
    assert FakeSettings.store["audio/master_id"] == PROJECTOR.id().hex()
    assert FakeSettings.store["audio/master_name"] == PROJECTOR.description()
    assert player.device is PROJECTOR
    assert not mgr.is_audio_remembered("monitor")   # roles are independent

    # Next start of the program on the same computer.
    mgr2, _, _ = manager()
    assert mgr2.get_master_audio_device() is PROJECTOR


def test_unplugged_projector_falls_back_and_comes_back(manager):
    mgr, player, notices = manager()
    mgr.choose_master_audio(PROJECTOR)
    notices.clear()

    FakeMedia.outputs = [REALTEK]                  # projector unplugged
    mgr._on_audio_outputs_changed()
    assert player.device is REALTEK
    assert mgr.missing_audio_name("master") == PROJECTOR.description()
    assert notices and PROJECTOR.description() in notices[-1] and REALTEK.description() in notices[-1]
    assert mgr.is_audio_remembered("master")       # the choice is kept

    FakeMedia.outputs = [REALTEK, PROJECTOR]       # plugged in again
    FakeMedia.default = PROJECTOR                  # Windows grabs the HDMI audio too
    mgr._on_audio_outputs_changed()
    assert player.device is PROJECTOR
    assert mgr.missing_audio_name("master") is None
    assert "di nuovo collegata" in notices[-1]


def test_windows_switching_its_default_does_not_move_chosen_speakers(manager):
    mgr, player, _ = manager()
    mgr.choose_master_audio(REALTEK)
    FakeMedia.default = PROJECTOR                  # Windows switches to HDMI on plug-in
    mgr._on_audio_outputs_changed()
    assert player.device is REALTEK


def test_show_opened_on_another_computer_without_those_speakers(manager):
    FakeSettings.store = {"audio/master_id": b"{other-pc}".hex(), "audio/master_name": "Other PC speakers"}
    FakeMedia.outputs = [REALTEK]
    mgr, player, _ = manager()
    assert mgr.get_master_audio_device() is REALTEK
    assert player.device is REALTEK
    assert "Other PC speakers" in mgr.audio_notice_text()


def test_usb_card_in_another_port_is_found_by_name(manager):
    mgr, player, _ = manager()
    mgr.choose_master_audio(USB)
    moved = FakeDevice(b"{0.0.0}.{usb-port-2}", "USB DAC")
    FakeMedia.outputs = [REALTEK, moved]
    mgr._on_audio_outputs_changed()
    assert player.device is moved


def test_follow_windows_again_forgets_the_choice(manager):
    mgr, player, _ = manager()
    mgr.choose_master_audio(PROJECTOR)
    mgr.choose_master_audio(None)
    assert "audio/master_id" not in FakeSettings.store
    assert not mgr.is_audio_remembered("master")
    assert player.device is REALTEK
