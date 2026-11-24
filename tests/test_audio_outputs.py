"""Stage 3, item 3.1: logical audio outputs (stage / hall / foldback) mapped per computer.

Fake devices and in-memory settings, as in test_audio_memory: the real
registry and sound cards are never touched.
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
from engine import audio_routes  # noqa: E402
from models.cue import Cue  # noqa: E402


class FakeDevice:
    def __init__(self, dev_id: bytes, name: str) -> None:
        self._id, self._name = dev_id, name

    def id(self) -> bytes:
        return self._id

    def description(self) -> str:
        return self._name

    def isNull(self) -> bool:
        return False


SPEAKERS = FakeDevice(b"{realtek}", "Speakers (Realtek)")
HALL = FakeDevice(b"{usb-hall}", "USB Hall")
PHONES = FakeDevice(b"{usb-phones}", "USB Foldback")


class FakeMedia:
    outputs: list[FakeDevice] = []
    default: FakeDevice = SPEAKERS

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
        self.device, self.gain = None, None

    def set_audio_device(self, device) -> None:
        self.device = device

    def set_output_gain(self, gain) -> None:
        self.gain = gain


@pytest.fixture()
def mgr(monkeypatch):
    QApplication.instance() or QApplication([])
    FakeSettings.store = {}
    FakeMedia.outputs = [SPEAKERS, HALL, PHONES]
    FakeMedia.default = SPEAKERS
    monkeypatch.setattr(dm, "QSettings", FakeSettings)
    manager = dm.DeviceManager()
    monkeypatch.setattr(dm, "QMediaDevices", FakeMedia)
    manager._master_device = manager._resolve_audio("master")
    manager.players = [FakePlayer(), FakePlayer()]
    manager.register_live_players(manager.players)
    return manager


def test_rules_without_devices():
    assert audio_routes.normalize_output("HALL") == "hall" and audio_routes.normalize_output("x") == "stage"
    assert audio_routes.normalize_fallback("stage", "stage") == "default"      # never falls back on itself
    assert audio_routes.normalize_fallback("foldback", None) == "mute"
    assert audio_routes.trim_gain(-6) == pytest.approx(0.501, abs=0.001) and audio_routes.trim_gain(12) == 1.0
    found = {"hall-id": "HALL-DEV"}

    def find(choice):
        return found.get(choice[0])

    choices = {"stage": None, "hall": ("hall-id", "USB Hall"), "foldback": ("gone", "Phones")}
    assert audio_routes.resolve("hall", choices, {}, find) == audio_routes.Route("HALL-DEV", False, "hall")
    fold = audio_routes.resolve("foldback", choices, {}, find)
    assert fold.muted and fold.missing == "Phones"                           # private track never to the hall
    assert audio_routes.resolve("foldback", choices, {"foldback": "stage"}, find).via == "stage"
    assert audio_routes.resolve("stage", choices, {}, find) == audio_routes.Route(None, False, "stage")
    assert audio_routes.normalize_fallback("stage", "mute") == "default"       # the stage is never muted by a rule
    assert audio_routes.resolve("mute", choices, {}, find).muted
    data = audio_routes.export_map({"hall": {"id": "a", "name": "b", "fallback": "mute", "trim_db": -50}})
    assert audio_routes.import_map(data)["hall"] == {"id": "a", "name": "b", "fallback": "mute", "trim_db": -30.0}
    for bad in ({"nope": 1}, {"outputs": {}}, {"blindcue_audio_outputs": 99, "outputs": data["outputs"]},
                {"blindcue_audio_outputs": 1, "outputs": {"moon": {}}}):
        with pytest.raises(ValueError):
            audio_routes.import_map(bad)


def test_cue_field_round_trip():
    cue = Cue.from_dict({"cue_id": 1, "name": "a", "media_type": "AUDIO", "file_path": "/x.wav",
                         "audio_output": "foldback"})
    assert Cue.from_dict(cue.to_dict()).audio_output == "foldback"
    assert Cue.from_dict({**cue.to_dict(), "audio_output": "moon"}).audio_output == "stage"
    assert Cue(name="b", media_type=cue.media_type, file_path="/y.wav").audio_output == "stage"


def test_players_follow_the_map_and_unplugging(mgr):
    one, two = mgr.players
    assert one.device is SPEAKERS and one.gain == 1.0                       # nothing set: system default
    mgr.set_output_device("hall", HALL)
    mgr.set_output_rule("hall", trim_db=-6)
    route = mgr.route_player(one, "hall")
    assert one.device is HALL and one.gain == pytest.approx(0.501, abs=0.001) and route.via == "hall"
    mgr.route_player(two, "foldback")                                        # not set here: muted
    assert two.gain == 0.0
    mgr.set_output_device("foldback", PHONES)
    assert two.device is PHONES and two.gain == 1.0                          # the map changed: re-routed
    FakeMedia.outputs = [SPEAKERS]                                           # both USB cards unplugged
    mgr._on_audio_outputs_changed()
    assert one.device is SPEAKERS and two.gain == 0.0                        # hall -> stage, foldback -> mute
    FakeMedia.outputs = [SPEAKERS, HALL, PHONES]
    mgr._on_audio_outputs_changed()
    assert one.device is HALL and two.device is PHONES and two.gain == 1.0   # back again


def test_review_stage_stays_put_and_muted_keeps_its_device(mgr):
    one, two = mgr.players
    FakeMedia.default = HALL                                                 # Windows picks another default
    mgr._on_audio_outputs_changed()
    assert one.device is SPEAKERS                                            # nothing chosen: stage stays
    mgr.set_output_device("foldback", PHONES)
    mgr.route_player(two, "foldback")
    FakeMedia.outputs = [SPEAKERS, HALL]                                     # the foldback card falls out
    mgr._on_audio_outputs_changed()
    assert two.gain == 0.0 and two.device is PHONES                          # silent, never moved to the hall
    assert "USB Foldback" in mgr.audio_notice_text()


def test_export_and_import_the_map(mgr):
    mgr.set_output_device("hall", HALL)
    mgr.set_output_rule("foldback", fallback="stage", trim_db=-3)
    data = mgr.export_outputs()
    assert data["outputs"]["hall"]["name"] == "USB Hall" and data["outputs"]["foldback"]["fallback"] == "stage"
    FakeSettings.store = {}
    mgr.import_outputs(data)
    assert mgr.output_trim_db("foldback") == -3.0 and mgr.resolve_output("hall").device is HALL
    mgr.import_outputs({"blindcue_audio_outputs": 1, "outputs": {"foldback": {"fallback": "mute"}}})
    assert mgr.resolve_output("hall").device is HALL and mgr.output_fallback("foldback") == "mute"  # hall kept


def test_dialog_sets_the_map_and_is_read_only_in_the_show(mgr):
    from ui.audio_outputs_dialog import AudioOutputsDialog

    dlg = AudioOutputsDialog(mgr)
    device, fallback, trim, _test = dlg._rows["hall"]
    device.setCurrentIndex(device.findText("USB Hall"))
    trim.setValue(-4.0)
    assert mgr.resolve_output("hall").device is HALL and mgr.output_trim_db("hall") == -4.0
    assert "USB Hall" in dlg.lbl_status.text()
    FakeMedia.outputs = [SPEAKERS]                                   # unplugged: the choice is kept, marked
    dlg._fill()
    assert "USB Hall" in dlg._rows["hall"][0].currentText() and mgr.output_choices()["hall"] is not None
    FakeMedia.outputs = [SPEAKERS, HALL, PHONES]
    busy = AudioOutputsDialog(mgr, busy=lambda: True)
    busy._test("stage")
    assert busy._player.source().isEmpty()                         # no test tone over the show
    busy.deleteLater()
    locked = AudioOutputsDialog(mgr, locked=True)
    assert not locked._rows["stage"][0].isEnabled() and not locked.btn_import.isEnabled()
    dlg.deleteLater()
    locked.deleteLater()


def test_readiness_row_only_when_the_show_uses_hall_or_foldback():
    from engine.readiness import AUDIO_OUTS, OK, PROBLEM, Facts, checks

    assert not [c for c in checks(Facts()) if c.key == AUDIO_OUTS]          # only the stage: no row
    good = [c for c in checks(Facts(outputs=(("Sala", "USB Hall", True, 2),))) if c.key == AUDIO_OUTS]
    bad = [c for c in checks(Facts(outputs=(("Spie", "muto", False, 1),))) if c.key == AUDIO_OUTS]
    assert good[0].state == OK and bad[0].state == PROBLEM
