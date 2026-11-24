"""A show of Show Cue System 11 (``.scs11``) turned into BlindCue cues (stage 5, item 5.3). No Qt.

An ``.scs11`` file is XML: ``<Production>`` with a ``<Head>`` (title) and
one ``<Cue>`` per cue; a cue has a label (``CueId``), a description, how it
starts (``ActivationMethod``: by GO, automatically relative to another cue,
by a key) and one or more sub-cues (``<Sub>``, ``SubType``):

=====  =========================  ==========================================
SCS    what it is                 BlindCue
=====  =========================  ==========================================
F      audio file                 sound cue (layer 2): level, fades, IN/OUT
A      video / picture(s)         video or picture (layer 1); several files =
                                  a scene that plays them one after another
P      playlist                   playlist (a looping one: a looping scene)
L      level change               "level" action (absolute or ± dB)
S      stop / fade / release /    "stop", "fade", "release", "pause" (fade
       hibernate / resume         and hibernate = put to sleep), "resume"
E, N   memo, note                 note for the operator
Q      call a cue                 "call" action
G      go to a cue                "jump" action
=====  =========================  ==========================================

A cue with several sub-cues becomes a scene where all start together (each
with its own delay); when it starts by itself, its parts go on rows of their
own instead. Automatic starts become relative starts (2.1) when the cue they
follow has a media file, otherwise "together with" / Auto-GO of the row
before. Only single cues start outside the GO order (a key, a call, a
relative start): a scene or playlist that did so in SCS waits for a GO here
and is reported - the program cannot yet hold a whole scene outside the GO
order. What does not map (lighting, control messages, other programs,
time code, live input, panning, loop regions, level envelopes...) is left
out and reported, keyed by the cue it belongs to, so the import window can
show it before anything is added. Media paths ``$(Cue)\\...`` are relative
to the folder of the ``.scs11`` file.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from models.cue import (
    ACTION_CALL,
    ACTION_FADE,
    ACTION_GOTO,
    ACTION_LEVEL,
    ACTION_NOTE,
    ACTION_PAUSE,
    ACTION_RELEASE,
    ACTION_RESUME,
    ACTION_STOP,
    ACTION_TARGET_ALL,
    ACTION_TARGET_CUES,
    Cue,
    CueStatus,
    FollowMode,
    GroupMode,
    MediaType,
    sanitize_action_spec,
)

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff", ".svg"}
MAX_REL_OFFSET = 600.0
# Sub-cue types that have no BlindCue counterpart (reported by their letter).
UNSUPPORTED_SUBS = {"K": "lighting", "M": "control", "R": "program", "T": "position", "U": "timecode",
                    "J": "enable", "I": "live_input"}

# Warning kinds (the UI words them): every warning is (kind, cue name, count, detail).
W_SUB = "scs_sub"              # detail: the sub type letter
W_START = "scs_start"          # detail: the activation method
W_START_REF = "scs_start_ref"  # an automatic start after a cue that is not there / has no media
W_KEY = "scs_key"              # a hot key that is not one letter or digit
W_TARGET = "scs_target"        # a stop / level / call names a cue that is not there
W_LOOP = "scs_loop"            # a loop region: the whole file loops
W_PAN = "scs_pan"              # panning is left out
W_ENVELOPE = "scs_envelope"    # level points inside the file are left out
W_DEVICES = "scs_devices"      # several outputs of one sound: the first one is used
W_AFTER_SUB = "scs_after_sub"  # "after the previous sub-cue ends": starts with the cue instead
W_SFR = "scs_sfr"              # detail: the SFR action that does not map
W_OFFSET = "scs_offset"        # a relative start later than 600 s: shortened
W_REPEAT = "scs_repeat"        # a scene / effect made of several sub-cues: check it (older imports)
W_GROUP_START = "scs_group_start"  # a scene / playlist that started by itself (key, call, auto): now by GO


@dataclass
class ScsShow:
    title: str = ""
    cues: list[Cue] = field(default_factory=list)
    # cue_id of the top-level cue it concerns (0 = the whole show) -> warnings
    warnings: dict[int, list[tuple[str, str, int, str]]] = field(default_factory=dict)

    def all_warnings(self) -> list[tuple[str, str, int, str]]:
        return [w for ws in self.warnings.values() for w in ws]


def _ms(text: str | None, default: float = 0.0) -> float:
    try:
        return max(0.0, float(str(text).strip()) / 1000.0)
    except (TypeError, ValueError):
        return default


def _db_to_level(text: str | None, default: float = 1.0) -> float:
    try:
        db = max(-200.0, min(20.0, float(str(text).strip())))  # a damaged value never overflows
        return max(0.0, min(1.0, 10 ** (db / 20.0)))
    except (TypeError, ValueError):
        return default


def _db(text: str | None, default: float = 0.0) -> float:
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return default


def rtf_to_text(rtf: str) -> str:
    """The words of a memo (SCS keeps memos as RTF); formatting is dropped."""
    if not rtf or not rtf.lstrip().startswith("{\\rtf"):
        return (rtf or "").strip()
    # The code page of the \'xx bytes: \ansicpg1250 on a Polish Windows, else the font's charset.
    codec = "cp1252"
    page = re.search(r"\\ansicpg(\d+)", rtf)
    charset = re.search(r"\\fcharset(\d+)", rtf)
    charsets = {238: "cp1250", 204: "cp1251", 161: "cp1253", 162: "cp1254", 186: "cp1257", 0: "cp1252"}
    for candidate in ((f"cp{page.group(1)}" if page else ""),
                      charsets.get(int(charset.group(1)), "") if charset else ""):
        if candidate and candidate != "cp1252":
            try:
                "".encode(candidate)
                codec = candidate
                break
            except LookupError:
                continue
    # A line break of the file ends a control word ("\par" + CRLF + "then") and is no text itself.
    text = re.sub(r"(\\[a-zA-Z]+-?\d*)[\r\n]+", r"\1 ", rtf)
    text = text.replace("\r", "").replace("\n", "")
    text = re.sub(r"\{\\\*[^{}]*(\{[^{}]*\}[^{}]*)*\}", "", text)              # {\*\generator ...}
    text = re.sub(r"\{\\(fonttbl|colortbl|stylesheet|info)[^{}]*(\{[^{}]*\}[^{}]*)*\}", "", text)
    # \uN is the character itself, the one unit after it (? or \'xx) only its fallback for old readers.
    text = re.sub(r"\\u(-?\d+) ?(?:\\'[0-9a-fA-F]{2}|[^\\{}])?", lambda m: chr(int(m.group(1)) % 65536), text)
    text = re.sub(r"(?:\\'[0-9a-fA-F]{2})+",
                  lambda m: bytes(int(h, 16) for h in re.findall(r"[0-9a-fA-F]{2}", m.group(0).replace("\\'", " ")))
                  .decode(codec, "replace"), text)
    text = re.sub(r"\\(par|line)\b ?", "\n", text)
    text = re.sub(r"\\tab\b ?", "\t", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    text = text.replace("\\{", "{").replace("\\}", "}").replace("\\\\", "\\")
    text = text.replace("{", "").replace("}", "")
    # Characters outside the basic plane come as two \uN halves: join them (a lone half cannot be saved).
    text = text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    lines: list[str] = []
    for line in (part.strip() for part in text.split("\n")):
        if line or (lines and lines[-1]):  # at most one empty line between paragraphs
            lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _media_path(raw: str | None, folder: Path) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    text = text.replace("$(Cue)", str(folder)).replace("$(cue)", str(folder))
    text = text.replace("\\", "/") if os.sep == "/" else text
    path = Path(text)
    if not path.is_absolute():
        path = folder / path
    return str(path)


def _action_seconds(cue: Cue) -> float:
    """How long an action takes (a fade, a level change, putting to sleep); 0 for the rest."""
    spec = cue.action_spec or {}
    if spec.get("kind") in (ACTION_PAUSE, ACTION_RESUME):
        return float(spec.get("sleep_sec", 0.0) or 0.0)
    if spec.get("kind") in (ACTION_LEVEL, ACTION_FADE):
        return float(spec.get("duration", 0.0) or 0.0)
    return 0.0


def _kind_of(path: str) -> MediaType:
    return MediaType.IMAGE if Path(path).suffix.lower() in IMAGE_EXT else MediaType.VIDEO


class _Reader:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.out: list[Cue] = []
        self.warnings: dict[int, list[tuple[str, str, int, str]]] = {}
        self.label_to_top: dict[str, Cue] = {}       # SCS label -> our top-level cue
        self.label_to_media: dict[str, Cue] = {}     # SCS label -> its first cue with a media file
        self.pending: list[tuple[Cue, str, dict]] = []   # actions whose targets are labels (second pass)
        self.top_order: list[Cue] = []
        self.starts: list[tuple[Cue, ET.Element, str]] = []        # top cue, its SCS element, its name
        self.extra_tops: list[tuple[Cue, list[Cue]]] = []          # scene in a scene -> its own row
        # Top cue id -> the rows that start one SCS cue (one row, or its parts when it starts by itself),
        # and the rows a stop / fade / level aimed at that SCS cue acts on (+ its scenes on own rows).
        self.rows_of: dict[int, list[Cue]] = {}
        self.targets_of: dict[int, list[Cue]] = {}

    def warn(self, owner: Cue | None, kind: str, name: str, count: int = 1, detail: str = "") -> None:
        self.warnings.setdefault(owner.cue_id if owner is not None else 0, []).append((kind, name, count, detail))

    # ── one sub-cue -> cues ──
    def _audio(self, sub: ET.Element, name: str, who: str, owner_box: list) -> list[Cue]:
        out = []
        for af in sub.findall("AudioFile") or [sub]:
            path = _media_path(af.findtext("FileName"), self.folder)
            if not path:
                continue
            cue = Cue(name=name or Path(path).stem, media_type=MediaType.AUDIO, file_path=path, layer=2)
            cue.volume = _db_to_level(af.findtext("DBLevel0"), 1.0)
            cue.fade_in = _ms(af.findtext("FadeInTime"))
            cue.fade_out = _ms(af.findtext("FadeOutTime"))
            start, end = _ms(af.findtext("StartAt")), _ms(af.findtext("EndAt"))
            cue.in_point = start
            cue.out_point = end if end > start else None
            info = af.find("LoopInfo")
            if info is not None and info.findtext("Loop", "0").strip() == "1":
                cue.loop = True
                if info.findtext("LoopStart") or info.findtext("LoopEnd"):
                    owner_box.append((W_LOOP, who, 1, ""))
            if af.findtext("Pan0", "0").strip() not in ("", "0") or any(
                    (p.text or "0").strip() not in ("", "0") for p in af.iter("LvlPtItemPan")):
                owner_box.append((W_PAN, who, 1, ""))
            if any((lp.findtext("LvlPtType") or "") not in ("FadeIn", "FadeOut", "Start", "End")
                   for lp in af.findall("LvlPt")):
                owner_box.append((W_ENVELOPE, who, 1, ""))
            if af.findtext("LogicalDev1"):
                owner_box.append((W_DEVICES, who, 1, ""))
            out.append(cue)
        return out

    def _pictures(self, sub: ET.Element, name: str) -> list[Cue]:
        items = sub.findall("VideoFile") or [sub]
        out = []
        for vf in items:
            path = _media_path(vf.findtext("FileName"), self.folder)
            if not path:
                continue
            kind = _kind_of(path)
            cue = Cue(name=Path(path).stem if len(items) > 1 else (name or Path(path).stem),
                      media_type=kind, file_path=path, layer=1)
            end = _ms(vf.findtext("EndAt"))
            continuous = vf.findtext("Continuous", "0").strip() == "1"
            if kind == MediaType.IMAGE:
                cue.hold_time = 0.0 if continuous or not end else end
            else:
                cue.loop = continuous
                cue.out_point = end if end > 0 else None
            if (vf.findtext("TransType") or "").strip().lower() == "xfade":
                cue.crossfade = _ms(vf.findtext("TransTime"))
            out.append(cue)
        if out:
            out[0].fade_in = _ms(sub.findtext("PLFadeInTime"))
            out[-1].fade_out = _ms(sub.findtext("PLFadeOutTime"))
            level = sub.findtext("SubDBLevel0")
            for cue in out:
                if cue.media_type == MediaType.VIDEO and level:
                    cue.volume = _db_to_level(level, 1.0)
        return out

    def _playlist(self, sub: ET.Element, name: str) -> tuple[Cue, list[Cue]]:
        repeat = sub.findtext("PLRepeat", "0").strip() == "1"
        group = Cue(name=name or "Playlist", media_type=MediaType.GROUP, file_path="", layer=2,
                    group_mode=(GroupMode.LOOP if repeat else GroupMode.SEQUENCE).value, collapsed=True,
                    color="#0ea5e9")
        group.playlist = not repeat
        master = _db_to_level(sub.findtext("PLMastDBLevel0"), 1.0)
        xfade = _ms(sub.findtext("PLTransTime")) if (sub.findtext("PLTransType") or "").lower() == "xfade" else 0.0
        tracks = []
        for af in sub.findall("AudioFile"):
            path = _media_path(af.findtext("FileName"), self.folder)
            if not path:
                continue
            cue = Cue(name=Path(path).stem, media_type=MediaType.AUDIO, file_path=path, layer=2,
                      parent_id=group.cue_id)
            try:
                rel = max(0.0, min(100.0, float(af.findtext("PLRelLevel", "100")))) / 100.0
            except ValueError:
                rel = 1.0
            cue.volume = round(master * rel, 4)
            start, end = _ms(af.findtext("StartAt")), _ms(af.findtext("EndAt"))
            cue.in_point = start
            cue.out_point = end if end > start else None
            cue.crossfade = xfade
            tracks.append(cue)  # the scene plays them one after another (no Auto-GO inside)
        if tracks:
            tracks[0].fade_in = _ms(sub.findtext("PLFadeInTime"))
            tracks[-1].fade_out = _ms(sub.findtext("PLFadeOutTime"))
        return group, tracks

    def _action(self, kind: str, name: str, **spec) -> Cue:
        return Cue(name=name or kind, media_type=MediaType.ACTION, file_path="", action_spec={"kind": kind, **spec})

    def _sub_cues(self, sub: ET.Element, cue_name: str, who: str, box: list) -> list[Cue]:
        """The cues of one sub-cue (a scene comes first, its cues after it), [] when it does not map."""
        kind = (sub.findtext("SubType") or "").strip().upper()
        name = (sub.findtext("SubDescription") or "").strip() or cue_name
        if kind == "F":
            return self._audio(sub, name, who, box)
        if kind == "A":
            pictures = self._pictures(sub, name)
            if len(pictures) <= 1:
                return pictures
            scene = Cue(name=name, media_type=MediaType.GROUP, file_path="", layer=1,
                        group_mode=GroupMode.SEQUENCE.value, collapsed=True)
            for p in pictures:
                p.parent_id = scene.cue_id  # the scene shows them one after another
            return [scene, *pictures]
        if kind == "P":
            group, tracks = self._playlist(sub, name)
            return [group, *tracks] if tracks else []
        if kind in ("E", "N"):
            text = rtf_to_text(sub.findtext("MemoRTFText") or "") or name
            return [self._action(ACTION_NOTE, name, text=text)]
        if kind == "Q":
            action = self._action(ACTION_CALL, name, target=ACTION_TARGET_CUES)
            self.pending.append((action, who, {"labels": [sub.findtext("CallCue") or ""]}))
            return [action]
        if kind == "G":
            action = self._action(ACTION_GOTO, name, target=ACTION_TARGET_CUES, goto_play=False)
            self.pending.append((action, who, {"labels": [sub.findtext("GoToCue") or sub.findtext("GotoCue") or ""]}))
            return [action]
        if kind == "L":
            rel = (sub.findtext("LCAction") or "").strip().lower() == "rel"
            db = _db(sub.findtext("LCReqdDBLevel0"))
            spec = {"target": ACTION_TARGET_CUES, "duration": _ms(sub.findtext("LCTime0")),
                    "mode": "relative" if rel else "absolute", "db": db, "level": _db_to_level(str(db))}
            action = self._action(ACTION_LEVEL, name, **spec)
            self.pending.append((action, who, {"labels": [sub.findtext("LCCue") or ""]}))
            if sub.findtext("LCReqdPan0"):
                box.append((W_PAN, who, 1, ""))
            return [action]
        if kind == "S":
            return self._sfr(sub, name, who, box)
        box.append((W_SUB, who, 1, kind or "?"))
        return []

    def _sfr(self, sub: ET.Element, name: str, who: str, box: list) -> list[Cue]:
        kinds = {"stop": ACTION_STOP, "fadeout": ACTION_FADE, "release": ACTION_RELEASE,
                 "fadeouthib": ACTION_PAUSE, "hibernate": ACTION_PAUSE, "resumehib": ACTION_RESUME,
                 "resume": ACTION_RESUME}
        out: list[Cue] = []
        by_kind: dict[tuple[str, str], Cue] = {}
        i = 0
        while sub.find(f"SFRAction{i}") is not None:
            what = (sub.findtext(f"SFRAction{i}") or "").strip().lower()
            scope = (sub.findtext(f"SFRCueType{i}") or "sel").strip().lower()
            label = (sub.findtext(f"SFRCue{i}") or "").strip()
            i += 1
            kind = kinds.get(what)
            if kind is None:
                box.append((W_SFR, who, 1, what))
                continue
            target = ACTION_TARGET_ALL if scope == "all" else ACTION_TARGET_CUES
            key = (what, target)
            action = by_kind.get(key)
            if action is None:
                action = self._action(kind, name if not out else f"{name} ({len(out) + 1})", target=target)
                by_kind[key] = action
                out.append(action)
                self.pending.append((action, who, {"labels": [], "sfr": what}))
            if target == ACTION_TARGET_CUES:
                entry = next(p for p in self.pending if p[0] is action)
                entry[2]["labels"].append(label if scope != "prev" else "\x00prev")
        return out

    # ── one SCS cue ──
    def read_cue(self, el: ET.Element) -> None:
        label = (el.findtext("CueId") or "").strip()
        desc = (el.findtext("Description") or "").strip()
        who = f"{label} {desc}".strip()
        box: list[tuple[str, str, int, str]] = []
        made: list[list[Cue]] = []   # units: a row with the rows inside it (a scene and its cues)
        rel_starts: list[tuple[float, str]] = []
        for sub in el.findall("Sub"):
            delay = (_ms(sub.findtext("RelStartTime")), (sub.findtext("RelStartMode") or "").strip())
            for cue in self._sub_cues(sub, desc, who, box):
                if cue.parent_id is None or not made:
                    made.append([cue])        # e.g. a stop and a fade of one SCS sub-cue: two units
                    rel_starts.append(delay)
                else:
                    made[-1].append(cue)
        if not made:
            # Nothing maps (e.g. only lighting): a note keeps its place in the list and says what was there.
            note = self._action(ACTION_NOTE, desc or label, text=f"SCS {who}")
            made, rel_starts = [[note]], [(0.0, "")]
        how = (el.findtext("ActivationMethod") or "manual").strip().lower()
        if len(made) == 1:
            top, children = made[0][0], made[0][1:]
            if desc:
                top.name = desc
            block = [top, *children]
            rows = [top]
        elif how == "auto" and all(len(u) == 1 and u[0].media_type != MediaType.GROUP for u in made):
            # Starts by itself: no scene (a scene cannot wait for another cue) - its parts on rows of their
            # own, each started relative to the same cue with its own delay (second pass).
            block = rows = [u[0] for u in made]
            for row, (delay, mode) in zip(rows, rel_starts):
                row.pre_delay = delay
                if mode.startswith("ae"):
                    box.append((W_AFTER_SUB, who, 1, ""))
            top = rows[0]
        else:
            top = Cue(name=desc or label, media_type=MediaType.GROUP, file_path="",
                      group_mode=GroupMode.SIMULTANEOUS.value, collapsed=False)
            block = [top]
            rows = [top]
            for cues, (delay, mode) in zip(made, rel_starts):
                head = cues[0]
                if head.media_type == MediaType.GROUP:
                    # A scene inside a scene is not used: the picture scene / playlist goes on its own row
                    # after this scene and waits for its own GO.
                    box.append((W_GROUP_START, f"{who} – {head.name}", 1, ""))
                    self.extra_tops.append((top, cues))
                    continue
                for cue in cues:
                    cue.parent_id = top.cue_id
                    cue.pre_delay = delay
                    block.append(cue)
                if mode.startswith("ae"):
                    box.append((W_AFTER_SUB, who, 1, ""))
        self.rows_of[top.cue_id] = list(rows)
        self.targets_of[top.cue_id] = list(rows)
        top.q_label = label
        self._apply_page(el, top)
        if (el.findtext("Enabled") or el.findtext("CueEnabled") or "1").strip() == "0":
            top.enabled = False
        self.out.extend(block)
        self.top_order.append(top)
        if label:
            self.label_to_top[label] = top
            media = next((c for c in block if c.media_type.has_file), None)
            if media is not None:
                self.label_to_media[label] = media
        self.starts.append((top, el, who))
        merged: dict[tuple[str, str, str], int] = {}  # the same thing twice in one cue: once, counted
        for kind, name, count, detail in box:
            merged[(kind, name, detail)] = merged.get((kind, name, detail), 0) + count
        self.warnings.setdefault(top.cue_id, []).extend((k, n, c, d) for (k, n, d), c in merged.items())

    @staticmethod
    def _apply_page(el: ET.Element, cue: Cue) -> None:
        page = el.findtext("PageNo") or el.findtext("Page") or ""
        when = el.findtext("WhenReqd") or el.findtext("WhenRequired") or ""
        cue.script_page = page.strip()[:20]
        cue.script_line = when.strip()[:300]

    # ── second pass: how cues start, what actions act on ──
    def resolve(self) -> None:
        tops = self.top_order
        for top, el, who in self.starts:
            how = (el.findtext("ActivationMethod") or "manual").strip().lower()
            if how in ("", "manual"):
                continue
            rows = self.rows_of.get(top.cue_id, [top])
            has_group = any(r.media_type == MediaType.GROUP for r in rows)
            if how in ("hot", "callq") and has_group:
                # A scene / playlist outside the GO order would leave its cues on GO (they do not know
                # their scene waits): it stays on GO and the teacher is told.
                if how == "hot":
                    key = (el.findtext("Hotkey") or "").strip()
                    hint = (el.findtext("HotkeyLabel") or "").strip()
                    top.notes = top.notes or f"⌨ {key}: {hint}".strip(": ")
                self.warn(top, W_GROUP_START, who, 1, how)
                continue
            if how == "hot":
                key = (el.findtext("Hotkey") or "").strip()
                top.adlib = True
                top.hotkey = key[:1].upper() if len(key) == 1 and key.isalnum() else ""
                label = (el.findtext("HotkeyLabel") or "").strip()
                if label and not top.notes:
                    top.notes = label
                if not top.hotkey:
                    self.warn(top, W_KEY, who, 1, key)
                continue
            if how == "callq":
                top.call_only = True
                continue
            if how != "auto":
                self.warn(top, W_START, who, 1, how)
                continue
            ref_label = (el.findtext("AutoActivateCue") or "").strip()
            pos = tops.index(top)
            if not ref_label or (el.findtext("AutoActivateCueType") or "").strip().lower() == "prev":
                ref_top = tops[pos - 1] if pos > 0 else None
                ref_label = ref_top.q_label if ref_top is not None else ""
            else:
                ref_top = self.label_to_top.get(ref_label)
            when = {"start": "start", "end": "end", "b4end": "before_end"}.get(
                (el.findtext("AutoActivatePosn") or "start").strip().lower(), "start")
            offset = _ms(el.findtext("AutoActivateTime"))
            if offset > MAX_REL_OFFSET:
                self.warn(top, W_OFFSET, who)
                offset = MAX_REL_OFFSET
            mine = {r.cue_id for r in rows}
            ref_media = self.label_to_media.get(ref_label) if ref_top is not None else None
            if not has_group and ref_media is not None and ref_media.cue_id not in mine \
                    and ref_media.parent_id not in mine:
                self._start_rows(rows, ref_media.cue_id, when, offset)
                continue
            # It follows an action that itself starts relative to a media cue: relative to that cue,
            # the action's own length added ("3 s after the end of a 2 s level change" = 5 s later).
            if not has_group and ref_top is not None and ref_top.media_type == MediaType.ACTION \
                    and ref_top.start_rel_cue and ref_top.start_rel_cue not in mine \
                    and ref_top.start_rel_when in ("start", "end") and when in ("start", "end"):
                self._start_rows(rows, ref_top.start_rel_cue, ref_top.start_rel_when,
                                 ref_top.start_rel_offset + offset
                                 + (_action_seconds(ref_top) if when == "end" else 0.0))
                continue
            # The cue it follows has no media file (a note, a level change...): tie it to the row before,
            # when that row is in the GO order and is not a scene (a scene's own tie is not used).
            row = self.out.index(top)
            before = self.out[row - 1] if row > 0 else None
            ref_rows = self.rows_of.get(ref_top.cue_id, [ref_top]) if ref_top is not None else []
            # (A scene started this way loses a delay: its own Pre-Delay is not used - only without one.)
            if len(rows) == 1 and before is not None and ref_rows and before is ref_rows[-1] \
                    and when != "before_end" and before.media_type != MediaType.GROUP \
                    and not before.adlib and not before.call_only and before.start_rel_cue is None \
                    and (not has_group or offset == 0):
                before.follow_mode = (FollowMode.SIMULTANEOUS if when == "start" else FollowMode.AUTO_FOLLOW).value
                top.pre_delay = round(top.pre_delay + offset, 3)
                continue
            if has_group:
                self.warn(top, W_GROUP_START, who, 1, how)
            else:
                self.warn(top, W_START_REF, who, 1, ref_label)
        for action, who, data in self.pending:
            owner = self._top_of(action)
            labels = data["labels"]
            ids = []
            for label in labels:
                if label == "\x00prev":
                    pos = self.top_order.index(owner) if owner in self.top_order else 0
                    target = self.top_order[pos - 1] if pos > 0 else None
                else:
                    target = self.label_to_top.get(label.strip())
                if target is None:
                    self.warn(owner, W_TARGET, who, 1, label.strip("\x00"))
                    continue
                for cue in self.targets_of.get(target.cue_id, [target]):
                    if cue.cue_id not in ids:
                        ids.append(cue.cue_id)
            spec = dict(action.action_spec)
            if spec.get("target") == ACTION_TARGET_ALL:
                ids = []
            spec["cue_ids"] = ids
            what = data.get("sfr", "")
            if what in ("fadeout", "fadeouthib", "resumehib"):
                times = [self._fade_time(i, "fade_in" if what == "resumehib" else "fade_out") for i in ids]
                seconds = max([t for t in times if t > 0] or [3.0 if what != "resumehib" else 1.0])
                spec["duration" if what == "fadeout" else "sleep_sec"] = seconds
            action.action_spec = sanitize_action_spec(spec)

    def _start_rows(self, rows: list[Cue], ref_id: int, when: str, offset: float) -> None:
        """Every row of one SCS cue starts relative to *ref_id*, each with its own delay added."""
        for row in rows:
            row.start_rel_cue = ref_id
            row.start_rel_when = when
            row.start_rel_offset = round(min(MAX_REL_OFFSET, max(0.0, offset + row.pre_delay)), 3)
            row.pre_delay = 0.0

    def place_extra_tops(self) -> None:
        """A picture scene / playlist that was a sub-cue of a bigger cue: its own row after that cue (in
        the SCS order), waiting for its own GO; a stop / fade aimed at the SCS cue reaches it too."""
        placed: dict[int, set[int]] = {}
        for owner, cues in self.extra_tops:
            done = placed.setdefault(owner.cue_id, set())
            at = self.out.index(owner)
            while at + 1 < len(self.out) and (self.out[at + 1].parent_id == owner.cue_id
                                              or self.out[at + 1].cue_id in done
                                              or self.out[at + 1].parent_id in done):
                at += 1
            self.out[at + 1:at + 1] = cues  # not in top_order: "the previous cue" stays the SCS one
            done.update(c.cue_id for c in cues)
            self.targets_of.setdefault(owner.cue_id, [owner]).append(cues[0])

    def _fade_time(self, cue_id: int, field_name: str) -> float:
        cues = [c for c in self.out if c.cue_id == cue_id or c.parent_id == cue_id]
        return max((float(getattr(c, field_name, 0.0)) for c in cues), default=0.0)

    def _top_of(self, cue: Cue) -> Cue | None:
        if cue.parent_id is None:
            return cue
        return next((c for c in self.out if c.cue_id == cue.parent_id), None)


def read_scs(path: str | Path) -> ScsShow:
    """Read an ``.scs11`` file. Raises ValueError when it is not one."""
    source = Path(path)
    try:
        root = ET.parse(source).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"Not an SCS show (XML error): {exc}") from exc
    if root.tag != "Production":
        raise ValueError("Not an SCS show: no <Production>")
    reader = _Reader(source.parent)
    for el in root.findall("Cue"):
        reader.read_cue(el)
    reader.place_extra_tops()
    reader.resolve()
    for cue in reader.out:
        cue.status = CueStatus.LOADED if (not cue.media_type.has_file or Path(cue.file_path).is_file()) \
            else CueStatus.OFFLINE
    head = root.find("Head")
    title = (head.findtext("Title") or "").strip() if head is not None else ""
    return ScsShow(title=title, cues=reader.out, warnings=reader.warnings)
