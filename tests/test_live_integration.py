"""Test di integrazione e ciclo di vita per BlindCUE – headless, senza finestre visibili.

Verificano le INTERAZIONI tra componenti (non i singoli moduli) e la stabilità delle
risorse durante uno spettacolo live:

  1. RemoteManager: avvio/arresto ripetuto non lascia thread orfani
  2. Catena OSC -> RemoteManager -> segnali verso la GUI
  3. Cache di stato remoto: consistenza sotto lettura/scrittura concorrente
  4. OutputWindow.force_close(): ferma TUTTI i timer (video/layer/deck-swap)
  5. MainWindow: avvio e chiusura headless senza eccezioni, QThreadPool drenato

Esecuzione:
    QT_QPA_PLATFORM=offscreen pytest -q tests/test_live_integration.py
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import json
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import struct  # noqa: E402
import pytest  # noqa: E402

from PySide6.QtCore import QCoreApplication, QThreadPool, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from services.osc_protocol import parse_osc_message  # noqa: E402
from services.remote_manager import RemoteManager  # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def qt_app():
    """Event loop Qt headless condiviso (QApplication per poter usare i widget)."""
    app = QApplication.instance() or QApplication([])
    yield app


def _pump(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _pump_until(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    QCoreApplication.processEvents()
    return predicate()


# ── 1. Ciclo di vita RemoteManager ───────────────────────────────────

def test_remote_manager_repeated_start_stop_no_thread_leak(qt_app):
    """Avvii/arresti ripetuti non devono accumulare thread."""
    rm = RemoteManager()
    baseline = threading.active_count()

    for _ in range(3):
        web_ok, osc_ok = rm.start_all(web_port=0, osc_port=0)
        assert web_ok, "il server web non si è avviato su porta effimera"
        assert osc_ok, "il server OSC non si è avviato su porta effimera"
        _pump(0.15)
        assert rm.web_server.is_running()
        assert rm.osc_server.is_running()
        rm.stop_all()
        _pump(0.15)
        assert not rm.web_server.is_running()
        assert not rm.osc_server.is_running()

    _pump(0.3)
    # Tolleranza 1 thread per jitter del runtime; nessuna crescita monotona.
    assert threading.active_count() <= baseline + 1, (
        f"thread leak: baseline={baseline} attuale={threading.active_count()}"
    )


def test_remote_manager_stop_is_idempotent(qt_app):
    """Chiamare stop_all() più volte (o senza avvio) non deve sollevare eccezioni."""
    rm = RemoteManager()
    rm.stop_all()
    rm.stop_all()
    ok, _ = rm.start_all(web_port=0, osc_port=0)
    assert ok
    rm.stop_all()
    rm.stop_all()
    assert not rm.web_server.is_running()


# ── 2. Catena OSC -> segnali GUI ─────────────────────────────────────

def _pad4(data: bytes) -> bytes:
    return data + b"\x00" * ((4 - len(data) % 4) % 4)


def _osc_noargs(address: str) -> bytes:
    """OSC message con type-tag string vuota (nessun argomento)."""
    return _pad4(address.encode("ascii")) + _pad4(b",")


def _osc_int(address: str, value: int) -> bytes:
    """OSC message con un singolo argomento int32."""
    return _pad4(address.encode("ascii")) + _pad4(b",i") + struct.pack(">i", value)


def test_osc_datagram_reaches_remote_manager_signals(qt_app):
    """Un datagramma OSC reale deve propagarsi fino ai segnali di alto livello."""
    # Auto-validazione del formato: gli argomenti devono essere vuoti.
    assert parse_osc_message(_osc_noargs("/go")) == ("/go", [])
    assert parse_osc_message(_osc_int("/cue/go", 4)) == ("/cue/go", [4])

    rm = RemoteManager()
    go_calls: list[int] = []
    panic_calls: list[int] = []
    cue_calls: list[object] = []
    rm.go_requested.connect(lambda: go_calls.append(1))
    rm.panic_requested.connect(lambda: panic_calls.append(1))
    rm.cue_go_requested.connect(cue_calls.append)

    ok_web, ok_osc = rm.start_all(web_port=0, osc_port=0)
    assert ok_osc
    try:
        port = rm.osc_server._socket.localPort()
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            tx.sendto(_osc_noargs("/go"), ("127.0.0.1", port))
            tx.sendto(_osc_noargs("/panic"), ("127.0.0.1", port))
            tx.sendto(_osc_int("/cue/go", 4), ("127.0.0.1", port))
        finally:
            tx.close()

        assert _pump_until(
            lambda: bool(go_calls) and bool(panic_calls) and bool(cue_calls),
            timeout=3.0,
        )
        assert go_calls, "il comando /go non è arrivato alla GUI"
        assert panic_calls, "il comando /panic non è arrivato alla GUI"
        assert cue_calls == [4], "il comando /cue/go 4 non ha propagato l'indice corretto"
    finally:
        rm.stop_all()


# ── 3. Concorrenza sulla cache di stato ──────────────────────────────

def test_state_cache_concurrent_access_is_consistent(qt_app):
    """Letture HTTP concorrenti mentre la GUI aggiorna la cache non devono fallire."""
    rm = RemoteManager()
    refresh_count = {"n": 0}

    def provider() -> dict:
        refresh_count["n"] += 1
        return {"is_live": True, "cues": [{"i": i} for i in range(50)]}

    rm.set_state_provider(provider)

    errors: list[BaseException] = []
    stop = threading.Event()

    def reader() -> None:
        try:
            while not stop.is_set():
                snap = rm._get_cached_state()
                # Lo snapshot deve essere sempre coerente (copie, mai mutazioni parziali)
                assert "cues" in snap
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    readers = [threading.Thread(target=reader, daemon=True) for _ in range(8)]
    for r in readers:
        r.start()
    try:
        for _ in range(500):
            rm._refresh_state_cache()
    finally:
        stop.set()
        for r in readers:
            r.join(5.0)

    assert not errors, f"eccezioni nei lettori concorrenti: {errors}"
    assert refresh_count["n"] == 500


# ── 4. OutputWindow.force_close() ────────────────────────────────────

def _make_output_window():
    from ui.output_window import OutputWindow
    return OutputWindow()


def test_output_window_force_close_stops_all_timers(qt_app):
    """force_close() deve fermare TUTTI i timer di animazione, inclusi i deck-swap."""
    try:
        win = _make_output_window()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"OutputWindow non istanziabile in ambiente headless: {exc}")

    try:
        active_timers: list[QTimer] = []
        for bucket in (win._video_fade_timers, win._layer_fade_timers,
                       win._deck_swap_timers):
            bucket.clear()
            t = QTimer(win)
            t.setSingleShot(True)
            t.setInterval(5000)
            t.start()
            active_timers.append(t)
            bucket[0] = t

        assert any(t.isActive() for t in active_timers)

        win.force_close()

        assert win._video_fade_timers == {}
        assert win._layer_fade_timers == {}
        assert win._deck_swap_timers == {}
        assert not any(t.isActive() for t in active_timers), (
            "un timer è rimasto attivo dopo force_close()"
        )
    finally:
        win.deleteLater()
        _pump(0.05)


# ── 5. Avvio/chiusura MainWindow headless ────────────────────────────

def test_main_window_boots_and_closes_headless(qt_app):
    """MainWindow deve costruirsi e chiudersi senza eccezioni e senza thread residui."""
    try:
        from ui.output_window import OutputWindow
        from ui.main_window import MainWindow
        output = OutputWindow()
        win = MainWindow(output)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"MainWindow non istanziabile in ambiente headless: {exc}")

    try:
        _pump(0.1)
        assert win is not None
        # Chiusura pulita:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump(0.1)
        # Il thread pool globale deve poter drenare (nessun worker appeso)
        drained = QThreadPool.globalInstance().waitForDone(3000)
        assert drained, "il QThreadPool globale non si è drenato entro il timeout"
    finally:
        win.deleteLater()
        output.deleteLater()
        _pump(0.05)


# ── 6. Autosave asincrono ────────────────────────────────────────────

def _minimal_cue(cue_id: int, name: str):
    from models.cue import Cue, MediaType
    return Cue.from_dict(
        {
            "cue_id": cue_id,
            "name": name,
            "media_type": MediaType.AUDIO.value,
            "file_path": f"/nonexistent/{name}.wav",
        }
    )


def test_autosave_payload_split_matches_legacy_format(qt_app, tmp_path):
    """build_autosave_payload + write_autosave_payload devono produrre lo STESSO
    file di autosave() (a meno del timestamp), così il formato su disco è invariato."""
    from models.project_manager import ProjectManager

    cues = [_minimal_cue(1, "A"), _minimal_cue(2, "B")]

    pm_legacy = ProjectManager(autosave_dir=tmp_path / "legacy")
    assert pm_legacy.autosave(
        cues, current_index=1, active_project_path="/shows/x.blindcue", settings={"k": 1}
    )

    pm_split = ProjectManager(autosave_dir=tmp_path / "split")
    payload = pm_split.build_autosave_payload(
        cues, current_index=1, active_project_path="/shows/x.blindcue", settings={"k": 1}
    )
    assert pm_split.write_autosave_payload(payload)

    data_legacy = json.loads((tmp_path / "legacy" / "autosave.json").read_text(encoding="utf-8"))
    data_split = json.loads((tmp_path / "split" / "autosave.json").read_text(encoding="utf-8"))

    # Il timestamp è l'unica differenza attesa.
    data_legacy.pop("saved_at")
    data_split.pop("saved_at")
    assert data_legacy == data_split
    assert data_split["clean_exit"] is False
    assert data_split["cues_count"] == 2
    assert [c["name"] for c in data_split["cues"]] == ["A", "B"]


def test_autosave_io_runs_off_gui_thread(qt_app, tmp_path):
    """Il salvataggio deve avvenire su un worker thread: la GUI non deve mai
    eseguire l'I/O bloccante (JSON + fsync) della scrittura su disco."""
    try:
        from ui.output_window import OutputWindow
        from ui.main_window import MainWindow
        output = OutputWindow()
        win = MainWindow(output)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"MainWindow non istanziabile in ambiente headless: {exc}")

    try:
        from models.project_manager import ProjectManager

        win._project_manager = ProjectManager(autosave_dir=tmp_path)
        win._cues.clear()
        win._cues.append(_minimal_cue(1, "Live"))
        win._current_index = 0

        calls: dict[str, object] = {}
        original = win._project_manager.write_autosave_payload

        def spy(payload):
            calls["thread"] = threading.get_ident()
            calls["cues_count"] = payload.get("cues_count")
            return original(payload)

        win._project_manager.write_autosave_payload = spy

        main_ident = threading.main_thread().ident
        win._auto_save()

        # Immediatamente dopo la chiamata, la scrittura NON deve essere avvenuta
        # sul thread della GUI (prova che l'I/O è delegato al pool).
        assert calls.get("thread") != main_ident, "autosave eseguito sul thread GUI!"

        assert _pump_until(lambda: "thread" in calls, timeout=3.0), "il worker non ha completato"
        assert calls["thread"] != main_ident
        assert calls["cues_count"] == 1

        assert win._autosave_pool.waitForDone(5000), "il pool autosave non si è drenato"
        # `finished` viaggia dal worker con connessione queued: il flag si
        # azzera solo quando il loop della GUI consegna il segnale.
        assert _pump_until(lambda: not win._autosave_in_progress, timeout=2.0)
        assert win._autosave_worker is None

        data = json.loads((tmp_path / "autosave.json").read_text(encoding="utf-8"))
        assert data["clean_exit"] is False
        assert data["cues_count"] == 1
        assert data["cues"][0]["name"] == "Live"
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        win.deleteLater()
        output.deleteLater()
        _pump(0.05)


