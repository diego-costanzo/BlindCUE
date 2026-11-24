"""A show from a template, a school library of sounds and of cues (stage 5, item 5.9). No Qt.

- ``school_show``: the "School show" template - music while the audience
  comes in, three bells, a caption about phones, the lights down, the
  school's logo, the interval with its countdown and music, thanks, the
  closing music and a fade of everything. The music and the logo are cues
  that wait for their file (OFFLINE, "Choose a file…" attaches it); the bell
  comes from the sound library when it has one.
- The sound library is a folder (on this computer, a USB stick or a shared
  drive): its sounds, grouped by subfolder, become a menu; one click adds a
  sound cue after the selection.
- The cue library is a folder of small show files: the selected cues saved
  under a name and inserted into any show later (new ids, links kept - the
  same rules as importing from another show, 5.3).
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from models.cue import Cue, CueStatus, FollowMode, MediaType

from engine.action_cues import default_action_spec

AUDIO_EXT = {".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".wma", ".opus"}
SNIPPET_EXT = ".blindcue"
MAX_LIBRARY_FILES = 2000


def school_show(tr: Callable[[str], str] = lambda s: s, bell: str = "",
                caption_png: Callable[[dict[str, Any]], str] | None = None) -> list[Cue]:
    """The cues of the "School show" template (names through *tr*, captions by *caption_png*)."""

    def waiting(name: str, kind: MediaType, **fields: Any) -> Cue:
        cue = Cue(name=tr(name), media_type=kind, file_path="", layer=2 if kind == MediaType.AUDIO else 1)
        for key, value in fields.items():
            setattr(cue, key, value)
        cue.status = CueStatus.OFFLINE  # waits for its file: "Choose a file…" (5.10)
        return cue

    def bell_cue(name: str) -> Cue:
        cue = Cue(name=tr(name), media_type=MediaType.AUDIO, file_path=bell, layer=2)
        cue.status = CueStatus.LOADED if bell and Path(bell).is_file() else CueStatus.OFFLINE
        return cue

    def action(name: str, kind: str, **spec: Any) -> Cue:
        full = default_action_spec(kind)
        full.update(spec)
        cue = Cue(name=tr(name), media_type=MediaType.ACTION, file_path="", action_spec=full)
        cue.status = CueStatus.LOADED
        return cue

    def caption(text: str, **fields: Any) -> Cue | None:
        if caption_png is None:
            return None
        spec = {"text": tr(text), "position": fields.pop("position", "bottom"), "size": fields.pop("size", 90)}
        cue = Cue(name="📝 " + tr(text).replace("\n", " "), media_type=MediaType.IMAGE,
                  file_path=caption_png(spec))
        cue.text_spec = spec
        cue.layer = 3
        cue.fade_in = cue.fade_out = 0.5
        for key, value in fields.items():
            setattr(cue, key, value)
        cue.status = CueStatus.LOADED
        return cue

    cues = [
        waiting("Musica d'ingresso del pubblico", MediaType.AUDIO, loop=True, fade_in=2.0, fade_out=3.0),
        bell_cue("Campanella – 3 minuti"),
        bell_cue("Campanella – 1 minuto"),
        caption("Per favore spegnete i telefoni", hold_time=8.0),
        bell_cue("Campanella – si comincia"),
        action("Buio: sfuma musica e immagini", "fade", duration=3.0),
        waiting("Logo della scuola", MediaType.IMAGE, fade_in=1.0, fade_out=1.0),
        action("Intervallo: 15 minuti", "countdown", countdown_sec=900.0, text=tr("Intervallo")),
        waiting("Musica dell'intervallo", MediaType.AUDIO, loop=True, fade_in=2.0, fade_out=3.0),
        action("Fine dell'intervallo: sfuma la musica", "fade", duration=3.0),
        caption("Grazie!", position="center", size=140),
        waiting("Musica finale", MediaType.AUDIO, fade_in=1.0, fade_out=5.0),
        action("Fine: sfuma tutto", "fade", duration=5.0),
    ]
    # The captions go with the cue before them ("Simult."): the phones caption with its bell.
    out = [c for c in cues if c is not None]
    for i, cue in enumerate(out[:-1]):
        if out[i + 1].text_spec and cue.media_type == MediaType.AUDIO:
            cue.follow_mode = FollowMode.SIMULTANEOUS.value
    return out


def library_sounds(folder: str | Path) -> list[tuple[str, list[Path]]]:
    """(subfolder name, its sounds in name order); "" = the library's own folder first. Hidden files left out."""
    from engine.quick_start import natural_key

    base = Path(folder)
    if not base.is_dir():
        return []
    groups: dict[str, list[Path]] = {}
    seen = 0
    # os.walk, pruned and stopped early: the menu opens fast even on a big USB stick.
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted((d for d in dirs if not d.startswith((".", "~$", "_"))), key=natural_key)  # "_unused"
        rel = Path(root).relative_to(base)
        group = rel.parts[0] if rel.parts else ""
        for name in sorted(files, key=natural_key):
            if name.startswith((".", "~$")) or Path(name).suffix.lower() not in AUDIO_EXT:
                continue
            groups.setdefault(group, []).append(Path(root) / name)
            seen += 1
            if seen >= MAX_LIBRARY_FILES:
                break
        if seen >= MAX_LIBRARY_FILES:
            break
    return sorted(groups.items(), key=lambda item: (item[0] != "", natural_key(item[0])))


def library_snippets(folder: str | Path) -> list[Path]:
    """The saved cue groups of the cue library, in name order."""
    from engine.quick_start import natural_key

    base = Path(folder)
    if not base.is_dir():
        return []
    return sorted((p for p in base.glob(f"*{SNIPPET_EXT}") if p.is_file() and not p.name.startswith(".")),
                  key=lambda p: natural_key(p.stem))


def safe_file_name(text: str, fallback: str = "cue") -> str:
    """A name Windows accepts for a file: no \\ / : * ? " < > |, no trailing dot or space."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", text or "").strip().rstrip(". ")
    name = re.sub(r"\s+", " ", name)[:80]
    if name.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                        *(f"LPT{i}" for i in range(1, 10))}:
        name = f"_{name}"
    return name or fallback


def with_scene_cues(cues: list[Cue], rows: Iterable[int]) -> list[Cue]:
    """The chosen rows and everything inside the chosen scenes, in list order."""
    ids = {cues[r].cue_id for r in rows if 0 <= r < len(cues)}
    grown = True
    while grown:
        grown = False
        for cue in cues:
            if cue.parent_id in ids and cue.cue_id not in ids:
                ids.add(cue.cue_id)
                grown = True
    return [c for c in cues if c.cue_id in ids]
