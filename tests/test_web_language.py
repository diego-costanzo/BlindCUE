"""The phone remote and the director monitor follow the program's language (served pages, errors, PIN)."""

from __future__ import annotations

import json
import re
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import i18n  # noqa: E402
import pytest  # noqa: E402
from services.web_server import (  # noqa: E402
    _HTML_MONITOR_PAGE,
    _HTML_PAGE,
    WebRemoteServer,
    _BlindCueHttpRequestHandler,
    _ThreadingHttpServer,
    localize_page,
)


@pytest.fixture()
def polish():
    i18n.set_language("pl")
    try:
        yield
    finally:
        i18n.set_language("it")


@pytest.fixture()
def server():
    """The real request handler on 127.0.0.1 (no LAN, no firewall question)."""
    controller = WebRemoteServer()
    controller.set_state_provider(lambda: {"show_title": "PAUSA", "cues": []})
    httpd = _ThreadingHttpServer(("127.0.0.1", 0), _BlindCueHttpRequestHandler, controller=controller)
    controller._running = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield controller, f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        controller._running = False
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - local test server
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8")


def _dictionary(page: str) -> dict[str, str]:
    match = re.search(r"const I18N = (\{.*?\});", page)
    assert match, "the script's dictionary is missing"
    return json.loads(match.group(1))


def test_served_remote_page_is_polish(polish, server):
    _controller, base = server
    status, page = _get(base + "/")
    assert status == 200
    assert '<html lang="pl">' in page and "{{t:" not in page and "/*I18N*/" not in page
    for text in ("NASTĘPNY", "Nic nie gra", "LISTA CUE", "Poprzedni", "Następny", "POŁĄCZONO",
                 "STEROWANIE CHRONIONE", "GOTOWY", "Pauza", "PANIC", "▶ GO"):
        assert text in page, text
    for italian in ("PROSSIMO IN STANDBY", "Nessun media in onda", "SCALETTA LIVE", ">PREV<", ">NEXT<"):
        assert italian not in page.split("const I18N")[0], italian       # gone from the visible HTML
    assert 'id="cdBox"' in page and "renderTimers(state.timers)" in page and "Zegar komputera" in page  # 2.5
    words = _dictionary(page)
    assert words["— Fine Scaletta —"] == "— Koniec listy —"
    assert words["Riprendi"] == "Wznów" and words["IN PAUSA"] == "PAUZA" and words["LAYER {}"] == "WARSTWA {}"
    assert words["Errore di connessione alla regia"].startswith("Brak połączenia")


def test_served_monitor_page_is_polish(polish, server):
    _controller, base = server
    status, page = _get(base + "/monitor")
    assert status == 200
    assert '<html lang="pl">' in page and "{{t:" not in page
    for text in ("podgląd reżysera", "WARSTWA 1 (TŁO)", "B·WARSTWA 3 (WIERZCH)", "NASTĘPNY CUE", "PEŁNA LISTA CUE",
                 "CUE I UWAGI", "POTEM", "WOLNA", "— bezczynny / czerń —", "tylko do oglądania"):
        assert text in page, text
    assert 'id="cdBox"' in page and "renderTimers(state.timers)" in page and "Następny cue o godzinie" in page
    words = _dictionary(page)
    assert words["○ PRONTA"] == "○ GOTOWY" and words["▶ STANDBY"] == "▶ NASTĘPNY"
    assert words["🎵 AUDIO"] == "🎵 DŹWIĘK" and words["Simultanea"] == "Razem"
    assert words["Tutte le cue eseguite"] == "Wszystkie cue zagrane"


def test_errors_and_pin_answers_are_polish(polish, server):
    controller, base = server
    status, page = _get(base + "/nie-ma-takiej")
    assert status == 404 and "Nie ma takiej strony" in page and "Wróć do pilota" in page
    controller.set_pin_protection(True, "123456")
    status, body = _get(base + "/api/status")
    data = json.loads(body)
    assert data["authenticated"] is False and data["error"] == "Wymagany PIN"
    data = json.loads(_get(base + "/api/status?pin=000000")[1])
    assert data["error"] == "Zły PIN."
    for _ in range(5):
        _get(base + "/api/status?pin=000000")
    data = json.loads(_get(base + "/api/status?pin=000000")[1])
    assert data["error"].startswith("Za dużo błędnych prób. Blokada na ")
    data = json.loads(_get(base + "/api/status?pin=123456")[1])
    assert data["authenticated"] is False                       # still locked out


def test_show_data_is_never_translated(polish, server):
    controller, base = server
    controller.set_pin_protection(False)
    data = json.loads(_get(base + "/api/status")[1])
    assert data["show_title"] == "PAUSA"                         # a show called "PAUSA" keeps its name


def test_italian_and_english_pages():
    page = localize_page(_HTML_PAGE)
    assert '<html lang="it">' in page and "PROSSIMO IN STANDBY" in page and "{{t:" not in page
    assert set(_dictionary(page)) <= {"BlindCUE"}                 # only the product name, never Italian words
    i18n.set_language("en")
    try:
        page = localize_page(_HTML_MONITOR_PAGE)
        assert '<html lang="en">' in page and "FULL CUE LIST" in page and "LAYER 1 (BACKGROUND)" in page
        assert _dictionary(page)["— Fine Scaletta —"] == "— End of the list —"
    finally:
        i18n.set_language("it")
