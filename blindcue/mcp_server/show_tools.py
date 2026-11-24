"""Show-file tools for an AI assistant (stage 1M, M1).

An assistant (Claude Desktop, Claude Code or any MCP client) prepares a show
with these functions: it opens or creates a .blindcue file, adds media,
caption and action cues, groups and orders them, checks the show and saves
it. They work on show FILES, never on the show open in the running program:
saving is refused while the program has that show open.

Everything here is plain Python on top of the program's own model
(``models.cue``, ``models.project_manager``, ``engine.show_engine``), so the
MCP layer in ``server.py`` stays thin and every rule matches the inspector.

Safety rules:
- Files are read and written only inside the folders the user allowed
  (``AccessPolicy``); ``..`` and links that lead outside are refused.
- Media files are never changed or deleted; an existing show is copied to
  ``<name>.blindcue.bak`` before it is overwritten.
- Only names, notes and file names of the show reach the assistant, never
  the content of the media.
"""

from __future__ import annotations

import copy
import json
import ntpath
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from engine.action_cues import default_action_name, default_action_spec, describe_action
from engine.show_engine import block_end, insert_position, relative_cycle
from models.cue import (
    ACTION_KINDS,
    Cue,
    CueStatus,
    FollowMode,
    GroupMode,
    MediaType,
    action_names_one_cue,
    action_needs_target,
    detect_layer_conflicts,
    sanitize_action_spec,
)
from models.project_manager import ProjectManager
from ui.theme import AUDIO_EXT, IMAGE_EXT, VIDEO_EXT

# The pre-show checklist was taken out (2026-11-24): old shows keep theirs, nothing makes a new one.
NEW_ACTION_KINDS = tuple(k for k in ACTION_KINDS if k != "checklist")

SHOW_SUFFIX = ".blindcue"
MAX_SECONDS = 600.0
MAX_LIST_MEDIA = 500
MAX_SCAN_ENTRIES = 5000
MAX_SCAN_DEPTH = 4
DURATION_BUDGET_SEC = 20.0
RECENT_AUTOSAVE_SEC = 15 * 60
_ACTION_KEYS = {"target", "layer", "output", "cue_ids", "duration", "mode", "level", "db", "curve",
                "text", "note_color", "items", "goto_play", "goto_max", "seek_mode", "seek_sec",
                "countdown_sec", "sw_mode", "sleep_sec"}


class ToolError(Exception):
    """A refusal or a wrong argument, told to the assistant in plain words."""


# ── Allowed folders ──────────────────────────────────────────────────────────

class AccessPolicy:
    """Folders the user allowed; every path is checked after resolving links."""

    def __init__(self, roots: list[str | Path]) -> None:
        self.roots = [Path(os.path.abspath(os.path.expanduser(str(r)))).resolve()
                      for r in roots if str(r).strip()]
        self._unc_allowed = any(str(r).startswith(("\\\\", "//")) for r in self.roots)

    def describe(self) -> list[str]:
        return [str(r) for r in self.roots]

    def _textual(self, text: str) -> str:
        """Absolute form of *text* worked out from the string alone (no disk, no network)."""
        if "\x00" in text:
            raise ToolError("Invalid path.")
        if os.name == "nt":
            if text.startswith(("\\\\", "//")) and not self._unc_allowed:
                raise ToolError("Network paths are not allowed.")
            _drive, rest = ntpath.splitdrive(text)
            if ":" in rest:
                raise ToolError("':' is not allowed inside a file name.")
        base = str(self.roots[0]) if self.roots else os.getcwd()
        return os.path.abspath(os.path.join(base, os.path.expanduser(text)))

    def contains(self, raw: str | Path) -> bool:
        """True when *raw* lies in an allowed folder by its text alone (nothing is opened)."""
        try:
            candidate = os.path.normcase(self._textual(str(raw)))
        except ToolError:
            return False
        for root in self.roots:
            base = os.path.normcase(str(root)).rstrip("\\/")
            if candidate == base or candidate.startswith(base + os.sep):
                return True
        return False

    def check(self, raw: str | Path, must_exist: bool = False) -> Path:
        if not self.roots:
            raise ToolError("No folder is allowed. Start the server with --root <folder> "
                            "(the show folder and the media folder).")
        text = str(raw or "").strip()
        if not text:
            raise ToolError("A path is needed.")
        outside = ToolError(f"'{text}' is outside the allowed folders: {', '.join(self.describe())}.")
        if not self.contains(text):
            raise outside
        resolved = Path(self._textual(text)).resolve()  # links and junctions, checked again
        if not any(resolved == root or resolved.is_relative_to(root) for root in self.roots):
            raise outside
        if must_exist and not resolved.exists():
            raise ToolError(f"'{resolved}' does not exist.")
        return resolved


def _is_link(path: str | Path) -> bool:
    text = str(path)
    return os.path.islink(text) or bool(getattr(os.path, "isjunction", lambda _p: False)(text))


def _stamp(path: Path) -> tuple[int, int] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


# ── Media files ──────────────────────────────────────────────────────────────

def media_type_for(path: str | Path) -> MediaType | None:
    ext = Path(path).suffix.lower()
    if ext in VIDEO_EXT:
        return MediaType.VIDEO
    if ext in AUDIO_EXT:
        return MediaType.AUDIO
    if ext in IMAGE_EXT:
        return MediaType.IMAGE
    return None


def media_duration(path: str | Path) -> float | None:
    """Length in seconds through ffprobe, None when unknown (or no ffprobe)."""
    try:
        from engine.audio_analyzer import WaveformAnalyzer
        return WaveformAnalyzer(str(path))._get_duration()
    except Exception:
        return None


# ── Is the show open in the program? ─────────────────────────────────────────

