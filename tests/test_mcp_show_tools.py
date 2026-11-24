"""Stage 1M, M1: the show assistant's tools on show files (and the MCP server over stdio)."""

from __future__ import annotations

import asyncio
import time
import json
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest

pytest.importorskip("mcp")  # optional: pip install mcp

from mcp_server.show_tools import AccessPolicy, ShowSession, ToolError
from models.project_manager import ProjectManager


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    # A full QApplication first: ensure_qt_gui() would otherwise make a bare
    # QGuiApplication, and a later test file that opens windows would crash.
    from PySide6.QtWidgets import QApplication

    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def place(tmp_path):
    shows, media = tmp_path / "shows", tmp_path / "media"
    shows.mkdir()
    media.mkdir()
    for name in ("intro.mp4", "music.mp3", "rain.wav", "poster.jpg"):
        (media / name).write_bytes(b"\0" * 64)
    (media / "readme.txt").write_text("not media")
    session = ShowSession(AccessPolicy([shows, media]), autosave_file=tmp_path / "no-autosave.json")
    return session, shows, media, tmp_path


def test_paths_stay_inside_the_allowed_folders(place):
    session, shows, media, tmp = place
    policy = session.policy
    assert policy.check(shows / "a.blindcue") == (shows / "a.blindcue").resolve()
    assert policy.check("a.blindcue") == (shows / "a.blindcue").resolve()   # relative: first folder
    for bad in (tmp / "elsewhere.blindcue", str(shows / ".." / "x.blindcue"), "../x.blindcue"):
        with pytest.raises(ToolError):
            policy.check(bad)
    assert AccessPolicy([]).check(shows) == shows.resolve()             # no folder: every drive
    link = media / "link_out"
    try:
        os.symlink(tmp, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        return  # no right to make links here
    with pytest.raises(ToolError):
        policy.check(link / "elsewhere.blindcue")


def test_build_save_and_reopen_a_show(place):
    session, shows, media, _tmp = place
    session.new_show(str(shows / "play"))
    assert [m["type"] for m in session.list_media(str(media), durations=False)["files"]] == \
        ["VIDEO", "AUDIO", "IMAGE", "AUDIO"]                       # readme.txt is not media
    intro = session.add_media_cue(str(media / "intro.mp4"), fields={"name": "Intro",
                                                                    "follow_mode": "SIMULTANEOUS"})
    music = session.add_media_cue(str(media / "music.mp3"), fields={"fade_in": 2, "volume": "0.8"})
    assert music["layer"] == 2 and intro["layer"] == 1
    caption = session.add_text_cue("Akt I\nW krainie czarów", position="top")
    assert caption["layer"] == 3 and caption["file"] == "(caption)"
    assert Path(session.get_cue(caption["cue_id"])["file_path"]).is_file()   # PNG drawn offscreen
    down = session.add_action_cue("level", spec={"target": "cues", "cue_ids": [music["cue_id"]],
                                                 "mode": "relative", "db": -12, "duration": 2})
    note = session.add_action_cue("note", spec={"text": "Kurtyna"}, after_cue_id=intro["cue_id"])
    assert [c["cue_id"] for c in session.list_cues()][1] == music["cue_id"]  # SIMULT chain kept whole
    assert session.list_cues()[2]["cue_id"] == note["cue_id"]
    scene = session.add_group("Scena 1", [music["cue_id"], down["cue_id"]], mode="SEQUENCE")
    rows = session.list_cues()
    at = [r["cue_id"] for r in rows].index(scene["cue_id"])
    assert [r.get("group_id") for r in rows[at + 1:at + 3]] == [scene["cue_id"]] * 2
    assert session.validate_show()["ok"]
    saved = session.save_show()
    assert Path(saved["saved"]).suffix == ".blindcue" and "backup" not in saved
    again = session.save_show()
    assert Path(again["backup"]).is_file()                         # the old file kept as .bak

    other = ShowSession(session.policy, autosave_file=session.autosave_file)
    other.open_show(saved["saved"])
    assert [(c["name"], c["type"]) for c in other.list_cues()] == [(r["name"], r["type"]) for r in rows]
    cues, _idx, _settings = ProjectManager(autosave_dir=place[3] / "pm").load_project(saved["saved"])
    assert len(cues) == len(rows)                                  # the program reads it as well


def test_wrong_values_are_refused_and_nothing_changes(place):
    session, shows, media, _tmp = place
    session.new_show(str(shows / "x.blindcue"))
    cue = session.add_media_cue(str(media / "music.mp3"))
    before = session.get_cue(cue["cue_id"])
    for fields in ({"volume": 3}, {"layer": 7}, {"follow_mode": "SOMETIMES"}, {"hotkey": "Ctrl"},
                   {"status": "LIVE"}, {"fade_in": 1, "out_point": 0.5, "in_point": 2},
                   {"exclusive": "maybe"}):
        with pytest.raises(ToolError):
            session.update_cue(cue["cue_id"], fields)
    assert session.get_cue(cue["cue_id"]) == before
    with pytest.raises(ToolError):
        session.add_media_cue(str(media / "readme.txt"))
    with pytest.raises(ToolError):
        session.add_action_cue("fade", spec={"target": "cues", "cue_ids": [99999]})
    with pytest.raises(ToolError):
        session.add_action_cue("explode")
    session.update_cue(cue["cue_id"], {"adlib": "true", "hotkey": "b", "hotkey_mode": "note"})
    effect = session.get_cue(cue["cue_id"])
    assert effect["adlib"] and effect["hotkey"] == "B" and effect["hotkey_mode"] == "note"


def test_move_delete_and_validate(place):
    session, shows, media, _tmp = place
    session.new_show(str(shows / "y.blindcue"))
    a = session.add_media_cue(str(media / "intro.mp4"))["cue_id"]
    b = session.add_media_cue(str(media / "music.mp3"))["cue_id"]
    c = session.add_media_cue(str(media / "rain.wav"))["cue_id"]
    fade = session.add_action_cue("fade", spec={"target": "cues", "cue_ids": [b], "duration": 2})["cue_id"]
    session.move_cue(c, to_top=True)
    assert [r["cue_id"] for r in session.list_cues()] == [c, a, b, fade]
    session.move_cue(c, after_cue_id=b)
    assert [r["cue_id"] for r in session.list_cues()] == [a, b, c, fade]
    group = session.add_group("Scene", [a, b])["cue_id"]
    session.move_cue(group)                                        # to the end, with its items
    assert [r["cue_id"] for r in session.list_cues()] == [c, fade, group, a, b]
    session.delete_cue(b)
    report = session.validate_show()
    assert not report["ok"] and any("without a target" in p for p in report["problems"])
    session.delete_cue(group)                                      # its item stays, ungrouped
    assert [r.get("group_id") for r in session.list_cues()] == [None, None, None]
    (media / "rain.wav").unlink()
    assert any("missing" in p for p in session.validate_show()["problems"])


def test_a_show_open_in_the_program_is_not_overwritten(place):
    session, shows, media, tmp = place
    session.new_show(str(shows / "live.blindcue"))
    session.add_media_cue(str(media / "music.mp3"))
    target = Path(session.save_show()["saved"])
    autosave = tmp / "no-autosave.json"
    autosave.write_text(json.dumps({"active_project_path": str(target), "clean_exit": False,
                                    "saved_at": datetime.now().isoformat()}), encoding="utf-8")
    assert "warning" in ShowSession(session.policy, autosave).open_show(str(target))
    with pytest.raises(ToolError):
        session.save_show()
    copy_path = session.save_show(str(shows / "live-copy.blindcue"))["saved"]   # under another name: fine
    assert Path(copy_path).is_file()


def test_portable_show_stays_portable(place):
    session, shows, media, tmp = place
    from models.cue import Cue, MediaType

    pm = ProjectManager(autosave_dir=tmp / "pm")
    show = shows / "bundle.blindcue"
    pm.save_project_bundled(show, [Cue(name="m", media_type=MediaType.AUDIO, file_path=str(media / "music.mp3"))])
    session.open_show(str(show))
    assert session.bundled
    archived = shows / "bundle_media"
    session.add_media_cue(str(media / "rain.wav"))
    session.save_show()
    data = json.loads(show.read_text(encoding="utf-8"))
    assert all(not Path(c["file_path"]).is_absolute() for c in data["cues"])
    assert (archived / "rain.wav").is_file() and (media / "rain.wav").is_file()   # media copied, never moved


def test_mcp_tools_answer_with_messages(place):
    session, shows, media, _tmp = place
    from mcp_server import server

    server.SESSION = server.FILES = session
    try:
        def call(name, **args):
            result = asyncio.run(server.mcp.call_tool(name, args))
            content = result[0] if isinstance(result, tuple) else result
            return json.loads(content[0].text)  # what the assistant reads

        assert "error" in call("list_cues")                         # nothing open yet
        call("new_show", path=str(shows / "z.blindcue"))
        added = call("add_media_cue", path=str(media / "poster.jpg"), fields={"hold_time": 5})
        assert added["type"] == "IMAGE"
        assert "error" in call("add_media_cue", path=str(shows.parent / "outside.jpg"))
        assert call("validate_show")["ok"]
        assert Path(call("save_show")["saved"]).is_file()
        text = server.manual_resource("pl")
        assert "GO" in text and "<" not in text[:200]
    finally:
        server.SESSION = server.FILES = None


def test_real_mcp_client_over_stdio(place):
    """The server as an MCP client starts it: a separate process talking over stdio."""
    _session, shows, media, _tmp = place
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(APP_DIR / "mcp_server" / "server.py"), "--root", str(shows), "--root", str(media)],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )

    async def run() -> dict:
        async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
            await client.initialize()
            names = {t.name for t in (await client.list_tools()).tools}
            await client.call_tool("new_show", {"path": str(shows / "remote.blindcue")})
            await client.call_tool("add_media_cue", {"path": str(media / "music.mp3")})
            saved = await client.call_tool("save_show", {})
            return {"names": names, "saved": json.loads(saved.content[0].text)}

    out = asyncio.run(asyncio.wait_for(run(), timeout=90))
    assert {"open_show", "add_text_cue", "validate_show"} <= out["names"]
    assert Path(out["saved"]["saved"]).is_file()