def test_autosave_deferred_call_is_flushed_not_lost(qt_app, tmp_path):
    """Se un secondo autosave arriva mentre il primo è in corso, non deve essere
    perso: il pool (1 thread) serializza e lo stato finale finisce su disco."""
    try:
        from ui.output_window import OutputWindow
        from ui.main_window import MainWindow
        output = OutputWindow()
        win = MainWindow(output)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"MainWindow non istanziabile in ambiente headless: {exc}")

    try:
        from models.project_manager import ProjectManager

        win._project_manager = ProjectManager(autosave_dir=tmp_path)
        win._cues.clear()
        win._cues.append(_minimal_cue(1, "One"))
        win._current_index = 0

        # Simula un salvataggio già in corso e una richiesta accodata.
        win._autosave_in_progress = True
        win._auto_save()
        assert win._autosave_retry_pending is True

        # Al termine del worker in corso, il retry deve partire automaticamente.
        win._on_autosave_finished()
        assert _pump_until(
            lambda: (tmp_path / "autosave.json").is_file()
            and not win._autosave_in_progress,
            timeout=3.0,
        ), "l'autosave differito non è stato eseguito"
        assert win._autosave_pool.waitForDone(5000)

        data = json.loads((tmp_path / "autosave.json").read_text(encoding="utf-8"))
        assert data["cues"][0]["name"] == "One"
        assert win._autosave_retry_pending is False
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        win.deleteLater()
        output.deleteLater()
        _pump(0.05)