def program_running() -> bool:
    """True while BlindCue runs for this user (its single-instance lock is held)."""
    try:
        from PySide6.QtCore import QCoreApplication, QLockFile, QStandardPaths
        from services.single_instance import default_key

        QCoreApplication.setOrganizationName("BlindCue")
        QCoreApplication.setApplicationName("BlindCue")
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        lock_path = os.path.join(base or tempfile.gettempdir(), default_key() + ".lock")
        if not os.path.exists(lock_path):
            return False
        lock = QLockFile(lock_path)
        lock.setStaleLockTime(0)
        if lock.tryLock(0):
            lock.unlock()
            return False
        return lock.error() == QLockFile.LockError.LockFailedError
    except Exception:
        return False


def open_in_program(path: Path, autosave_file: Path | None = None) -> bool:
    """True when the running program (or one that just crashed) has *path* open."""
    autosave_file = autosave_file or Path.home() / ".config" / "blindcue" / "autosave.json"
    try:
        data = json.loads(autosave_file.read_text(encoding="utf-8"))
        active = data.get("active_project_path")
        if not active or data.get("clean_exit", True):
            return False
        if Path(active).resolve() != path.resolve():
            return False
        saved = datetime.fromisoformat(str(data.get("saved_at")))
        recent = (datetime.now() - saved).total_seconds() < RECENT_AUTOSAVE_SEC
        return recent or program_running()
    except Exception:
        return False


# ── The show being prepared ──────────────────────────────────────────────────

def _float(value: Any, name: str, lo: float = 0.0, hi: float = MAX_SECONDS) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ToolError(f"{name} must be a number.") from None
    if not lo <= number <= hi:
        raise ToolError(f"{name} must be between {lo:g} and {hi:g}.")
    return number


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "yes", "1", "on"):
            return True
        if text in ("false", "no", "0", "off", ""):
            return False
        raise ToolError(f"'{value}' is not true or false.")
    return bool(value)


def _choice(value: Any, name: str, allowed: tuple[str, ...]) -> str:
    text = str(value or "").strip()
    match = next((a for a in allowed if a.lower() == text.lower()), None)
    if match is None:
        raise ToolError(f"{name} must be one of: {', '.join(allowed)}.")
    return match


_FOLLOW = tuple(m.value for m in FollowMode)
_GROUP_MODES = tuple(m.value for m in GroupMode)

# field -> (description for the schema, converter)
EDITABLE: dict[str, tuple[str, Any]] = {
    "name": ("Name shown in the cue list.", lambda v: _text(v, "name", 200, required=True)),
    "notes": ("Director's notes shown to the operator during the show.", lambda v: _text(v, "notes", 2000)),
    "q_label": ("Callout from the script, e.g. 'Q-12'.", lambda v: _text(v, "q_label", 20)),
    "layer": ("Layer 1-3 (pictures and videos on the same layer replace each other; audio defaults to 2, "
              "captions to 3).", lambda v: int(_float(v, "layer", 1, 3))),
    "volume": ("Audio level 0.0-1.0.", lambda v: _float(v, "volume", 0.0, 1.0)),
    "fade_in": ("Fade in, seconds.", lambda v: _float(v, "fade_in")),
    "fade_out": ("Fade out, seconds.", lambda v: _float(v, "fade_out")),
    "in_point": ("Start inside the file, seconds.", lambda v: _float(v, "in_point", 0.0, 86400.0)),
    "out_point": ("End inside the file, seconds (null = end of file).",
                  lambda v: None if v in (None, "", 0) else _float(v, "out_point", 0.0, 86400.0)),
    "loop": ("Repeat the file.", _bool),
    "loop_count": ("Repeats when loop is on (0 = until stopped).", lambda v: int(_float(v, "loop_count", 0, 999))),
    "hold_time": ("Pictures: seconds on screen (0 = until replaced).", lambda v: _float(v, "hold_time", 0.0, 86400.0)),
    "pre_delay": ("Wait after GO before starting, seconds.", lambda v: _float(v, "pre_delay")),
    "post_delay": ("Wait after the end before an Auto-GO, seconds.", lambda v: _float(v, "post_delay")),
    "follow_mode": ("MANUAL (waits for GO), AUTO_FOLLOW (starts the next cue at its end) or SIMULTANEOUS "
                    "(starts the next cue together with this one).", lambda v: _choice(v, "follow_mode", _FOLLOW)),
    "crossfade": ("Pictures/videos: seconds the previous picture on the layer dissolves into this one.",
                  lambda v: _float(v, "crossfade")),
    "fade_others": ("On start, other sounds and videos fade out over these seconds (change of music in one "
                    "cue; 0 = no).", lambda v: _float(v, "fade_others")),
    "exclusive": ("While it plays, a GO by hand is refused (a key scene).", _bool),
    "call_only": ("Started only by a 'call' action (or a jump); GO skips it.", _bool),
    "enabled": ("false = off in this version of the show: the cue never plays.", _bool),
    "start_clock": ("Starts by itself at this time of day during the show ('19:55' or '19:55:30'; '' = with GO). "
                    "More than a minute late: skipped.", lambda v: _clock(v)),
    "audio_output": ("Where a sound or video plays: stage | hall | foldback (monitors for the performers) | mute. Which speakers each is, is set on each computer.",
                     lambda v: _choice(v, "audio_output", ("stage", "hall", "foldback", "mute"))),
    "playback_rate": ("Tempo of a sound or video: 0.5-2.0 (1.0 = as recorded).",
                      lambda v: _float(v, "playback_rate", 0.5, 2.0)),
    "keep_pitch": ("With a tempo other than 1.0: keep the pitch of the notes.", _bool),
    "script_page": ("Page of the script the cue is on (printed lists).", lambda v: _text(v, "script_page", 20)),
    "script_line": ("The line (words) of the script the cue comes on (printed lists).",
                    lambda v: _text(v, "script_line", 300)),
    "confirm_start": ("Starts only after the director's OK (Enter or the OK button).", _bool),
    "adlib": ("Effect on demand: outside the GO order, started by its key or tile.", _bool),
    "hotkey": ("Effect key: one letter or digit.", lambda v: _hotkey(v)),
    "hotkey_mode": ("Effect key: trigger (again = from the top), toggle (start/stop), note (plays while "
                    "held).", lambda v: _choice(v, "hotkey_mode", ("trigger", "toggle", "note"))),
    "color": ("Colour mark in the list, '#RRGGBB' or ''.", lambda v: _color(v)),
    "output_target": ("Projector output A or B (B only with two outputs).",
                      lambda v: _choice(v, "output_target", ("A", "B"))),
    "start_rel_cue": ("Start by itself relative to this cue_id (null = with GO). Such a cue is outside the "
                      "GO order.", lambda v: None if v in (None, "", 0) else int(_float(v, "start_rel_cue", 1, 10**9))),
    "start_rel_when": ("With start_rel_cue: start (N s after it starts), end (N s after it ends), "
                       "before_end (N s before it ends) or marker (N s after a marker of it, start_rel_marker).",
                       lambda v: _choice(v, "start_rel_when", ("start", "end", "before_end", "marker"))),
    "start_rel_marker": ("With start_rel_when marker: the marker id in the reference cue.",
                         lambda v: None if v in (None, "", 0) else int(_float(v, "start_rel_marker", 1, 10**6))),
    "markers": ("Named points of a sound/video file: [{\"name\": \"chorus\", \"sec\": 30.5}, ...] "
                "(ids are given in order).", lambda v: _markers(v)),
    "start_rel_offset": ("Seconds for start_rel_when.", lambda v: _float(v, "start_rel_offset")),
    "group_mode": ("Groups: STEP (one GO per item), SEQUENCE (one GO plays all in a row), SIMULTANEOUS "
                   "(all together), RANDOM, LOOP.", lambda v: _choice(v, "group_mode", _GROUP_MODES)),
}