def test_review_paths_network_streams_and_junctions(place):
    session, shows, media, tmp = place
    policy = session.policy
    for bad in (r"\\attacker\share\x.blindcue", "//attacker/share/x.blindcue",
                str(media / "intro.mp4:.blindcue"), "intro.mp4:hidden"):
        with pytest.raises(ToolError):
            policy.check(bad)
        assert not policy.contains(bad)
    if sys.platform == "win32":
        import _winapi

        outside = tmp / "secret"
        outside.mkdir()
        (outside / "song.mp3").write_bytes(b"\0" * 64)
        _winapi.CreateJunction(str(outside), str(media / "jump"))
        with pytest.raises(ToolError):                 # a junction inside the folder leads out
            policy.check(media / "jump" / "song.mp3")
        names = [Path(f["path"]).name for f in session.list_media(str(media), recursive=True, durations=False)["files"]]
        assert "song.mp3" not in names                 # list_media does not follow it


def test_review_portable_save_never_copies_outside_files(place):
    session, shows, media, tmp = place
    from models.cue import Cue, MediaType

    secret = tmp / "access.env.png"
    secret.write_bytes(b"secret")
    pm = ProjectManager(autosave_dir=tmp / "pm")
    show = shows / "shared.blindcue"
    pm.save_project_bundled(show, [Cue(name="m", media_type=MediaType.AUDIO, file_path=str(media / "music.mp3"))])
    data = json.loads(show.read_text(encoding="utf-8"))
    data["cues"].append({**data["cues"][0], "cue_id": 777, "name": "evil", "file_path": str(secret),
                         "media_type": "IMAGE"})
    show.write_text(json.dumps(data), encoding="utf-8")
    opened = session.open_show(str(show))
    assert "outside the allowed folders" in opened["warning"]
    assert any("outside" in w for w in session.validate_show()["warnings"])
    with pytest.raises(ToolError):
        session.save_show()
    assert not (shows / "shared_media" / secret.name).exists()
    session.delete_cue(777)
    session.save_show()                                         # without that cue: fine


