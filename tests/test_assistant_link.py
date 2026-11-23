"""Stage 1M, M2: the assistant changes the show open in the program (local link)."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _in_thread(fn):
    """Run *fn* (blocking socket calls) while the window keeps serving the link."""
    box: dict = {}

    def run():
        try:
            box["value"] = fn()
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc
    worker = threading.Thread(target=run)
    worker.start()
    deadline = time.monotonic() + 30
    while worker.is_alive() and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.002)
    worker.join(1)
    if "error" in box:
        raise box["error"]
    return box.get("value")


@pytest.fixture()
def setup(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    media = tmp_path / "media"
    media.mkdir()
    for name in ("song.mp3", "photo.jpg"):
        (media / name).write_bytes(b"\0" * 64)
    output = OutputWindow()
    win = MainWindow(output)
    try:
        yield win, media, tmp_path
    finally:
        win._assistant_stop()
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_off_by_default_and_on_by_the_teacher(setup):
    win, media, home = setup
    info = home / ".config" / "blindcue" / "assistant.json"
    assert not win._act_assistant.isChecked() and win._assistant_server is None and not info.exists()
    win._act_assistant.setChecked(True)
    data = json.loads(info.read_text(encoding="utf-8"))
    assert data["port"] > 0 and len(data["token"]) > 20
    win._act_assistant.setChecked(False)
    assert not info.exists() and win._assistant_server is None


def test_the_assistant_edits_the_open_show(setup):
    from mcp_server.program_link import ProgramSession
    from mcp_server.show_tools import AccessPolicy, ToolError

    win, media, home = setup
    win._act_assistant.setChecked(True)
    policy = AccessPolicy([media])
    link = _in_thread(lambda: ProgramSession(policy))
    assert link.hello["program"] == "BlindCue" and link.hello["mode"] == "preparation"
    added = _in_thread(lambda: link.add_media_cue(str(media / "song.mp3"), fields={"name": "Song", "fade_in": 2}))
    assert [c.name for c in win._cues] == ["Song"] and win._cues[0].layer == 2
    assert win._cue_list.currentRow() == 0 and win._is_modified
    assert win._undo.can_undo                                         # Ctrl+Z takes it back
    _in_thread(lambda: link.update_cue(added["cue_id"], {"volume": 0.5}))
    assert win._cues[0].volume == 0.5
    assert [r["name"] for r in _in_thread(link.list_cues)] == ["Song"]
    assert "'Song'" in win._assistant_changes[0][1] and len(win._assistant_changes) == 2
    with pytest.raises(ToolError):                                    # outside the allowed folders
        _in_thread(lambda: link.add_media_cue(str(home / "elsewhere.mp3")))
    with pytest.raises(ToolError):                                    # unknown argument names
        _in_thread(lambda: link._request("update_cue", {"cue_id": added["cue_id"], "fields": {}, "x": 1}))

    win.set_live_mode(True)                                           # the show: read only
    assert [r["name"] for r in _in_thread(link.list_cues)] == ["Song"]
    with pytest.raises(ToolError):
        _in_thread(lambda: link.add_media_cue(str(media / "photo.jpg")))
    assert len(win._cues) == 1
    win.set_live_mode(False)
    link.close()


def test_a_wrong_token_is_refused(setup):
    from mcp_server.program_link import ProgramSession
    from mcp_server.show_tools import AccessPolicy, ToolError

    win, media, home = setup
    win._act_assistant.setChecked(True)
    info = home / ".config" / "blindcue" / "assistant.json"
    data = json.loads(info.read_text(encoding="utf-8"))
    fake = home / "fake.json"
    fake.write_text(json.dumps({"port": data["port"], "token": "guess"}), encoding="utf-8")
    with pytest.raises(ToolError):
        _in_thread(lambda: ProgramSession(AccessPolicy([media]), info_file=fake))
    win._act_assistant.setChecked(False)
    with pytest.raises(ToolError):                                    # switched off: no link at all
        _in_thread(lambda: ProgramSession(AccessPolicy([media])))


def test_dialog_makes_the_extension_and_mirrors_the_switch(setup, monkeypatch):
    import zipfile

    from ui import assistant_dialog

    win, media, home = setup
    opened: list = []
    monkeypatch.setattr(assistant_dialog, "_documents", lambda: home / "Documents")
    monkeypatch.setattr(assistant_dialog.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url) or True))
    dlg = assistant_dialog.AssistantDialog(win)
    dlg.btn_claude.click()
    made = home / "Documents" / "BlindCue" / "blindcue-show-assistant.mcpb"
    assert made.is_file() and len(opened) == 1
    assert "manifest.json" in zipfile.ZipFile(made).namelist()
    dlg.chk_allow.setChecked(True)
    assert win._act_assistant.isChecked() and win._assistant_server is not None
    dlg.btn_copy.click()
    assert '"mcpServers"' in QApplication.clipboard().text()
    dlg.chk_allow.setChecked(False)
    assert win._assistant_server is None
    dlg.close()
