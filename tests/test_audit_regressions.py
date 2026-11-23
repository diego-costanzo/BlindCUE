"""Regression tests for all reliability, safety, and architecture audit fixes.

Run headlessly with:
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -v tests/test_audit_regressions.py
"""

from __future__ import annotations

import ast
import json
import os
import struct
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
BLINDCUE_DIR = ROOT / "blindcue"
if str(BLINDCUE_DIR) not in sys.path:
    sys.path.insert(0, str(BLINDCUE_DIR))

from PySide6.QtCore import QCoreApplication, Qt  # noqa: E402
from PySide6.QtGui import QAction, QImage, QShortcut  # noqa: E402
from PySide6.QtMultimedia import QMediaPlayer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

from engine.device_manager import DeviceManager  # noqa: E402
from engine.hardware_profile import clear_hardware_cache, get_hardware_details  # noqa: E402
from engine.player_live import LivePlayer  # noqa: E402
from engine.show_engine import ShowEngine  # noqa: E402
from engine.sleep_inhibitor import SleepInhibitor  # noqa: E402
from models.cue import Cue, CueStatus, FollowMode, GroupMode, MediaType  # noqa: E402
from models.project_manager import ProjectManager  # noqa: E402
from models.surface import SurfaceDefinition, create_default_surface  # noqa: E402
from services.osc_protocol import parse_osc_message  # noqa: E402
from services.osc_server import OscServer  # noqa: E402
from services.web_server import _HTML_MONITOR_PAGE, _HTML_PAGE, WebRemoteServer  # noqa: E402
from ui.cue_table import ROLE_PHASE_TXT  # noqa: E402
from ui.live_show_view import LiveShowPanel  # noqa: E402
from ui.live_status_panel import LiveStatusPanel  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.output_window import OutputWindow  # noqa: E402
from ui.surface_mapping_dialog import SurfaceMappingDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def _make_png(path: Path, color: int = 0xFF336699) -> Path:
    img = QImage(32, 32, QImage.Format.Format_ARGB32)
    img.fill(color)
    assert img.save(str(path), "PNG")
    return path


def _make_window(qapp, tmp_path: Path):
    out = OutputWindow()
    win = MainWindow(output_window=out)
    win._project_manager = ProjectManager(autosave_dir=tmp_path / "cfg")
    win._autosave_timer.stop()
    return win, out


def _cleanup_window(win: MainWindow, out: OutputWindow) -> None:
    win._force_closing = True
    win.close()
    out.force_close()
    win.deleteLater()
    out.deleteLater()
    QCoreApplication.processEvents()


# ── C1: main.py undefined symbols ────────────────────────────────────────────

def test_main_imports_show_engine_group_mode_and_sleep_inhibitor():
    import main as blindcue_main

    assert blindcue_main.ShowEngine is ShowEngine
    assert blindcue_main.GroupMode is GroupMode
    assert blindcue_main.SleepInhibitor is SleepInhibitor


# ── C2: Zero duplicate shortcuts (Ctrl+B, F5, F7, Shift+F7, Ctrl+Y) ──────────

def test_main_window_has_no_duplicate_shortcuts(qapp, tmp_path):
    win, out = _make_window(qapp, tmp_path)
    try:
        seq_owners: dict[str, list[str]] = {}
        for act in win.findChildren(QAction):
            for seq in act.shortcuts():
                key = seq.toString()
                if key:
                    seq_owners.setdefault(key, []).append(f"QAction:{act.text()}")
        for sc in win.findChildren(QShortcut):
            key = sc.key().toString()
            if key:
                seq_owners.setdefault(key, []).append("QShortcut")

        dups = {k: v for k, v in seq_owners.items() if len(v) > 1}
        assert dups == {}, f"Trovate scorciatoie duplicate (ambigue per Qt): {dups}"

        # Verify Ctrl+B and F5 actions actually work
        blackouts: list[int] = []
        win.blackout_requested.connect(lambda: blackouts.append(1))
        ctrl_b_actions = [
            a for a in win.findChildren(QAction)
            if any(s.toString() == "Ctrl+B" for s in a.shortcuts())
        ]
        assert len(ctrl_b_actions) == 1
        ctrl_b_actions[0].trigger()
        assert len(blackouts) == 1

        f5_actions = [
            a for a in win.findChildren(QAction)
            if any(s.toString() == "F5" for s in a.shortcuts())
        ]
        assert len(f5_actions) == 1
        assert win.is_live_mode() is False
        f5_actions[0].trigger()
        assert win.is_live_mode() is True
    finally:
        _cleanup_window(win, out)


