"""Stage 5, item 5.3 (rest): an SCS 11 show imported, and the import warnings shown before OK."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from engine.scs_import import read_scs, rtf_to_text
from engine.show_import import preview, take_over
from models.cue import Cue
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

# A small production in the shape of SCS 11.9 files (tags as written by SCS).
SCS = r"""<?xml version="1.0" encoding="UTF-8"?>
<Production>
   <Head><Title>School play</Title><PRLogicalDev0>Front</PRLogicalDev0></Head>
   <Cue>
      <CueId>Q1</CueId><Description>Pre-show music</Description>
      <Sub><SubType>F</SubType><SubDescription>Music</SubDescription>
         <AudioFile><FileName>$(Cue)\Audio\music.mp3</FileName><FadeInTime>2000</FadeInTime>
            <FadeOutTime>5000</FadeOutTime><DBLevel0>-6.0</DBLevel0><StartAt>1500</StartAt><EndAt>60000</EndAt>
            <LoopInfo><Loop>1</Loop><LoopStart>1000</LoopStart><LoopEnd>9000</LoopEnd></LoopInfo>
         </AudioFile></Sub>
   </Cue>
   <Cue>
      <CueId>Q2</CueId><Description>Bell after music start</Description>
      <ActivationMethod>auto</ActivationMethod><AutoActivateCueType>prev</AutoActivateCueType>
      <AutoActivatePosn>start</AutoActivatePosn><AutoActivateTime>10000</AutoActivateTime>
      <Sub><SubType>F</SubType><AudioFile><FileName>$(Cue)\Audio\bell.wav</FileName><DBLevel0>0.0</DBLevel0>
         <Pan0>-300</Pan0></AudioFile></Sub>
   </Cue>
   <Cue>
      <CueId>Q3</CueId><Description>Memo</Description>
      <Sub><SubType>E</SubType><SubDescription>Memo</SubDescription>
         <MemoRTFText>{\rtf1\ansi{\fonttbl{\f0\fnil Calibri;}}&#xD;&#xA;\pard\b Lights down\b0\par&#xD;&#xA;\par&#xD;&#xA;then caf\'e9\par&#xD;&#xA;}</MemoRTFText>
      </Sub>
   </Cue>
   <Cue>
      <CueId>Q4</CueId><Description>After the memo</Description>
      <ActivationMethod>auto</ActivationMethod><AutoActivateCueType>prev</AutoActivateCueType>
      <AutoActivatePosn>end</AutoActivatePosn><AutoActivateTime>0</AutoActivateTime>
      <Sub><SubType>A</SubType><SubDescription>Slides</SubDescription><PLFadeInTime>1000</PLFadeInTime>
         <VideoFile><FileName>$(Cue)\Media\a.jpg</FileName><EndAt>7000</EndAt><TransType>xfade</TransType>
            <TransTime>1500</TransTime></VideoFile>
         <VideoFile><FileName>$(Cue)\Media\b.jpg</FileName><EndAt>5000</EndAt></VideoFile></Sub>
   </Cue>
   <Cue>
      <CueId>Q5</CueId><Description>Lights and fade</Description>
      <Sub><SubType>K</SubType><SubDescription>Lights</SubDescription></Sub>
      <Sub><SubType>S</SubType><SubDescription>Fade music</SubDescription>
         <SFRAction0>fadeout</SFRAction0><SFRCueType0>sel</SFRCueType0><SFRCue0>Q1</SFRCue0>
         <SFRAction1>stop</SFRAction1><SFRCueType1>sel</SFRCueType1><SFRCue1>Q9</SFRCue1></Sub>
      <Sub><SubType>L</SubType><RelStartMode>ae_prev_sub</RelStartMode><LCCue>Q1</LCCue><LCAction>rel</LCAction>
         <LCReqdDBLevel0>-12.0</LCReqdDBLevel0><LCTime0>2000</LCTime0></Sub>
   </Cue>
   <Cue>
      <CueId>Q6</CueId><Description>Interval playlist</Description>
      <Hotkey>O</Hotkey><HotkeyLabel>Interval music</HotkeyLabel><ActivationMethod>hot</ActivationMethod>
      <Sub><SubType>P</SubType><PLRepeat>1</PLRepeat><PLMastDBLevel0>0.0</PLMastDBLevel0>
         <PLTransType>xfade</PLTransType><PLTransTime>3000</PLTransTime>
         <AudioFile><FileName>$(Cue)\Playlist\one.mp3</FileName><PLRelLevel>50</PLRelLevel></AudioFile>
         <AudioFile><FileName>$(Cue)\Playlist\two.mp3</FileName><PLRelLevel>100</PLRelLevel></AudioFile></Sub>
   </Cue>
   <Cue>
      <CueId>Q7</CueId><Description>Start the interval</Description>
      <Sub><SubType>Q</SubType><CallCue>Q6</CallCue></Sub>
   </Cue>
   <Cue>
      <CueId>Q8</CueId><Description>Lights only</Description>
      <Sub><SubType>K</SubType></Sub>
   </Cue>
   <Cue>
      <CueId>Q9</CueId><Description>Time code start</Description><ActivationMethod>ltc</ActivationMethod>
      <Sub><SubType>F</SubType><AudioFile><FileName>C:\elsewhere\x.mp3</FileName></AudioFile></Sub>
   </Cue>
   <Cue>
      <CueId>Q10</CueId><Description>Bell and duck</Description><ActivationMethod>auto</ActivationMethod>
      <AutoActivateCue>Q1</AutoActivateCue><AutoActivatePosn>start</AutoActivatePosn>
      <AutoActivateTime>2000</AutoActivateTime>
      <Sub><SubType>F</SubType><AudioFile><FileName>$(Cue)\Audio\bell.wav</FileName></AudioFile></Sub>
      <Sub><SubType>L</SubType><RelStartTime>500</RelStartTime><LCCue>Q1</LCCue>
         <LCReqdDBLevel0>-10.0</LCReqdDBLevel0></Sub>
   </Cue>
   <Cue>
      <CueId>Q11</CueId><Description>Slides later</Description><ActivationMethod>auto</ActivationMethod>
      <AutoActivateCue>Q1</AutoActivateCue><AutoActivatePosn>end</AutoActivatePosn>
      <Sub><SubType>A</SubType>
         <VideoFile><FileName>$(Cue)\Media\a.jpg</FileName></VideoFile>
         <VideoFile><FileName>$(Cue)\Media\b.jpg</FileName></VideoFile></Sub>
   </Cue>
   <Cue>
      <CueId>Q12</CueId><Description>Scene with a playlist</Description>
      <Sub><SubType>F</SubType><AudioFile><FileName>$(Cue)\Audio\bell.wav</FileName></AudioFile></Sub>
      <Sub><SubType>P</SubType><AudioFile><FileName>$(Cue)\Playlist\one.mp3</FileName></AudioFile></Sub>
      <Sub><SubType>A</SubType>
         <VideoFile><FileName>$(Cue)\Media\a.jpg</FileName></VideoFile>
         <VideoFile><FileName>$(Cue)\Media\b.jpg</FileName></VideoFile></Sub>
   </Cue>
   <Cue>
      <CueId>Q13</CueId><Description>Stop the scene</Description>
      <Sub><SubType>S</SubType><SFRAction0>stop</SFRAction0><SFRCueType0>sel</SFRCueType0><SFRCue0>Q12</SFRCue0></Sub>
   </Cue>
</Production>
"""


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _write(tmp_path: Path) -> Path:
    for rel in ("Audio/music.mp3", "Audio/bell.wav", "Media/a.jpg", "Media/b.jpg", "Playlist/one.mp3",
                "Playlist/two.mp3"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(b"x")
    path = tmp_path / "play.scs11"
    path.write_text(SCS, encoding="utf-8")
    return path


def _by_label(cues: list[Cue]) -> dict[str, Cue]:
    return {c.q_label: c for c in cues if c.q_label}


def test_rtf_memo_to_text():
    assert rtf_to_text("{\\rtf1\\ansi{\\fonttbl{\\f0 Arial;}}\\pard Hello\\par\\par world\\'e9\\par}") == \
        "Hello\n\nworldé"
    assert rtf_to_text("plain words") == "plain words"
    # A character outside the basic plane comes as two halves: joined, so the show can be saved.
    rocket = rtf_to_text("{\\rtf1\\ansi Brawo \\u-10179?\\u-8576?\\par}")
    assert rocket == "Brawo \U0001F680" and rocket.encode("utf-8")
    # A Polish memo: the code page of the file, and the fallback byte after \uN is not doubled.
    assert rtf_to_text("{\\rtf1\\ansi\\ansicpg1250 Wy\\'b3\\'b9cz \\u322\\'b3\\par}") == "Wyłącz ł"


def test_scs_cues_map(tmp_path):
    show = read_scs(_write(tmp_path))
    assert show.title == "School play"
    q = _by_label(show.cues)
    music = q["Q1"]
    assert music.media_type.value == "AUDIO" and music.layer == 2
    assert Path(music.file_path) == tmp_path / "Audio" / "music.mp3" and music.status.value == "LOADED"
    assert (music.fade_in, music.fade_out, music.in_point, music.out_point) == (2.0, 5.0, 1.5, 60.0)
    assert abs(music.volume - 0.501) < 1e-3 and music.loop
    bell = q["Q2"]                                         # 10 s after the music starts: a relative start
    assert (bell.start_rel_cue, bell.start_rel_when, bell.start_rel_offset) == (music.cue_id, "start", 10.0)
    memo = q["Q3"]
    assert memo.action_spec["kind"] == "note" and memo.action_spec["text"] == "Lights down\n\nthen café"
    slides = q["Q4"]                                       # after the end of a note (no file): Auto-GO
    assert memo.follow_mode == "AUTO_FOLLOW" and not slides.start_rel_cue
    pics = [c for c in show.cues if c.parent_id == slides.cue_id]
    assert slides.group_mode == "SEQUENCE" and [p.hold_time for p in pics] == [7.0, 5.0]
    assert pics[0].crossfade == 1.5 and pics[0].fade_in == 1.0 and pics[0].media_type.value == "IMAGE"
    scene = q["Q5"]                                        # lights left out, two SFR kinds + a level change
    inside = [c for c in show.cues if c.parent_id == scene.cue_id]
    kinds = [c.action_spec["kind"] for c in inside]
    assert scene.group_mode == "SIMULTANEOUS" and kinds == ["fade", "stop", "level"]
    assert inside[0].action_spec["cue_ids"] == [music.cue_id] and inside[0].action_spec["duration"] == 5.0
    assert inside[1].action_spec["cue_ids"] == [q["Q9"].cue_id]
    assert inside[2].action_spec["mode"] == "relative" and inside[2].action_spec["db"] == -12.0
    playlist = q["Q6"]                                     # a playlist on a key: a scene cannot be an effect
    assert not playlist.adlib and "O" in playlist.notes and playlist.group_mode == "LOOP"
    tracks = [c for c in show.cues if c.parent_id == playlist.cue_id]
    assert [round(t.volume, 2) for t in tracks] == [0.5, 1.0] and tracks[0].crossfade == 3.0
    assert q["Q7"].action_spec["kind"] == "call" and q["Q7"].action_spec["cue_ids"] == [playlist.cue_id]
    assert q["Q8"].action_spec["kind"] == "note"            # nothing maps: a note keeps its place
    # Starts by itself with two parts: no scene, each part relative to Q1 with its own delay.
    first = q["Q10"]
    duck = show.cues[show.cues.index(first) + 1]
    assert first.parent_id is None and duck.parent_id is None and duck.action_spec["kind"] == "level"
    assert [(c.start_rel_cue, c.start_rel_offset, c.pre_delay) for c in (first, duck)] == [
        (music.cue_id, 2.0, 0.0), (music.cue_id, 2.5, 0.0)]
    assert not q["Q11"].start_rel_cue                       # a picture scene cannot wait for Q1: GO + warning
    # A scene with a playlist and a picture scene: those go on rows after it; "stop Q12" reaches them all.
    scene12 = q["Q12"]
    at = show.cues.index(scene12)
    heads = [c for c in show.cues[at + 1:] if c.parent_id is None][:3]
    assert [h.media_type.value for h in heads[:2]] == ["GROUP", "GROUP"] and heads[0].playlist
    assert heads[2] is q["Q13"]
    assert set(q["Q13"].action_spec["cue_ids"]) == {scene12.cue_id, heads[0].cue_id, heads[1].cue_id}
    # Nothing outside the GO order is a scene (its cues would stay on GO).
    from engine.show_engine import outside_go_order
    assert not any(outside_go_order(c) for c in show.cues if c.media_type.value == "GROUP")
    kinds = {(w[0], w[1].split()[0]) for w in show.all_warnings()}
    assert {("scs_loop", "Q1"), ("scs_pan", "Q2"), ("scs_sub", "Q5"), ("scs_after_sub", "Q5"),
            ("scs_sub", "Q8"), ("scs_start", "Q9"), ("scs_group_start", "Q6"), ("scs_group_start", "Q11"),
            ("scs_group_start", "Q12")} <= kinds
    assert show.warnings[scene.cue_id] and q["Q9"].status.value == "OFFLINE"


def test_taken_over_like_a_show(tmp_path):
    show = read_scs(_write(tmp_path))
    q = _by_label(show.cues)
    tops = [c.cue_id for c in show.cues if c.parent_id is None]
    counter_before = next(Cue._id_counter)
    warnings = preview(show.cues, tops)
    assert next(Cue._id_counter) == counter_before + 1        # the preview takes no ids
    new, warnings_after = take_over(show.cues, tops)
    assert len(new) == len(show.cues) and warnings == warnings_after
    new_q = _by_label(new)
    assert new_q["Q2"].start_rel_cue == new_q["Q1"].cue_id    # links follow the new ids
    assert new_q["Q7"].action_spec["cue_ids"] == [new_q["Q6"].cue_id]
    only_bell = preview(show.cues, [q["Q2"].cue_id])
    assert ("relative", "Bell after music start", 1) in only_bell


def test_window_import_shows_warnings_before_ok(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from PySide6.QtWidgets import QListWidget
    from ui.main_window import MainWindow, _show_import
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        path = _write(tmp_path)
        monkeypatch.setattr(_show_import.QFileDialog, "getOpenFileName",
                            staticmethod(lambda *a, **k: (str(path), "")))
        seen = {}

        def look(dlg):
            cues = dlg.findChild(QListWidget, "import_cues")
            warns = dlg.findChild(QListWidget, "import_warnings")
            seen["cues"] = cues.count()
            seen["warnings"] = [warns.item(i).text() for i in range(warns.count())]
            buttons = dlg.findChildren(_show_import.QDialogButtonBox)[0]
            seen["ok"] = buttons.button(_show_import.QDialogButtonBox.StandardButton.Ok).text()
            return _show_import.QDialog.DialogCode.Accepted

        monkeypatch.setattr(_show_import.QDialog, "exec", look)
        win._import_scs_show()
        assert seen["cues"] == len(read_scs(path).cues)
        assert any("Q5" in w and "(" in w for w in seen["warnings"])       # the lighting part, before OK
        assert any("Q9" in w for w in seen["warnings"])
        assert len(win._cues) == seen["cues"] and win._show_info.get("title") == "School play"
        win._on_undo()
        assert not win._cues                                                # one Ctrl+Z
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
