"""Suite di robustezza live per BlindCUE – headless, senza finestre grafiche.

Copre:
  1. Stress OSC (datagrammi UDP malformati / vuoti / oversized / con tipi errati)
  2. Chaos Web Remote (HTTP concorrente + disconnessione improvvisa dei client SSE)
  3. Resilienza media (file inesistente / 0 byte / corrotto, zero processi zombie)
  4. Caricamento progetto (JSON corrotto, cue con percorsi mancanti)

Esecuzione:
    QT_QPA_PLATFORM=offscreen pytest -q tests/test_live_robustness.py
"""

from __future__ import annotations

import http.client
import json
import math
import os
import shutil
import socket
import struct
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest  # noqa: E402

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engine import audio_analyzer  # noqa: E402
from models.project_manager import ProjectManager  # noqa: E402
from services.osc_protocol import parse_osc_message  # noqa: E402
from services.osc_server import OscServer  # noqa: E402
from services.web_server import WebRemoteServer  # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def qt_core_app():
    """Event loop Qt headless (offscreen): QApplication così anche i widget test funzionano."""
    app = QApplication.instance() or QApplication([])
    yield app


def _pump_until(predicate, timeout: float = 5.0) -> bool:
    """Processa l'event loop Qt fino a che il predicato è vero o scade il timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    QCoreApplication.processEvents()
    return predicate()


# ── 1. STRESS TEST OSC ───────────────────────────────────────────────

def _hostile_osc_payloads() -> list[bytes]:
    """Costruisce 250+ datagrammi ostili: vuoti, troncati, oversized, tipi errati."""
    payloads: list[bytes] = [
        b"",                                          # datagramma vuoto
        b"\x00",                                      # solo terminatore
        b"\x00\x00\x00",                              # troppo corto
        b"no-slash\x00\x00\x00\x00",                  # address senza '/'
        b"/go",                                       # terminatore mancante
        b"/go\x00\x00,",                              # type tags tronchi
        b"/go\x00\x00,i\x00\x00",                     # argomento int senza payload
        b"/go\x00\x00,f\x00\x00\x00",                 # payload float troncato
        b"/go\x00\x00,b\x00\x00\x00\x00\x10",         # blob più lungo del datagramma
        b"/cue/\x00\x00\x00\x00,i\x00\x00\xff\xff\xff\xff",
        b"/" + b"a" * 40000 + b"\x00",                # address oversized (40 KB)
        struct.pack(">i", -1),                        # binario grezzo
        bytes(range(256)) * 4,                        # binario denso
    ]
    for i in range(80):
        payloads.append(b"/cue/%d/go\x00\x00\x00,i\x00\x00" % i)
        payloads.append(b"/volume\x00,s\x00\x00fake\x00\x00")
        payloads.append(b"/volume\x00,f\x00\x00" + struct.pack(">f", float("nan")))
    return payloads


def test_osc_stress_malformed_packets_never_fatal(qt_core_app):
    """100+ pacchetti UDP ostili non devono mai sollevare eccezioni o congelare il server."""
    server = OscServer()
    volumes: list[float] = []
    seen: list[tuple] = []
    server.volume_change_requested.connect(volumes.append)
    server.command_received.connect(lambda a, b, c: seen.append((a, b, c)))

    assert server.start(0), "OscServer non ha potuto agganciare una porta UDP effimera"
    try:
        port = server._socket.localPort()
        payloads = _hostile_osc_payloads()
        expected = sum(1 for p in payloads if parse_osc_message(p)[0])
        assert expected > 200, "il corpus ostile deve contenere >200 pacchetti validi"

        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Invio a blocchi: si drena l'event loop Qt tra un blocco e l'altro così il
            # buffer di ricezione UDP non viene saturato (perdita deterministica ~zero).
            for start in range(0, len(payloads), 20):
                for payload in payloads[start:start + 20]:
                    tx.sendto(payload, ("127.0.0.1", port))
                for _ in range(4):
                    QCoreApplication.processEvents()
                    time.sleep(0.005)
        finally:
            tx.close()

        _pump_until(lambda: server._packet_count >= expected * 0.9, timeout=5.0)
        # UDP è lossy per natura: si tollera una piccola perdita, mai un'eccezione
        assert server._packet_count >= expected * 0.9
        assert server.is_running()
        assert server.get_last_command_info()
        # NaN/inf non devono mai raggiungere il motore audio come volume valido
        assert all(math.isfinite(v) for v in volumes), f"volume non finito emesso: {volumes}"
        assert all(0.0 <= v <= 1.0 for v in volumes)
    finally:
        server.stop()
    assert not server.is_running()


def test_osc_dispatch_fuzz_direct(qt_core_app):
    """Fuzz sul dispatch diretto: tipi errati devono essere ignorati, non far crashare nulla."""
    server = OscServer()
    cases = [
        ("/" + "x" * 5000, []),
        ("/cue/go", [b"\x00\x01\x02\x03"]),
        ("/cue/go", [None]),
        ("/cue/go", [1e308]),
        ("/cue/99999999999999999999/go", []),
        ("/volume", ["abc"]),
        ("/volume", [float("nan")]),
        ("/volume", [float("inf")]),
        ("/volume", [None]),
        ("/auth", [b"\xff\xfe"]),
        ("/cue//go", []),
        ("/cue/%2e%2e/go", []),
    ]
    for address, args in cases:
        server._dispatch_command(address, args, "127.0.0.1")
    assert True  # arrivare qui senza eccezioni è l'assertion


# ── 2. CHAOS WEB REMOTE ──────────────────────────────────────────────

def _http_request(port: int, method: str, path: str, body: bytes | None = None,
                  timeout: float = 3.0) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        headers = {"Content-Type": "application/json"} if body is not None else {}
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def test_web_remote_chaos_concurrent_http_and_sse_abort(qt_core_app):
    """HTTP concorrente + disconnessioni RST improvvise dei client SSE non devono uccidere il server."""
    server = WebRemoteServer(port=0)
    server.set_pin_protection(False)
    server.set_state_provider(
        lambda: {"show_title": "Chaos", "is_live": False, "cues": [{"name": "c1"}]}
    )
    assert server.start(0), "il web remote non ha potuto agganciare una porta effimera"
    port = server._httpd.server_address[1]

    try:
        bodies = [
            b"", b"{", b"null", b"[]", b'"plain-string"',
            b"\xff\xfe\x00binary",
            b'{"action": 12345, "cue_id": {"bad": true}}',
            b'{"action": "go", "cue_id": null}',
            b'{"action": "cue_go", "cue_id": "' + b"x" * 100000 + b'"}',
        ]

        def hammer() -> None:
            for body in bodies:
                try:
                    _http_request(port, "POST", "/api/action", body)
                except Exception:  # noqa: BLE001 - il chaos è l'obiettivo del test
                    pass

        workers = [threading.Thread(target=hammer, daemon=True) for _ in range(8)]
        for w in workers:
            w.start()
        for w in workers:
            w.join(10.0)
        assert not any(w.is_alive() for w in workers)

        # Client SSE che si disconnettono brutalmente con RST
        sse_socks: list[socket.socket] = []
        for _ in range(5):
            s = socket.create_connection(("127.0.0.1", port), timeout=3)
            s.sendall(
                b"GET /api/events HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                b"Accept: text/event-stream\r\n\r\n"
            )
            s.recv(1024)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            sse_socks.append(s)

        assert _pump_until(lambda: server.get_connected_clients_count() >= 5, timeout=3.0)

        for s in sse_socks:
            s.close()  # RST -> BrokenPipeError / ConnectionResetError lato server

        for _ in range(25):
            server.broadcast_state()
            time.sleep(0.02)

        assert _pump_until(lambda: server.get_connected_clients_count() == 0, timeout=6.0)
        assert server.get_connected_clients_count() == 0
        assert server.is_running()
        assert server._thread is not None and server._thread.is_alive()

        # Il server deve restare pienamente funzionante dopo il chaos
        status, payload = _http_request(port, "GET", "/api/status")
        assert status == 200
        data = json.loads(payload.decode("utf-8"))
        assert data.get("authenticated") is True
        assert data.get("cues") == [{"name": "c1"}]

        html_status, _ = _http_request(port, "GET", "/")
        assert html_status == 200

        bad_status, _ = _http_request(port, "POST", "/api/action", b"[]")
        assert bad_status == 400
    finally:
        server.stop()
    assert not server.is_running()


# ── 3. RESILIENZA MEDIA ──────────────────────────────────────────────

def _zombie_children() -> list[int]:
    """Ritorna i PID dei figli zombie di questo processo (solo Linux)."""
    if not sys.platform.startswith("linux"):
        return []
    zombies: list[int] = []
    me = os.getpid()
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", encoding="utf-8", errors="replace") as f:
                fields = f.read().rsplit(")", 1)[1].split()
            state, ppid = fields[0], int(fields[1])
        except (OSError, IndexError, ValueError):
            continue
        if state == "Z" and ppid == me:
            zombies.append(int(entry))
    return zombies


def test_waveform_missing_binary_returns_none(monkeypatch, tmp_path):
    """Se ffmpeg non esiste, l'analisi deve ritornare None senza sollevare eccezioni."""
    def _boom(*_args, **_kwargs):
        raise FileNotFoundError("ffmpeg not found")

    if hasattr(audio_analyzer, "_resolve_binary"):
        monkeypatch.setattr(audio_analyzer, "_resolve_binary", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(audio_analyzer.subprocess, "Popen", _boom)

    analyzer = audio_analyzer.WaveformAnalyzer(str(tmp_path / "missing.mp3"))
    assert analyzer._decode_pcm() is None


def test_waveform_analyzer_reports_container_duration(monkeypatch):
    """La durata ffprobe arriva subito, anche quando il file non ha traccia audio.

    La Forma d'Onda usa questo valore per abilitare taglio/zoom alla prima
    selezione, senza dipendere da QMediaPlayer (che emette durationChanged una
    sola volta per sorgente).
    """
    analyzer = audio_analyzer.WaveformAnalyzer("dummy.mp4")
    durations: list[float] = []
    errors: list[str] = []
    analyzer.signals.duration_ready.connect(lambda _path, dur: durations.append(dur))
    analyzer.signals.error.connect(lambda _path, msg: errors.append(msg))

    monkeypatch.setattr(analyzer, "_get_duration", lambda: 12.5)
    monkeypatch.setattr(analyzer, "_decode_pcm", lambda: None)

    analyzer.run()

    assert durations == [12.5]
    assert errors, "un file senza audio deve comunque segnalare l'errore di decodifica"


def test_waveform_kills_hung_ffmpeg(monkeypatch):
    """Un ffmpeg appeso deve essere killato, non lasciato in attesa indefinita."""
    calls = {"kill": 0, "communicate": 0}

    class _FakeProc:
        def __init__(self, *_a, **_k):
            self._done = False

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def communicate(self, timeout=None):
            calls["communicate"] += 1
            if calls["communicate"] == 1:
                raise audio_analyzer.subprocess.TimeoutExpired("ffmpeg", timeout)
            self._done = True
            return b"", None

        def kill(self):
            calls["kill"] += 1
            self._done = True

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0 if self._done else None

    if hasattr(audio_analyzer, "_resolve_binary"):
        monkeypatch.setattr(audio_analyzer, "_resolve_binary", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(audio_analyzer.subprocess, "Popen", _FakeProc)

    analyzer = audio_analyzer.WaveformAnalyzer("dummy.mp3")
    assert analyzer._decode_pcm() is None
    assert calls["kill"] >= 1, "l'ffmpeg appeso non è stato killato"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg non installato")
def test_real_ffmpeg_bad_files_leave_no_zombies(monkeypatch, tmp_path):
    """File inesistente / 0 byte / corrotto: sempre None e zero figli zombie ffmpeg."""
    class _FakeQSP:
        class StandardLocation:
            CacheLocation = "cache"

        @staticmethod
        def writableLocation(_loc):
            return str(tmp_path / "cache")

    monkeypatch.setattr(audio_analyzer, "QStandardPaths", _FakeQSP)

    empty = tmp_path / "empty.mp3"
    empty.write_bytes(b"")
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(os.urandom(8192))
    missing = tmp_path / "does_not_exist.wav"

    for target in (missing, empty, corrupt):
        before = _zombie_children()
        assert audio_analyzer.WaveformAnalyzer(str(target))._decode_pcm() is None
        assert audio_analyzer.scan_file_loudness(str(target)) is None
        assert audio_analyzer.render_normalized_media(str(target)) is None
        assert _zombie_children() == before, f"zombie ffmpeg lasciato dopo {target.name}"


# ── 4. CARICAMENTO PROGETTO ──────────────────────────────────────────

def test_project_manager_rejects_corrupted_json(tmp_path):
    pm = ProjectManager(autosave_dir=tmp_path / "cfg")
    bad = tmp_path / "broken.blindcue"
    bad.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(ValueError):
        pm.load_project(bad)


def test_project_manager_rejects_non_dict_root(tmp_path):
    pm = ProjectManager(autosave_dir=tmp_path / "cfg")
    bad = tmp_path / "list.blindcue"
    bad.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError):
        pm.load_project(bad)


def test_project_manager_missing_file(tmp_path):
    pm = ProjectManager(autosave_dir=tmp_path / "cfg")
    with pytest.raises(FileNotFoundError):
        pm.load_project(tmp_path / "nope.blindcue")


def test_project_manager_skips_bad_cues_without_blocking_startup(tmp_path):
    """Cue corrotte, path traversal e media mancanti non devono bloccare l'avvio dello show."""
    pm = ProjectManager(autosave_dir=tmp_path / "cfg")
    media = tmp_path / "ok.wav"
    media.write_bytes(b"RIFF....WAVEfmt ")

    show = tmp_path / "show.blindcue"
    show.write_text(
        json.dumps(
            {
                "app": "BlindCue",
                "schema_version": "1.0",
                "current_cue_index": "not-an-int",
                "settings": "broken-settings",
                "cues": [
                    {"name": "ok", "media_type": "AUDIO", "file_path": str(media),
                     "cue_id": 1, "status": "LIVE"},
                    {"name": "bad-status", "media_type": "AUDIO", "file_path": str(media),
                     "cue_id": 2, "status": "NOT_A_STATUS"},
                    {"name": "traversal", "media_type": "AUDIO",
                     "file_path": "../../etc/passwd", "cue_id": 3},
                    {"name": "missing-media", "media_type": "AUDIO",
                     "file_path": "gone.mp3", "cue_id": 4},
                    {"name": "not-a-cue"},
                ],
            }
        ),
        encoding="utf-8",
    )

    cues, index, settings = pm.load_project(show)

    assert isinstance(index, int)
    assert isinstance(settings, dict)
    by_name = {c.name: c for c in cues}
    assert "ok" in by_name
    assert by_name["ok"].status.value == "LOADED"
    assert by_name["missing-media"].status.value == "OFFLINE"
    assert "traversal" not in by_name, "una cue con path traversal deve essere saltata, mai caricata"
    assert "bad-status" not in by_name
    assert "not-a-cue" not in by_name


def test_bundled_save_copies_media_and_uses_relative_paths(tmp_path):
    """Il salvataggio 'portatile' copia i media accanto allo show e usa percorsi relativi."""
    from models.cue import Cue, MediaType

    pm = ProjectManager(autosave_dir=tmp_path / "cfg")
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    folder_a.mkdir()
    folder_b.mkdir()
    # Same file name in two different folders: both must survive the copy.
    clip_a = folder_a / "clip.mp4"
    clip_b = folder_b / "clip.mp4"
    clip_a.write_bytes(b"AAAA")
    clip_b.write_bytes(b"BBBBBB")
    cues = [
        Cue(name="A", media_type=MediaType.VIDEO, file_path=str(clip_a), layer=1),
        Cue(name="B", media_type=MediaType.VIDEO, file_path=str(clip_b), layer=2),
        Cue(name="G", media_type=MediaType.GROUP, file_path=""),
    ]

    show = tmp_path / "show.blindcue"
    saved, problems, copied = pm.save_project_bundled(show, cues, current_index=0)

    assert saved and not problems and copied == 2
    media_dir = tmp_path / "show_media"
    assert sorted(p.name for p in media_dir.iterdir()) == ["clip.mp4", "clip_2.mp4"]
    assert clip_a.read_bytes() == b"AAAA" and clip_b.exists(), "gli originali non si toccano"

    data = json.loads(show.read_text(encoding="utf-8"))
    paths = {c["name"]: c["file_path"] for c in data["cues"]}
    assert paths["A"] == "show_media/clip.mp4"
    assert paths["B"] == "show_media/clip_2.mp4"
    assert not any(p.startswith("/") for p in (paths["A"], paths["B"]))

    loaded, _idx, _settings = pm.load_project(show)
    by_name = {c.name: c for c in loaded}
    assert by_name["A"].status.value == "LOADED"
    assert by_name["B"].status.value == "LOADED"
    assert str(tmp_path) in by_name["A"].file_path


def test_bundled_save_reports_missing_media_and_keeps_it_linked(tmp_path):
    """Un media mancante non blocca il salvataggio: viene segnalato e resta assoluto."""
    from models.cue import Cue, MediaType

    pm = ProjectManager(autosave_dir=tmp_path / "cfg")
    gone = tmp_path / "gone.mp3"
    cues = [Cue(name="Manca", media_type=MediaType.AUDIO, file_path=str(gone), layer=1)]
    show = tmp_path / "show.blindcue"

    saved, problems, copied = pm.save_project_bundled(show, cues)

    assert saved and copied == 0
    assert problems and "Manca" in problems[0]
    data = json.loads(show.read_text(encoding="utf-8"))
    assert data["cues"][0]["file_path"] == str(gone)



def test_bundled_show_stays_portable_after_reopen_and_move(tmp_path):
    """Reopened bundle: detected as portable, and a moved copy still finds its media."""
    from models.cue import Cue, MediaType

    pm = ProjectManager(autosave_dir=tmp_path / "cfg")
    src = tmp_path / "src"
    src.mkdir()
    song = src / "song.mp3"
    song.write_bytes(b"MP3")
    show = tmp_path / "pc1" / "show.blindcue"
    show.parent.mkdir()
    cues = [Cue(name="S", media_type=MediaType.AUDIO, file_path=str(song), layer=2)]
    assert pm.save_project_bundled(show, cues)[0]

    loaded, _i, _s = pm.load_project(show)
    assert pm.uses_media_archive(show, loaded), "Ctrl+S must keep the bundle portable"

    # An older plain save wrote absolute paths into the archive: after moving
    # the folder to another PC the copy in "<name>_media/" must still be found.
    pm.save_project(show, loaded)
    moved = tmp_path / "pc2"
    shutil.copytree(show.parent, moved)
    shutil.rmtree(show.parent)
    again, _i, _s = pm.load_project(moved / "show.blindcue")
    assert again[0].status.value == "LOADED"
    assert Path(again[0].file_path).parent.name == "show_media"

    plain = [Cue(name="P", media_type=MediaType.AUDIO, file_path=str(song), layer=2)]
    assert not pm.uses_media_archive(moved / "show.blindcue", plain)


def test_bundled_save_archives_custom_layer0_image(tmp_path):
    """The custom Layer 0 image travels with the bundle and is found after a move."""
    from models.cue import Cue, MediaType

    pm = ProjectManager(autosave_dir=tmp_path / "cfg")
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"PNG")
    show = tmp_path / "pc1" / "show.blindcue"
    show.parent.mkdir()
    cues = [Cue(name="I", media_type=MediaType.IMAGE, file_path=str(logo), layer=1)]

    saved, problems, _copied = pm.save_project_bundled(
        show, cues, settings={"layer0_image": str(logo)}
    )
    assert saved and not problems
    data = json.loads(show.read_text(encoding="utf-8"))
    assert data["settings"]["layer0_image"] == "show_media/logo.png"

    moved = tmp_path / "pc2"
    shutil.copytree(show.parent, moved)
    _cues, _i, settings = pm.load_project(moved / "show.blindcue")
    assert Path(settings["layer0_image"]) == (moved / "show_media" / "logo.png").resolve()