# ── C3: OutputWindow.show_fallback() race condition ──────────────────────────

def test_output_window_show_fallback_cancelled_by_new_cue(qapp, tmp_path):
    img1 = _make_png(tmp_path / "img1.png", 0xFFFF0000)
    img2 = _make_png(tmp_path / "img2.png", 0xFF00FF00)

    out = OutputWindow()
    out.resize(320, 180)
    try:
        out.show_image(1, str(img1))
        assert out._image_containers[1].isVisible()

        finished_called = []
        out.show_fallback(fade_duration_sec=0.12, callback=lambda: finished_called.append(1))

        # New cue arrives BEFORE the 120ms fallback fade completes
        QTest.qWait(25)
        out.show_image(1, str(img2))

        # Wait past the original fallback deadline (120 + 15 ms)
        QTest.qWait(200)

        assert finished_called == [], "Il vecchio callback di show_fallback doveva essere annullato"
        assert out._image_containers[1].isVisible(), "La nuova immagine è stata cancellata dal vecchio fallback timer!"
        assert not out._layer_pixmaps[1].pixmap().isNull()
    finally:
        out.force_close()
        out.deleteLater()
        QCoreApplication.processEvents()


# ── C4: LiveStatusPanel compact lock actually blocks seek ────────────────────

def test_live_status_panel_compact_mode_locks_layer_bars(qapp, tmp_path):
    panel = LiveStatusPanel(compact_live_mode=True)
    try:
        cue = Cue(name="Track", media_type=MediaType.AUDIO, file_path=str(tmp_path / "t.mp3"), layer=1)
        panel.set_layer_live(cue, duration_sec=60.0)
        bar1 = panel._layer_labels[1]
        assert bar1._locked is True
        assert bar1._is_seekable() is False

        panel.set_locked(False)
        assert bar1._locked is False
        assert bar1._is_seekable() is True

        panel.set_locked(True)
        assert bar1._locked is True
        assert bar1._is_seekable() is False
    finally:
        panel.close()
        panel.deleteLater()
        QCoreApplication.processEvents()


# ── C5 & C6: LivePlayer idle-deck seek bug + stalled load watchdog ───────────

def test_live_player_idle_deck_never_seeks_active_live_deck(qapp):
    player = LivePlayer()
    try:
        seeks: list[tuple[int, int]] = []
        orig_p0 = player._player
        orig_p1 = player._standby_player

        class _SpyDeck:
            def __init__(self, idx: int, real):
                self._idx = idx
                self._real = real

            def setPosition(self, ms: int) -> None:
                seeks.append((self._idx, ms))

            def __getattr__(self, name: str):
                return getattr(self._real, name)

        player._player = _SpyDeck(0, orig_p0)
        player._standby_player = _SpyDeck(1, orig_p1)
        # Deck 1 is LIVE; deck 0 is idle standby
        player._active_deck = 1
        player._standby_seek_pending = True
        player._standby_target_ms = 12345

        player._on_deck_status(0, QMediaPlayer.MediaStatus.LoadedMedia)

        assert seeks == [(0, 12345)], f"Il seek standby ha colpito il deck sbagliato: {seeks}"
        assert player._standby_seek_pending is False
    finally:
        player._player = orig_p0
        player._standby_player = orig_p1
        player.shutdown()
        player.deleteLater()
        QCoreApplication.processEvents()


def test_live_player_load_watchdog_recovers_when_playing_state_stuck_in_loading(qapp, monkeypatch):
    player = LivePlayer()
    try:
        player._file_path = "dummy.mp4"
        player._media_progressed = False
        player._watchdog_trials = 0
        player._watchdog_armed = True
        played: list[int] = []

        deck, _ = player._deck_pair()
        monkeypatch.setattr(deck, "mediaStatus", lambda: QMediaPlayer.MediaStatus.LoadingMedia)
        monkeypatch.setattr(deck, "playbackState", lambda: QMediaPlayer.PlaybackState.PlayingState)
        monkeypatch.setattr(deck, "position", lambda: 0)
        monkeypatch.setattr(deck, "stop", lambda: None)
        monkeypatch.setattr(deck, "setSource", lambda _u: None)
        monkeypatch.setattr(deck, "setPosition", lambda _ms: None)
        monkeypatch.setattr(deck, "play", lambda: played.append(1))

        player._recover_stalled_load()

        assert player._watchdog_trials == 1
        assert len(played) == 1
    finally:
        player.shutdown()
        player.deleteLater()
        QCoreApplication.processEvents()