def _text(value: Any, name: str, limit: int, required: bool = False) -> str:
    text = str(value if value is not None else "").strip()
    if required and not text:
        raise ToolError(f"{name} must not be empty.")
    if len(text) > limit:
        raise ToolError(f"{name} is longer than {limit} characters.")
    return text


def _markers(value: Any) -> list[dict]:
    """Checked marker entries; an entry without id gets one in ``_keep_marker_ids`` (ids must stay stable)."""
    if not isinstance(value, list) or len(value) > 200:
        raise ToolError("markers must be a list (at most 200) of {name, sec}.")
    raw = []
    for i, item in enumerate(value, 1):
        if not isinstance(item, dict) or "sec" not in item:
            raise ToolError("each marker needs sec (seconds in the file) and may have a name.")
        mid = 0 if item.get("id") in (None, "", 0) else int(_float(item["id"], "id", 1, 10**6))
        raw.append({"id": mid, "name": _text(item.get("name", f"◆{i}"), "name", 30),
                    "sec": _float(item["sec"], "sec", 0.0, 86400.0)})
    return raw


def _keep_marker_ids(old: list[dict], new: list[dict]) -> list[dict]:
    """A marker given without id keeps the id of the old marker at the same time, else gets a new one."""
    from models.cue import sanitize_markers

    taken = {m["id"] for m in new if m["id"]}
    if len(taken) != len([m for m in new if m["id"]]):
        raise ToolError("Two markers have the same id.")
    next_id = max(taken | {m["id"] for m in old} | {0}) + 1
    out = []
    for m in new:
        if not m["id"]:
            same = next((o["id"] for o in old if abs(o["sec"] - m["sec"]) < 0.01 and o["id"] not in taken), None)
            if same is None:
                same, next_id = next_id, next_id + 1
            taken.add(same)
            m = {**m, "id": same}
        out.append(m)
    return sanitize_markers(out)


def _clock(value: Any) -> str:
    from engine.clock_plan import normalize_clock

    text = str(value or "").strip()
    if text and not normalize_clock(text):
        raise ToolError("start_clock must look like '19:55' or '19:55:30' (or '' for none).")
    return normalize_clock(text) if text else ""


