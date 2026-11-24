"""Stage 1M, M3: the Claude Desktop extension file and the settings for other clients."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mcp_server import bundle  # noqa: E402


def test_mcpb_is_a_zip_with_a_complete_manifest(tmp_path):
    out = bundle.build_mcpb(tmp_path / "x" / "assistant.mcpb", "0.1.0", icon_png=b"\x89PNG fake")
    with zipfile.ZipFile(out) as z:
        assert sorted(z.namelist()) == ["icon.png", "manifest.json"]
        manifest = json.loads(z.read("manifest.json").decode("utf-8"))
    for key in ("manifest_version", "name", "version", "description", "author", "server"):
        assert key in manifest                                   # required by the MCPB spec
    assert manifest["author"]["name"] and manifest["compatibility"]["platforms"] == ["win32"]
    server = manifest["server"]
    assert server["type"] == "binary"
    args = server["mcp_config"]["args"]
    assert args[-2:] == ["--root", "${user_config.folders}"]   # several folders: --root A B
    assert manifest["user_config"]["folders"]["type"] == "directory"
    assert manifest["user_config"]["folders"]["multiple"] is True
    assert manifest["user_config"]["folders"]["required"] is False         # empty: every drive (2026-11-24)
    assert "default" not in manifest["user_config"]["folders"]
    command = Path(server["mcp_config"]["command"])
    assert command.is_absolute() and command.exists()            # this computer's assistant


def test_without_icon_and_settings_for_other_clients(tmp_path):
    out = bundle.build_mcpb(tmp_path / "a.mcpb", "1.2.3")
    with zipfile.ZipFile(out) as z:
        assert z.namelist() == ["manifest.json"]
        assert "icon" not in json.loads(z.read("manifest.json"))
    config = json.loads(bundle.client_config([str(tmp_path)]))
    entry = config["mcpServers"]["blindcue"]
    assert entry["args"][-2:] == ["--root", str(tmp_path)]
    everywhere = json.loads(bundle.client_config([]))["mcpServers"]["blindcue"]["args"]
    assert "--root" not in everywhere


def test_server_accepts_both_root_forms(monkeypatch):
    import pytest

    pytest.importorskip("mcp")
    from mcp_server import server

    seen = {}
    monkeypatch.setattr(server.mcp, "run", lambda transport: seen.setdefault("t", transport))
    monkeypatch.setattr(server, "ensure_qt_gui", lambda: None)
    server.main(["--root", "C:/A", "C:/B", "--root", "C:/C"])
    assert [Path(r).name.lower() for r in server.FILES.policy.roots] == ["a", "b", "c"] and seen["t"] == "stdio"
    server.main(["--root"])                                  # Claude Desktop with no folder chosen
    assert server.FILES.policy.everywhere
    server.SESSION = server.FILES = None