# ── A1: GO button works with QComboBox focus while Space respects inputs ─────

def test_go_button_fires_with_combobox_focus_space_does_not(qapp, tmp_path):
    win, out = _make_window(qapp, tmp_path)
    try:
        f1 = _make_png(tmp_path / "f1.png")
        win._add_cue_from_file(str(f1), MediaType.IMAGE)
        fired: list[int] = []
        win.cue_fired.connect(lambda c: fired.append(c.cue_id))

        win.show()
        combo = QComboBox(win)
        combo.addItem("opt1")
        combo.show()
        combo.setFocus()
        QCoreApplication.processEvents()

        # Simulate focus on combo via monkeypatch if offscreen focus differs
        orig_focus = QApplication.focusWidget
        try:
            QApplication.focusWidget = staticmethod(lambda: combo)
            win._on_go_shortcut()
            assert fired == [], "Spazio non deve lanciare GO mentre una QComboBox ha focus"

            win._on_go()
            assert len(fired) == 1, "Il click sul pulsante GO deve sempre lanciare la cue!"
        finally:
            QApplication.focusWidget = orig_focus
    finally:
        _cleanup_window(win, out)


# ── A2: DeviceManager screen B swap onto screen A ────────────────────────────

def test_device_manager_swap_screen_b_onto_a(qapp, monkeypatch):
    class _FakeScreen:
        def __init__(self, name: str):
            self._name = name

        def name(self) -> str:
            return self._name

    dm = DeviceManager()
    try:
        s_a, s_b = _FakeScreen("HDMI-A-1"), _FakeScreen("HDMI-A-2")
        dm._output_a_screen = s_a
        dm._output_b_screen = s_b
        dm._target_screen = s_a
        monkeypatch.setattr(dm, "get_external_screens", lambda: [s_a, s_b])
        monkeypatch.setattr(dm, "_apply_output_mode", lambda: True)

        assert dm.set_output_screen("B", s_a) is True

        assert dm.get_output_screen("A") is s_b
        assert dm.get_output_screen("B") is s_a
        assert dm.get_target_screen() is s_b
    finally:
        dm.deleteLater()
        QCoreApplication.processEvents()


# ── A3: Delete live cue / New Show / Auto-follow after Undo ──────────────────

def test_delete_live_cue_and_new_show_stop_playback(qapp, tmp_path):
    win, out = _make_window(qapp, tmp_path)
    try:
        f1 = _make_png(tmp_path / "c1.png")
        f2 = _make_png(tmp_path / "c2.png")
        win._add_cue_from_file(str(f1), MediaType.IMAGE)
        win._add_cue_from_file(str(f2), MediaType.IMAGE)

        cleared: list[int] = []
        panics: list[int] = []
        win.layer_clear_requested.connect(lambda l: cleared.append(l))
        win.panic_requested.connect(lambda: panics.append(1))

        # Put cue 0 LIVE and delete it
        win._cues[0].status = CueStatus.LIVE
        win._cue_list.setCurrentRow(0)
        win._on_delete_cue()
        assert cleared == [1], "Eliminare una cue LIVE deve svuotare il suo layer attivo"

        # Put remaining cue LIVE and run Nuovo Show
        win._cues[0].status = CueStatus.LIVE
        win._is_modified = False  # skip save prompt
        win._on_new_show()
        assert len(panics) == 1, "Nuovo Show con cue LIVE deve arrestare la riproduzione"
    finally:
        _cleanup_window(win, out)


def test_show_engine_auto_follow_resolves_after_undo_object_replacement():
    c1 = Cue(name="One", media_type=MediaType.AUDIO, file_path="/a.mp3", follow_mode=FollowMode.AUTO_FOLLOW.value)
    c2 = Cue(name="Two", media_type=MediaType.AUDIO, file_path="/b.mp3")
    # Simulate Undo rebuilding a fresh Cue instance with the same cue_id
    c1_clone = Cue.from_dict(c1.to_dict())
    assert c1_clone is not c1
    assert ShowEngine.auto_follow_target([c1_clone, c2], c1) == 1