def test_review_backup_once_and_no_overwrite_of_newer_work(place):
    session, shows, media, _tmp = place
    show = shows / "b.blindcue"
    session.new_show(str(show))
    session.add_media_cue(str(media / "music.mp3"))
    session.save_show()
    teacher = show.read_text(encoding="utf-8")
    again = ShowSession(session.policy, session.autosave_file)
    again.open_show(str(show))
    again.add_media_cue(str(media / "rain.wav"))
    first = again.save_show()
    again.add_media_cue(str(media / "intro.mp4"))
    again.save_show()
    assert Path(first["backup"]).read_text(encoding="utf-8") == teacher   # the teacher's version stays
    time.sleep(0.02)
    show.write_text(show.read_text(encoding="utf-8").replace('"m"', '"m"'), encoding="utf-8")
    os.utime(show)                                                        # saved by someone else
    with pytest.raises(ToolError):
        again.save_show()
    with pytest.raises(ToolError):                                        # save-as never overwrites
        again.save_show(str(show))


def test_review_actions_groups_and_moves(place):
    session, shows, media, _tmp = place
    session.new_show(str(shows / "c.blindcue"))
    a = session.add_media_cue(str(media / "intro.mp4"))["cue_id"]
    b = session.add_media_cue(str(media / "music.mp3"))["cue_id"]
    c = session.add_media_cue(str(media / "rain.wav"))["cue_id"]
    for kind, spec in (("fade", {}), ("fade", {"target": "cue"}), ("fade", {"cue_ids": [b], "volume": 1}),
                       ("level", {"target": "cues", "cue_ids": [b], "db": 99}),
                       ("checklist", {"items": ["x" * 300]})):
        with pytest.raises(ToolError):
            session.add_action_cue(kind, spec=spec)
    fade = session.add_action_cue("fade", spec={"cue_ids": [b], "duration": 2})
    assert session.get_cue(fade["cue_id"])["action_spec"]["target"] == "cues"   # never "all" by guess
    with pytest.raises(ToolError):
        session.update_cue(fade["cue_id"], {"action": "everything"})
    group = session.add_group("Scene", [c, a, c])["cue_id"]                     # duplicates, any order
    rows = [r["cue_id"] for r in session.list_cues()]
    assert rows.count(c) == 1 and rows.index(a) < rows.index(c) == rows.index(group) + 2
    with pytest.raises(ToolError):
        session.move_cue(b, after_cue_id=987654)
    with pytest.raises(ToolError):
        session.move_cue(b, after_cue_id=a, to_top=True)
    session.move_cue(b, into_group_id=group)
    assert [r.get("group_id") for r in session.list_cues() if r["cue_id"] in (a, b, c)] == [group] * 3
    (media / "intro.mp4").unlink()
    session.update_cue(a, {"notes": "file comes later"})                       # a missing file is no block