def _hotkey(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text and (len(text) != 1 or not text.isalnum() or not text.isascii()):
        raise ToolError("hotkey must be one letter A-Z or one digit 0-9 (or '' for none).")
    return text


def _color(value: Any) -> str:
    text = str(value or "").strip()
    if text and (len(text) != 7 or not text.startswith("#")
                 or any(ch not in "0123456789abcdefABCDEF" for ch in text[1:])):
        raise ToolError("color must look like '#RRGGBB' (or '' for none).")
    return text


def _strict_action(kind: str, raw: Any, base: dict[str, Any], new: bool) -> dict[str, Any]:
    """An action description from the assistant: every key and value checked, nothing guessed."""
    if not isinstance(raw, dict):
        raise ToolError("The action description must be an object, e.g. {\"target\": \"cues\", \"cue_ids\": [3]}.")
    unknown = set(raw) - _ACTION_KEYS - {"kind"}
    if unknown:
        raise ToolError(f"Unknown action keys: {', '.join(sorted(unknown))}. Known: {', '.join(sorted(_ACTION_KEYS))}.")
    spec = dict(base)
    spec.update({k: v for k, v in raw.items() if k != "kind"})
    if "cue_ids" in raw and "target" not in raw:
        spec["target"] = "cues"
    if action_needs_target(kind):
        if new and "target" not in raw and "cue_ids" not in raw:
            raise ToolError(f"Say what the {kind} acts on: target 'cues' with cue_ids, 'layer' with layer "
                            "(1-3), or 'all' (everything that plays).")
        spec["target"] = _choice(spec.get("target"), "target", ("all", "layer", "cues"))
    if "layer" in raw:
        spec["layer"] = int(_float(raw["layer"], "layer", 1, 3))
    if "output" in raw:
        spec["output"] = _choice(raw["output"], "output", ("A", "B"))
    if "cue_ids" in raw:
        ids = raw["cue_ids"]
        if not isinstance(ids, list) or not all(isinstance(i, int) and i > 0 for i in ids):
            raise ToolError("cue_ids must be a list of cue_id numbers.")
    if "duration" in raw:
        _float(raw["duration"], "duration", 0.0, MAX_SECONDS)
    if "mode" in raw:
        spec["mode"] = _choice(raw["mode"], "mode", ("absolute", "relative"))
    if "level" in raw:
        _float(raw["level"], "level", 0.0, 1.0)
    if "db" in raw:
        _float(raw["db"], "db", -60.0, 20.0)
    if "curve" in raw:
        spec["curve"] = _choice(raw["curve"], "curve", ("log", "scurve", "linear"))
    if "text" in raw:
        spec["text"] = _text(raw["text"], "text", 2000)
    if "note_color" in raw:
        spec["note_color"] = _color(raw["note_color"]) or base.get("note_color", "")
    if action_names_one_cue(kind):
        ids = spec.get("cue_ids") or []
        if not isinstance(ids, list) or len(ids) != 1:
            raise ToolError(f"A {kind} names exactly one cue: cue_ids [cue_id].")
    if "goto_play" in raw:
        spec["goto_play"] = _bool(raw["goto_play"])
    if "goto_max" in raw:
        spec["goto_max"] = int(_float(raw["goto_max"], "goto_max", 0, 999))
    if "seek_mode" in raw:
        spec["seek_mode"] = _choice(raw["seek_mode"], "seek_mode", ("absolute", "relative", "before_end"))
    if "seek_sec" in raw:
        _float(raw["seek_sec"], "seek_sec", -86400.0, 86400.0)
    if "countdown_sec" in raw:
        _float(raw["countdown_sec"], "countdown_sec", 0.0, 14400.0)
    if "sleep_sec" in raw:
        _float(raw["sleep_sec"], "sleep_sec", 0.0, 600.0)
    if "sw_mode" in raw:
        _choice(raw["sw_mode"], "sw_mode", ("start", "stop", "reset"))
    if "items" in raw:
        items = raw["items"]
        if not isinstance(items, list) or len(items) > 30 or \
                not all(isinstance(i, str) and 0 < len(i.strip()) <= 200 for i in items):
            raise ToolError("items must be a list of up to 30 lines (each 1-200 characters).")
    spec["kind"] = kind
    return sanitize_action_spec(spec)


class ShowSession:
    """One show file prepared by the assistant (one at a time)."""

    def __init__(self, policy: AccessPolicy, autosave_file: Path | None = None) -> None:
        self.policy = policy
        self.autosave_file = autosave_file
        # Never the program's own autosave folder.
        self._pm = ProjectManager(autosave_dir=Path(tempfile.gettempdir()) / "blindcue-assistant")
        self.path: Path | None = None
        self.cues: list[Cue] = []
        self.settings: dict[str, Any] = {}
        self.current_index = -1
        self.modified = False
        self.bundled = False
        self._stamp: tuple[int, int] | None = None   # the file as we read or wrote it last
        self._backed_up = False                       # one .bak per opened show

    # ── opening and saving ──
    def _need_show(self) -> None:
        if self.path is None:
            raise ToolError("No show is open: call new_show or open_show first.")

    def _show_path(self, raw: str) -> Path:
        text = str(raw or "").strip()
        if text and not text.lower().endswith(SHOW_SUFFIX):
            text += SHOW_SUFFIX
        return self.policy.check(text)

    def _outside_files(self) -> list[str]:
        """Files the show uses outside the allowed folders (a portable save would copy them in)."""
        found = [f"'{c.name}': {c.file_path}" for c in self.cues
                 if c.media_type.has_file and c.file_path and not c.text_spec and not self.policy.contains(c.file_path)]
        layer0 = self.settings.get("layer0_image")
        if isinstance(layer0, str) and layer0 and not self.policy.contains(layer0):
            found.append(f"Layer 0 picture: {layer0}")
        for surface in self.settings.get("surfaces") or []:
            mask = surface.get("mask_image_path") if isinstance(surface, dict) else None
            if isinstance(mask, str) and mask and not self.policy.contains(mask):
                found.append(f"surface mask: {mask}")
        return found

    def new_show(self, path: str) -> dict[str, Any]:
        target = self._show_path(path)
        if target.exists():
            raise ToolError(f"'{target}' already exists: open it with open_show, or choose another name.")
        self.path, self.cues, self.settings, self.current_index = target, [], {}, -1
        self.modified, self.bundled = True, False
        self._stamp, self._backed_up = None, False
        return self.summary()

    def open_show(self, path: str) -> dict[str, Any]:
        target = self.policy.check(path, must_exist=True)
        if target.suffix.lower() != SHOW_SUFFIX:
            raise ToolError(f"'{target.name}' is not a show file ({SHOW_SUFFIX}).")
        try:
            cues, current, settings = self._pm.load_project(target)
        except Exception as exc:
            raise ToolError(f"The show cannot be read: {exc}") from None
        for cue in cues:
            cue.status = CueStatus.LOADED
        self.path, self.cues, self.settings, self.current_index = target, cues, settings, current
        self.modified = False
        # Portable = takes its media from <name>_media; worked out from the text of the paths.
        media_dir = os.path.normcase(os.path.abspath(str(self._pm.media_dir_for(target))))
        self.bundled = any(c.media_type.has_file and c.file_path and not c.text_spec and
                           os.path.normcase(os.path.abspath(c.file_path)).startswith(media_dir + os.sep)
                           for c in cues)
        self._stamp, self._backed_up = _stamp(target), False
        result = self.summary()
        warnings = []
        if open_in_program(target, self.autosave_file):
            warnings.append("This show is open in BlindCue right now: you can read it, but saving is "
                            "refused until it is closed there (or save it under another name).")
        outside = self._outside_files()
        if outside:
            warnings.append(f"{len(outside)} file(s) of this show are outside the allowed folders "
                            f"(e.g. {outside[0]}); they are not checked, and a portable show cannot be "
                            "saved until they are replaced.")
        if warnings:
            result["warning"] = " ".join(warnings)
        return result

    def save_show(self, path: str | None = None) -> dict[str, Any]:
        self._need_show()
        assert self.path is not None
        target = self._show_path(path) if path else self.path
        if open_in_program(target, self.autosave_file):
            raise ToolError("BlindCue has this show open right now: close it there first, or save it "
                            "under another name (save_show with a new path).")
        same_file = target == self.path
        if same_file and _stamp(target) != self._stamp:
            raise ToolError("The show file changed on disk since it was opened (saved in BlindCue?): "
                            "call open_show again so nothing is lost, or save under another name.")
        if not same_file and target.exists():
            raise ToolError(f"'{target.name}' already exists: choose another name.")
        if self.bundled:
            outside = self._outside_files()
            if outside:
                raise ToolError("A portable show copies its files next to it, and these are outside the "
                                "allowed folders: " + "; ".join(outside[:10]) +
                                ". Replace or delete those cues first.")
        backup = None
        if same_file and target.exists() and not self._backed_up:
            backup = target.with_name(target.name + ".bak")
            fd, tmp = tempfile.mkstemp(prefix=".bak-", dir=str(target.parent))
            os.close(fd)
            shutil.copy2(target, tmp)
            os.replace(tmp, backup)  # replaces a link sitting at the .bak name, never writes through it
            self._backed_up = True
        if self.bundled:
            saved, problems, _copied = self._pm.save_project_bundled(
                target, self.cues, self.current_index, self.settings)
        else:
            saved, problems = self._pm.save_project(target, self.cues, self.current_index, self.settings), []
        if not saved:
            raise ToolError(f"The show could not be written to '{target}'.")
        if not same_file:
            self._backed_up = True  # a new file: nothing of the teacher's to keep
        self.path, self.modified, self._stamp = target, False, _stamp(target)
        result: dict[str, Any] = {"saved": str(target), "cues": len(self.cues)}
        if backup is not None:
            result["backup"] = str(backup)
        if problems:
            result["problems"] = problems
        return result

    # ── reading ──
    def _row(self, cue_id: int) -> int:
        row = next((i for i, c in enumerate(self.cues) if c.cue_id == int(cue_id)), -1)
        if row < 0:
            raise ToolError(f"There is no cue with cue_id {cue_id}: call list_cues.")
        return row

    def _cue(self, cue_id: int) -> Cue:
        return self.cues[self._row(cue_id)]

    def _describe(self, row: int, cue: Cue) -> dict[str, Any]:
        item: dict[str, Any] = {
            "number": row + 1,
            "cue_id": cue.cue_id,
            "name": cue.name,
            "type": cue.media_type.value,
        }
        if cue.parent_id is not None:
            item["group_id"] = cue.parent_id
        if cue.media_type == MediaType.ACTION:
            item["action"] = describe_action(cue.action_spec, self.cues)
        elif cue.media_type == MediaType.GROUP:
            item["group_mode"] = cue.group_mode
        else:
            item["layer"] = cue.layer
            item["file"] = "(caption)" if cue.text_spec else Path(cue.file_path).name
            if cue.text_spec:
                item["text"] = cue.text_spec.get("text", "")
        if cue.follow_mode != FollowMode.MANUAL.value:
            item["follow_mode"] = cue.follow_mode
        if cue.adlib:
            item["effect_key"] = cue.hotkey or "(tile only)"
        if cue.notes:
            item["notes"] = cue.notes
        return item

    def list_cues(self) -> list[dict[str, Any]]:
        self._need_show()
        return [self._describe(i, c) for i, c in enumerate(self.cues)]

    def get_cue(self, cue_id: int) -> dict[str, Any]:
        self._need_show()
        cue = self._cue(cue_id)
        data = cue.to_dict()
        for noisy in ("status", "volume_points", "opacity_points", "sections", "mask_polygon"):
            if not data.get(noisy):
                data.pop(noisy, None)
        return data

    def summary(self) -> dict[str, Any]:
        self._need_show()
        counts: dict[str, int] = {}
        for cue in self.cues:
            counts[cue.media_type.value] = counts.get(cue.media_type.value, 0) + 1
        return {"show": str(self.path), "cues": len(self.cues), "by_type": counts,
                "unsaved_changes": self.modified, "portable": self.bundled}

    def list_media(self, folder: str, recursive: bool = False, durations: bool = True) -> dict[str, Any]:
        """Media files in *folder* (sub-folders up to a few levels with *recursive*), with limits."""
        base = self.policy.check(folder, must_exist=True)
        if not base.is_dir():
            raise ToolError(f"'{base}' is not a folder.")
        found: list[dict[str, Any]] = []
        notes: list[str] = []
        scanned = 0
        budget_end = time.monotonic() + DURATION_BUDGET_SEC
        for dirpath, dirnames, filenames in os.walk(base):
            depth = len(Path(dirpath).relative_to(base).parts)
            dirnames[:] = sorted(d for d in dirnames if not _is_link(os.path.join(dirpath, d))) \
                if recursive and depth < MAX_SCAN_DEPTH else []
            for name in sorted(filenames):
                scanned += 1
                path = Path(dirpath) / name
                kind = media_type_for(path)
                if kind is None or _is_link(path):
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                item: dict[str, Any] = {"path": str(path), "type": kind.value, "size_mb": round(size / 1_048_576, 2)}
                if durations and kind != MediaType.IMAGE:
                    if time.monotonic() < budget_end:
                        seconds = media_duration(path)
                        if seconds:
                            item["seconds"] = round(seconds, 1)
                    elif "lengths" not in " ".join(notes):
                        notes.append("Lengths were measured only for the first files (time limit).")
                found.append(item)
                if len(found) >= MAX_LIST_MEDIA or scanned >= MAX_SCAN_ENTRIES:
                    break
            if len(found) >= MAX_LIST_MEDIA or scanned >= MAX_SCAN_ENTRIES:
                notes.append("The list was cut: choose a smaller folder.")
                break
        result: dict[str, Any] = {"files": found}
        if notes:
            result["note"] = " ".join(notes)
        return result

    # ── adding ──
    def _insert(self, cue: Cue, after_cue_id: int | None) -> dict[str, Any]:
        anchor = self._row(after_cue_id) if after_cue_id is not None else -1
        position, parent_id = insert_position(self.cues, anchor)
        cue.parent_id = parent_id
        cue.status = CueStatus.LOADED
        self.cues.insert(position, cue)
        self.modified = True
        return self._describe(position, cue)

    def _apply(self, cue: Cue, fields: dict[str, Any] | None) -> None:
        old_markers = list(getattr(cue, "markers", []))
        for key, value in (fields or {}).items():
            if key not in EDITABLE:
                raise ToolError(f"'{key}' cannot be set here. Settable: {', '.join(sorted(EDITABLE))}.")
            setattr(cue, key, EDITABLE[key][1](value))
        if "markers" in (fields or {}):
            cue.markers = _keep_marker_ids(old_markers, cue.markers)
            kept = {m["id"] for m in cue.markers}
            for i, other in enumerate(self.cues):
                if (other is not cue and other.start_rel_cue == cue.cue_id and other.start_rel_when == "marker"
                        and other.start_rel_marker not in kept):
                    raise ToolError(f"Marker {other.start_rel_marker} is used by #{i + 1} '{other.name}' "
                                    "(it starts there): keep that marker and its id.")
        if cue.start_clock and cue.start_rel_cue is not None:
            raise ToolError("A cue starts at a time of day (start_clock) or relative to another cue "
                            "(start_rel_cue), not both.")
        if cue.out_point is not None and cue.out_point <= cue.in_point:
            raise ToolError("out_point must be after in_point.")
        if cue.media_type in (MediaType.GROUP, MediaType.ACTION) and cue.adlib:
            raise ToolError("Only media cues can be effects on demand.")
        ref = cue.start_rel_cue
        if ref is not None:
            if ref == cue.cue_id or not any(c.cue_id == ref and c.media_type.has_file for c in self.cues):
                raise ToolError(f"start_rel_cue {ref} is not another video, sound or picture cue of this show.")
            if relative_cycle(self.cues, cue.cue_id, ref):
                raise ToolError("That cue already starts from this one: they would start each other forever.")
            if cue.start_rel_when == "marker":
                target = next(c for c in self.cues if c.cue_id == ref)
                if not any(m["id"] == cue.start_rel_marker for m in target.markers):
                    raise ToolError("start_rel_marker is not a marker of that cue (see its markers).")

    def add_media_cue(self, path: str, after_cue_id: int | None = None,
                      fields: dict[str, Any] | None = None) -> dict[str, Any]:
        self._need_show()
        media = self.policy.check(path, must_exist=True)
        kind = media_type_for(media)
        if kind is None or not media.is_file():
            raise ToolError(f"'{media.name}' is not a video, audio or picture file BlindCue plays.")
        cue = Cue(name=media.name, media_type=kind, file_path=str(media))
        if kind == MediaType.AUDIO:
            cue.layer = 2  # as in the program: music never shares a player with pictures
        self._apply(cue, fields)
        errors = cue.validate()
        if errors:
            raise ToolError("; ".join(errors))
        return self._insert(cue, after_cue_id)

    def add_text_cue(self, text: str, after_cue_id: int | None = None, size: int = 90,
                     position: str = "bottom", color: str = "#ffffff",
                     fields: dict[str, Any] | None = None) -> dict[str, Any]:
        self._need_show()
        from engine.text_render import normalize_spec, text_cue_name

        spec = normalize_spec({"text": _text(text, "text", 1000, required=True), "size": size,
                               "position": _choice(position, "position", ("top", "center", "bottom")),
                               "color": _color(color) or "#ffffff"})
        cue = Cue(name=text_cue_name(spec), media_type=MediaType.IMAGE, file_path=render_caption(spec))
        cue.text_spec = spec
        cue.layer = 3
        cue.fade_in = cue.fade_out = 0.5
        self._apply(cue, fields)
        return self._insert(cue, after_cue_id)

    def add_action_cue(self, kind: str, after_cue_id: int | None = None,
                       spec: dict[str, Any] | None = None, name: str | None = None,
                       fields: dict[str, Any] | None = None) -> dict[str, Any]:
        self._need_show()
        kind = _choice(kind, "kind", NEW_ACTION_KINDS)
        clean = _strict_action(kind, spec or {}, default_action_spec(kind), new=True)
        missing = [cid for cid in clean.get("cue_ids", []) if not any(c.cue_id == cid for c in self.cues)]
        if missing:
            raise ToolError(f"Unknown target cue_ids: {missing}.")
        if action_needs_target(kind) and clean["target"] == "cues" and not clean["cue_ids"]:
            raise ToolError("target 'cues' needs cue_ids (or use target 'all' / 'layer').")
        cue = Cue(name=_text(name, "name", 200) or default_action_name(kind), media_type=MediaType.ACTION,
                  file_path="", action_spec=clean)
        self._apply(cue, fields)
        return self._insert(cue, after_cue_id)

    def add_group(self, name: str, cue_ids: list[int] | None = None, mode: str = "STEP",
                  after_cue_id: int | None = None) -> dict[str, Any]:
        """A scene: a group cue followed by its items (the listed cues move under it)."""
        self._need_show()
        group = Cue(name=_text(name, "name", 200, required=True), file_path="", media_type=MediaType.GROUP,
                    group_mode=_choice(mode, "mode", _GROUP_MODES), color="#6366f1", layer=1,
                    status=CueStatus.LOADED)
        ids = list(dict.fromkeys(int(c) for c in (cue_ids or [])))
        if not ids:
            return self._insert(group, after_cue_id)
        rows = sorted(self._row(cid) for cid in ids)
        members = [self.cues[r] for r in rows]   # in show order
        if any(m.media_type == MediaType.GROUP for m in members):
            raise ToolError("A group cannot be put inside a new group here.")
        if len({m.parent_id for m in members}) > 1:
            raise ToolError("The cues of one scene must come from one place (all outside groups, or "
                            "all from the same group).")
        taken = {id(m) for m in members}
        rest = [c for c in self.cues if id(c) not in taken]
        position = sum(1 for c in self.cues[:rows[0]] if id(c) not in taken)
        group.parent_id = members[0].parent_id
        for member in members:
            member.parent_id = group.cue_id
        self.cues = rest[:position] + [group] + members + rest[position:]
        self.modified = True
        return self._describe(position, group)

    # ── changing ──
    def update_cue(self, cue_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        self._need_show()
        row = self._row(cue_id)
        cue = self.cues[row]
        before = copy.deepcopy(cue)
        text = (fields or {}).get("text")
        try:
            plain = {k: v for k, v in (fields or {}).items() if k not in ("text", "action")}
            self._apply(cue, plain)
            if text is not None:
                if not cue.text_spec:
                    raise ToolError("'text' can be changed only on a caption cue.")
                from engine.text_render import normalize_spec, text_cue_name

                spec = normalize_spec({**cue.text_spec, "text": _text(text, "text", 1000, required=True)})
                cue.text_spec, cue.file_path = spec, render_caption(spec)
                if "name" not in plain:
                    cue.name = text_cue_name(spec)
            if "action" in (fields or {}):
                if cue.media_type != MediaType.ACTION:
                    raise ToolError("'action' can be changed only on an action cue.")
                kind = cue.action_spec["kind"]
                cue.action_spec = _strict_action(kind, fields["action"], cue.action_spec, new=False)
                missing = [i for i in cue.action_spec.get("cue_ids", []) if not any(c.cue_id == i for c in self.cues)]
                if missing:
                    raise ToolError(f"Unknown target cue_ids: {missing}.")
            if cue.media_type.has_file:
                # A missing file is for validate_show: notes of such a cue may still change.
                errors = [e for e in cue.validate() if "not found" not in e.lower()]
                if errors:
                    raise ToolError("; ".join(errors))
        except Exception:
            self.cues[row] = before
            raise
        self.modified = True
        return self._describe(row, cue)

    def move_cue(self, cue_id: int, after_cue_id: int | None = None, to_top: bool = False,
                 into_group_id: int | None = None) -> dict[str, Any]:
        """Move a cue (a group with its items) after another cue, to the top, or to the end of a group."""
        self._need_show()
        if sum(x is not None and x is not False for x in (after_cue_id, into_group_id, to_top or None)) > 1:
            raise ToolError("Give only one of after_cue_id, into_group_id, to_top.")
        row = self._row(cue_id)
        for other in (after_cue_id, into_group_id):
            if other is not None:
                self._row(other)
        end = block_end(self.cues, row)
        block = self.cues[row:end + 1]
        if any(c.cue_id in (after_cue_id, into_group_id) for c in block if c.cue_id is not None):
            raise ToolError("A cue cannot be moved next to or into itself or one of its own items.")
        rest = self.cues[:row] + self.cues[end + 1:]
        if into_group_id is not None:
            g_row = next(i for i, c in enumerate(rest) if c.cue_id == int(into_group_id))
            if rest[g_row].media_type != MediaType.GROUP:
                raise ToolError(f"cue_id {into_group_id} is not a group.")
            position, parent = block_end(rest, g_row) + 1, rest[g_row].cue_id
        elif to_top or after_cue_id is None:
            position, parent = (0 if to_top else len(rest)), None
        else:
            anchor = next(i for i, c in enumerate(rest) if c.cue_id == int(after_cue_id))
            anchor_cue = rest[anchor]
            if anchor_cue.media_type == MediaType.GROUP:
                position, parent = block_end(rest, anchor) + 1, anchor_cue.parent_id
            else:
                position, parent = anchor + 1, anchor_cue.parent_id
        block[0].parent_id = parent
        self.cues = rest[:position] + block + rest[position:]
        self.current_index = min(self.current_index, len(self.cues) - 1)
        self.modified = True
        return self._describe(position, block[0])

    def delete_cue(self, cue_id: int, with_items: bool = False) -> dict[str, Any]:
        """Remove a cue from the show (never its media file); a group's items stay unless *with_items*."""
        self._need_show()
        row = self._row(cue_id)
        cue = self.cues[row]
        gone = {cue.cue_id}
        if cue.media_type == MediaType.GROUP:
            end = block_end(self.cues, row)
            items = self.cues[row + 1:end + 1]
            if with_items:
                gone.update(c.cue_id for c in items)
            else:
                for item in items:
                    if item.parent_id == cue.cue_id:
                        item.parent_id = cue.parent_id
        self.cues = [c for c in self.cues if c.cue_id not in gone]
        for other in self.cues:  # actions aimed at a removed cue forget it
            if other.media_type == MediaType.ACTION and other.action_spec.get("cue_ids"):
                other.action_spec = sanitize_action_spec(
                    {**other.action_spec, "cue_ids": [i for i in other.action_spec["cue_ids"] if i not in gone]})
        self.current_index = min(self.current_index, len(self.cues) - 1)
        self.modified = True
        return {"deleted": sorted(gone), "cues": len(self.cues)}

    # ── checking ──
    def validate_show(self) -> dict[str, Any]:
        self._need_show()
        problems: list[str] = []
        warnings: list[str] = []
        ids = {c.cue_id for c in self.cues}
        for row, cue in enumerate(self.cues):
            ref = f"#{row + 1} '{cue.name}'"
            if cue.media_type.has_file and not cue.text_spec and not self.policy.contains(cue.file_path):
                warnings.append(f"{ref}: its file is outside the allowed folders (not checked).")
            elif cue.media_type.has_file and not cue.text_spec and not Path(cue.file_path).is_file():
                problems.append(f"{ref}: media file missing: {cue.file_path}")
            elif cue.media_type.has_file and not cue.text_spec:
                problems.extend(f"{ref}: {e}" for e in cue.validate() if "not found" not in e.lower())
            if cue.media_type == MediaType.ACTION:
                spec = cue.action_spec
                if action_needs_target(spec["kind"]) and spec["target"] == "cues":
                    live = [i for i in spec["cue_ids"] if i in ids]
                    if not live:
                        problems.append(f"{ref}: action without a target cue.")
            if cue.follow_mode != FollowMode.MANUAL.value and row == len(self.cues) - 1:
                warnings.append(f"{ref}: {cue.follow_mode} on the last cue starts nothing.")
            if cue.adlib and cue.follow_mode != FollowMode.MANUAL.value:
                warnings.append(f"{ref}: an effect on demand ignores {cue.follow_mode}.")
            if cue.adlib and not cue.hotkey:
                warnings.append(f"{ref}: effect on demand without a key (only its tile starts it).")
            if cue.start_rel_cue is not None and cue.start_rel_cue not in ids:
                problems.append(f"{ref}: starts relative to a cue that is no longer in the show.")
        names = {c.cue_id: c.name for c in self.cues}
        for cid, conflict in detect_layer_conflicts(self.cues, dual_active=False).items():
            if self._cue(cid).media_type == MediaType.GROUP:
                continue
            others = ", ".join(f"'{n}'" for n in conflict.conflicting_with_names)
            warnings.append(f"'{names.get(cid, cid)}' starts together with {others} on layer "
                            f"{conflict.layer}: only one plays there ({conflict.reason}).")
        return {"ok": not problems, "problems": problems, "warnings": warnings}


def render_caption(spec: dict[str, Any]) -> str:
    """The caption PNG, made like in the program (needs Qt; offscreen is enough)."""
    from engine.text_render import render_text_png

    ensure_qt_gui()
    return render_text_png(spec)


def ensure_qt_gui() -> None:
    """A hidden Qt GUI application for drawing captions (no window is shown)."""
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.instance() is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        QCoreApplication.setOrganizationName("BlindCue")
        QCoreApplication.setApplicationName("BlindCue")
        ensure_qt_gui.app = QGuiApplication([])  # type: ignore[attr-defined]


def cue_schema() -> dict[str, Any]:
    """What can be set on a cue, generated from the rules above (an MCP resource)."""
    return {
        "types": {"VIDEO": "video file", "AUDIO": "audio file (layer 2 by default)",
                  "IMAGE": "picture or caption (captions on layer 3)", "GROUP": "a scene that holds cues",
                  "ACTION": "no file: stop / fade / release / level / opacity / pause / resume / seek of "
                            "other cues, jump / call, a wait, a countdown, a stopwatch, or a note for "
                            "the operator"},
        "fields": {name: desc for name, (desc, _conv) in EDITABLE.items()},
        "action_kinds": list(NEW_ACTION_KINDS),
        "action_spec": {
            "target": "all | layer | cues", "layer": "1-3 (target layer)", "output": "A | B",
            "cue_ids": "[cue_id, ...] (target cues)", "duration": "seconds (fade/level/opacity)",
            "mode": "absolute | relative (level)", "level": "0.0-1.0 (level absolute, opacity)",
            "db": "-60..+20 (level relative)", "text": "note text",
            "goto (jump)": "cue_ids [one cue]; goto_play true = start it, false = only make it the next GO; "
                           "goto_max N = at most N times per run (0 = always)",
            "call": "cue_ids [one cue]: starts it without moving GO (mark that cue call_only)",
            "seek": "target + seek_mode absolute | relative | before_end, seek_sec seconds",
            "countdown": "countdown_sec seconds (0 stops it), text = its title",
            "wait": "duration seconds, then the next cue starts by itself (a delay visible in the list)",
            "pause / resume": "target: pause the sound / video of the targets, or let them play on; "
                              "sleep_sec > 0 = sleep (fade out, then pause) / wake (fade in)",
            "stopwatch": "sw_mode start | stop | reset (a stopwatch on the status bar)",
        },
        "media_extensions": sorted(VIDEO_EXT | AUDIO_EXT | IMAGE_EXT),
    }