# ── A4 & A7: Web Remote SSE fast revoke, XSS escaping, idempotent pause/resume

def test_web_remote_html_escapes_and_case_normalizes():
    assert _HTML_PAGE.count("function escapeHtml(") == 1
    assert _HTML_MONITOR_PAGE.count("function escapeHtml(") == 1
    assert "escapeHtml(c.name)" in _HTML_PAGE
    assert "escapeHtml(c.name)" in _HTML_MONITOR_PAGE
    assert "escapeHtml(c.notes)" in _HTML_MONITOR_PAGE
    assert ".toLowerCase()" in _HTML_PAGE
    assert ".toLowerCase()" in _HTML_MONITOR_PAGE
    assert "⚠ OFFLINE" in _HTML_MONITOR_PAGE


def test_web_remote_sse_terminates_promptly_on_revoke_and_supports_pause_resume(qapp):
    srv = WebRemoteServer(port=0)
    srv.set_pin_protection(True, "654321")
    srv.set_state_provider(lambda: {"show_title": "Test", "cues": []})

    pauses: list[str] = []
    srv.bridge.pause_requested.connect(lambda: pauses.append("pause"))
    srv.bridge.resume_requested.connect(lambda: pauses.append("resume"))
    srv.bridge.pause_toggle_requested.connect(lambda: pauses.append("toggle"))

    assert srv.start(0)
    port = srv._httpd.server_address[1]
    try:
        # 1. URL-encoded PIN and distinct pause/resume actions
        for action in ("pause", "resume", "pause_toggle"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/action?pin={urllib.parse.quote('654321')}",
                data=json.dumps({"action": action}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                assert resp.status == 200
        QCoreApplication.processEvents()
        assert pauses == ["pause", "resume", "toggle"]

        # 2. SSE connection closes promptly (< 1.5s) on revoke_all_sessions()
        closed_evt = threading.Event()

        def _sse_reader():
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/events?pin=654321", timeout=4.0) as resp:
                    # Read initial state chunk
                    line = resp.readline()
                    assert line.startswith(b"data:")
                    # Block until server closes stream
                    while resp.read(1):
                        pass
            finally:
                closed_evt.set()

        t = threading.Thread(target=_sse_reader, daemon=True)
        t.start()

        deadline = time.monotonic() + 2.0
        while srv.get_connected_clients_count() == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert srv.get_connected_clients_count() == 1

        t0 = time.monotonic()
        srv.revoke_all_sessions()
        assert closed_evt.wait(timeout=1.5), "Il thread SSE non è uscito subito su revoke_all_sessions()"
        assert (time.monotonic() - t0) < 1.5
        t.join(timeout=1.0)
    finally:
        srv.stop()


def test_osc_negative_blob_whitelist_empty_ip_and_pause_resume(qapp):
    # Negative blob length must not slice backwards or raise
    bad_pkt = b"/test\x00\x00\x00,b\x00\x00" + struct.pack(">i", -4) + b"\x00\x00\x00\x00"
    addr, args = parse_osc_message(bad_pkt)
    assert addr == "/test"
    assert args == []

    osc = OscServer()
    events: list[str] = []
    osc.go_requested.connect(lambda: events.append("go"))
    osc.pause_requested.connect(lambda: events.append("pause"))
    osc.resume_requested.connect(lambda: events.append("resume"))
    osc.pause_toggle_requested.connect(lambda: events.append("toggle"))

    # Empty sender IP must be rejected when IP whitelist is enabled
    osc.set_security(pin_required=False, allowed_ips=["192.168.1.50"])
    osc._dispatch_command("/go", [], sender_addr="")
    assert events == [], "Un sender IP vuoto ha aggirato la whitelist OSC!"

    osc._dispatch_command("/pause", [], sender_addr="192.168.1.50")
    osc._dispatch_command("/resume", [], sender_addr="192.168.1.50")
    osc._dispatch_command("/pause_toggle", [], sender_addr="192.168.1.50")
    assert events == ["pause", "resume", "toggle"]


# ── A5: LiveShowPanel item reuse & O(1) phase badge update ───────────────────

def test_live_show_panel_reuses_items_and_fast_phase_badge(qapp):
    panel = LiveShowPanel()
    try:
        cues = [
            Cue(name="Intro", media_type=MediaType.AUDIO, file_path="/a.mp3", layer=1),
            Cue(name="Outro", media_type=MediaType.AUDIO, file_path="/b.mp3", layer=2),
        ]
        panel.sync_cues(cues, standby_row=0, known_durations={})
        item_before = panel.live_table.item(0, 2)
        assert item_before is not None

        panel.sync_cues(cues, standby_row=1, known_durations={})
        item_after = panel.live_table.item(0, 2)
        assert item_after is item_before, "sync_cues deve riutilizzare i QTableWidgetItem esistenti"

        ok = panel.update_phase_badge(cues[0].cue_id, "PRE -2.0s")
        assert ok is True
        assert panel.live_table.item(0, 5).data(ROLE_PHASE_TXT) == "PRE -2.0s"
    finally:
        panel.close()
        panel.deleteLater()
        QCoreApplication.processEvents()


# ── A6 & M7: Autosave surfaces + bundled same-size collision + GROUP LOADED ──

def test_autosave_preserves_surfaces_and_bundled_same_size_files_do_not_collide(qapp, tmp_path):
    win, out = _make_window(qapp, tmp_path)
    try:
        f1 = _make_png(tmp_path / "one.png")
        win._add_cue_from_file(str(f1), MediaType.IMAGE)
        custom_surf = SurfaceDefinition(surface_id="wall_left", name="Muro SX", x=0.0, y=0.0, w=0.5, h=1.0)
        win._surfaces.append(custom_surf)

        # Build payload synchronously via _project_manager using same settings dict
        settings = {"surfaces": [s.to_dict() for s in win._surfaces]}
        payload = win._project_manager.build_autosave_payload(win._cues, settings=settings)
        # Mutating caller dict must not mutate deep-copied payload
        settings["surfaces"].clear()
        assert len(payload["settings"]["surfaces"]) == 2
        assert payload["settings"]["surfaces"][1]["surface_id"] == "wall_left"
    finally:
        _cleanup_window(win, out)

    # Bundled save with two same-name, SAME-SIZE, different-content files + GROUP cue
    pm = ProjectManager(autosave_dir=tmp_path / "pm_cfg")
    d1, d2 = tmp_path / "dir1", tmp_path / "dir2"
    d1.mkdir()
    d2.mkdir()
    p1 = d1 / "track.mp3"
    p2 = d2 / "track.mp3"
    p1.write_bytes(b"11111111")  # 8 bytes
    p2.write_bytes(b"22222222")  # 8 bytes — same size, different content!

    cues = [
        Cue(name="T1", media_type=MediaType.AUDIO, file_path=str(p1), layer=1),
        Cue(name="T2", media_type=MediaType.AUDIO, file_path=str(p2), layer=2),
        Cue(name="Scene", media_type=MediaType.GROUP, file_path=""),
    ]
    show = tmp_path / "bundle.blindcue"
    saved, problems, copied = pm.save_project_bundled(show, cues)
    assert saved and not problems and copied == 2

    media_dir = tmp_path / "bundle_media"
    assert (media_dir / "track.mp3").read_bytes() == b"11111111"
    assert (media_dir / "track_2.mp3").read_bytes() == b"22222222"

    loaded, _, _ = pm.load_project(show)
    by_name = {c.name: c for c in loaded}
    assert by_name["Scene"].status == CueStatus.LOADED, "Un gruppo non deve mai risultare OFFLINE"


# ── A9: SleepInhibitor lifecycle ─────────────────────────────────────────────

def test_sleep_inhibitor_acquire_release_linux_mock(monkeypatch):
    class _FakeStdin:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class _FakeProc:
        def __init__(self, *_a, **_k):
            self.pid = 42424
            self.stdin = _FakeStdin()
            self.terminated = False

        def poll(self):
            return 0 if self.terminated else None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.terminated = True
            return 0

        def kill(self):
            self.terminated = True

    monkeypatch.setattr("engine.sleep_inhibitor.sys.platform", "linux")
    monkeypatch.setattr(
        "engine.sleep_inhibitor.shutil.which",
        lambda name: f"/usr/bin/{name}" if name in ("systemd-inhibit", "cat") else None,
    )
    monkeypatch.setattr("engine.sleep_inhibitor.subprocess.Popen", _FakeProc)

    inh = SleepInhibitor()
    assert inh.acquire() is True
    assert inh.is_active is True
    inh.release()
    assert inh.is_active is False


# ── M8: Cue.from_dict sanitizes NaN / out-of-range numeric fields ────────────

def test_cue_from_dict_sanitizes_corrupt_numbers():
    raw = {
        "cue_id": 42,
        "name": "Corrupt",
        "media_type": "VIDEO",
        "file_path": "/tmp/fake.mp4",
        "layer": 99,
        "volume": float("nan"),
        "opacity": 5.0,
        "scale": -3.0,
        "position_x": float("inf"),
        "in_point": 10.0,
        "out_point": 5.0,
        "fade_in": -2.0,
        "fade_out": float("nan"),
        "loop_count": -7,
        "volume_points": [[1.0, 0.5], [float("nan"), 0.5], [2.0, 9.0]],
    }
    cue = Cue.from_dict(raw)
    assert cue.layer == 3
    assert 0.0 <= cue.volume <= 1.0
    assert cue.opacity == 1.0
    assert cue.scale > 0.0
    assert cue.position_x == 0.0
    assert cue.out_point is None
    assert cue.fade_in == 0.0
    assert cue.fade_out == 0.0
    assert cue.loop_count == 0
    assert cue.volume_points == [[1.0, 0.5], [2.0, 1.0]]


# ── M11: SurfaceMappingDialog unique IDs after delete + add + duplicate ──────

def test_surface_mapping_dialog_unique_ids_after_delete(qapp):
    out = OutputWindow()
    dlg = SurfaceMappingDialog(out, surfaces=[create_default_surface()])
    try:
        dlg._add_surface()  # surface_2
        dlg._add_surface()  # surface_3
        # Delete surface_2 (index 1)
        dlg._active_id = dlg._surfaces[1].surface_id
        dlg._delete_surface()
        # Add and duplicate: must never collide with surface_3
        dlg._add_surface()
        dlg._duplicate_surface()

        ids = [s.surface_id for s in dlg._surfaces]
        assert len(ids) == len(set(ids)), f"ID superfici duplicati: {ids}"
    finally:
        dlg.close()
        out.force_close()
        dlg.deleteLater()
        out.deleteLater()
        QCoreApplication.processEvents()


# ── M12: Double-ESC guard in LIVE mode ───────────────────────────────────────

def test_live_mode_escape_requires_double_press(qapp, tmp_path):
    win, out = _make_window(qapp, tmp_path)
    try:
        win.set_live_mode(True)
        panics: list[int] = []
        win.panic_requested.connect(lambda: panics.append(1))

        # Single ESC in LIVE mode must warn, not trigger PANIC
        win._on_escape_pressed()
        assert panics == []
        assert "ESC" in win._status_label.text()

        # Second ESC within 0.6s triggers PANIC
        win._on_escape_pressed()
        assert len(panics) == 1
    finally:
        _cleanup_window(win, out)


def test_design_mode_escape_twice_is_panic_too(qapp, tmp_path):
    """The emergency key works the same in the editor (stage 1 phase C1)."""
    win, out = _make_window(qapp, tmp_path)
    try:
        assert not win.is_live_mode()
        panics: list[int] = []
        stops: list[int] = []
        win.panic_requested.connect(lambda: panics.append(1))
        win._btn_test_stop.clicked.connect(lambda: stops.append(1))

        win._on_escape_pressed()          # one Esc: only the preview stops
        assert panics == [] and stops == [1]
        win._on_escape_pressed()          # the second one within 0.6 s: PANIC
        assert len(panics) == 1

        win._last_esc_press_mono = 0.0
        win._on_escape_pressed()
        win._last_esc_press_mono -= 1.0   # too late for a double press
        win._on_escape_pressed()
        assert len(panics) == 1
    finally:
        _cleanup_window(win, out)


# ── B4 & M3: Engine never imports UI & hardware probe caches cleanly ─────────

def test_engine_has_no_ui_imports_and_hardware_profile_caches():
    engine_dir = BLINDCUE_DIR / "engine"
    violations: list[str] = []
    for py_file in engine_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "ui" or alias.name.startswith("ui."):
                        violations.append(f"{py_file.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and (node.module == "ui" or node.module.startswith("ui.")):
                    violations.append(f"{py_file.name}: from {node.module} import ...")
    assert violations == [], f"Violazioni architetturali engine -> ui: {violations}"

    clear_hardware_cache()
    h1 = get_hardware_details()
    h2 = get_hardware_details()
    assert h1["cpu_model"] == h2["cpu_model"]
    assert h1["gpu_desc"] == h2["gpu_desc"]