def test_review_marker_ids_stay_and_one_way_to_start(place):
    session, shows, media, _tmp = place
    session.new_show(str(shows / "marks"))
    song = session.add_media_cue(str(media / "music.mp3"), fields={"markers": [{"name": "chorus", "sec": 30}]})
    mark = session.get_cue(song["cue_id"])["markers"][0]["id"]
    title = session.add_media_cue(str(media / "poster.jpg"), fields={
        "start_rel_cue": song["cue_id"], "start_rel_when": "marker", "start_rel_marker": mark})
    # a new marker in front, given without ids: "chorus" keeps its id (same time)
    session.update_cue(song["cue_id"], {"markers": [{"name": "intro", "sec": 5}, {"name": "chorus", "sec": 30}]})
    marks = {m["name"]: m["id"] for m in session.get_cue(song["cue_id"])["markers"]}
    assert marks["chorus"] == mark and marks["intro"] != mark
    with pytest.raises(ToolError, match="used by"):
        session.update_cue(song["cue_id"], {"markers": [{"name": "intro", "sec": 5}]})
    assert len(session.get_cue(song["cue_id"])["markers"]) == 2          # refused: nothing changed
    with pytest.raises(ToolError):
        session.update_cue(song["cue_id"], {"markers": [{"id": "abc", "sec": 5}]})
    with pytest.raises(ToolError, match="not both"):
        session.update_cue(title["cue_id"], {"start_clock": "19:55"})


def test_no_folder_means_every_drive_but_never_the_network_or_system_folders(tmp_path):
    """The media can be anywhere, also on a USB stick."""
    import sys

    for roots in ([], ["${user_config.folders}"], ["*"], ["  "]):
        policy = AccessPolicy(roots)
        assert policy.everywhere and "every drive" in policy.describe()[0]
    policy = AccessPolicy([])
    assert policy.check(tmp_path / "show.blindcue") == (tmp_path / "show.blindcue").resolve()
    assert policy.contains(str(tmp_path / "media" / "a.mp3"))
    if sys.platform == "win32":
        for network in (r"\\nas\media\a.mp3", "//nas/media/a.mp3"):
            assert not policy.contains(network)
            with pytest.raises(ToolError):
                policy.check(network)
        with pytest.raises(ToolError):
            policy.check_write(r"C:\Windows\show.blindcue")             # never into system folders
        assert policy.check_write(tmp_path / "x.blindcue") == (tmp_path / "x.blindcue").resolve()
    limited = AccessPolicy([tmp_path / "shows"])
    assert not limited.everywhere and not limited.contains(str(tmp_path / "elsewhere.mp3"))
