"""Order in the show's files (stage 5, item 5.10). No Qt.

- ``write_zip``: the show and every media file it uses in one ZIP (the same
  layout as a portable show: ``<name>/<name>.blindcue`` and
  ``<name>/<name>_media/...``), so it can be mailed or carried and opened on
  another computer after unpacking. Big playlists may stay out
  (``big_playlist_files``): their cues keep the path of this computer and
  are listed.
- ``unused_media`` / ``set_aside``: files in the show's media folder that no
  cue (nor Layer 0, a surface mask, a backup copy) uses are moved into its
  ``_unused`` subfolder - never deleted.
- ``rename_target`` / ``rename_in_cues`` / ``rename_in_dicts``: a media file
  renamed on disk and every reference to it (all cues, undo steps) updated.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from models.cue import Cue, MediaType

BIG_PLAYLIST_BYTES = 100 * 1024 * 1024
UNUSED_FOLDER = "_unused"
MEDIA_SUFFIX = "_media"


def path_key(path: str | Path) -> str:
    """The same file written two ways ("C:\\A\\b.mp3", "c:/a/B.MP3" on Windows) gives one key."""
    return os.path.normcase(os.path.abspath(str(path)))


def _size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


# ── big playlists ──
def playlists(cues: list[Cue]) -> list[tuple[Cue, int, list[str]]]:
    """(playlist, total bytes of its files, the files) for every playlist of the show."""
    out = []
    for group in cues:
        if group.media_type != MediaType.GROUP or not getattr(group, "playlist", False):
            continue
        files = [c.file_path for c in cues if c.parent_id == group.cue_id and c.media_type.has_file
                 and c.file_path and os.path.isfile(c.file_path)]
        out.append((group, sum(_size(f) for f in files), files))
    return out


def big_playlist_files(cues: list[Cue], limit: int = BIG_PLAYLIST_BYTES) -> set[str]:
    """Path keys of the files of the playlists bigger than *limit* bytes."""
    return {path_key(f) for _group, total, files in playlists(cues) if total > limit for f in files}


# ── the ZIP package ──
@dataclass
class PackResult:
    files: int = 0                                     # media files in the package
    size: int = 0                                      # their bytes
    missing: list[str] = field(default_factory=list)   # "cue name: path" not found
    excluded: list[str] = field(default_factory=list)  # files left out (big playlists)


class _Names:
    """One name per source file inside the media folder; same name, other file -> name_2."""

    def __init__(self) -> None:
        self.by_key: dict[str, str] = {}
        self.used: set[str] = set()

    def name_for(self, source: str) -> str:
        key = path_key(source)
        if key in self.by_key:
            return self.by_key[key]
        name = Path(source).name or "media"
        stem, suffix = os.path.splitext(name)
        index = 2
        while name.casefold() in self.used:
            name = f"{stem}_{index}{suffix}"
            index += 1
        self.used.add(name.casefold())
        self.by_key[key] = name
        return name


def write_zip(target: str | Path, show_name: str, cues: list[Cue], settings: dict[str, Any] | None = None,
              current_index: int = -1, exclude: Iterable[str] = ()) -> PackResult:
    """Write the package; *exclude*: path keys of files to leave out (their cues keep the full path)."""
    from models.project_manager import APP_NAME, SCHEMA_VERSION

    stem = re.sub(r'[\\/:*?"<>|]', " ", show_name).strip() or "show"
    media = f"{stem}{MEDIA_SUFFIX}"
    skip = set(exclude)
    names = _Names()
    result = PackResult()
    to_add: dict[str, tuple[str, str]] = {}             # path key -> (source, name in the package)

    def packed(source: str, label: str) -> str | None:
        """The relative path of *source* inside the package, or None (missing / left out)."""
        if not source:
            return None
        if path_key(source) in skip:
            if source not in result.excluded:
                result.excluded.append(source)
            return None
        if not os.path.isfile(source):
            result.missing.append(f"{label}: {source}")
            return None
        name = names.name_for(source)
        to_add.setdefault(path_key(source), (source, name))  # one file written two ways: once
        return f"{media}/{name}"

    cue_dicts = []
    for cue in cues:
        data = cue.to_dict()
        if cue.media_type.has_file and not cue.text_spec:
            rel = packed(cue.file_path, cue.name)
            if rel:
                data["file_path"] = rel
        if cue.text_spec and cue.file_path and os.path.isfile(cue.file_path):
            data["file_path"] = packed(cue.file_path, cue.name)   # a caption image: made again if lost
        if cue.original_file_path and os.path.isfile(cue.original_file_path):
            rel = packed(cue.original_file_path, cue.name)
            if rel:
                data["original_file_path"] = rel
        cue_dicts.append(data)
    eff = copy.deepcopy(settings) if isinstance(settings, dict) else {}
    for key, label in (("layer0_image", "Layer 0"), ("layer0_video", "Layer 0")):
        value = eff.get(key)
        if isinstance(value, str) and value and os.path.isfile(value):
            rel = packed(value, label)
            if rel:
                eff[key] = rel
    for surface in eff.get("surfaces", []) if isinstance(eff.get("surfaces"), list) else []:
        mask = surface.get("mask_image_path") if isinstance(surface, dict) else None
        if isinstance(mask, str) and mask and os.path.isfile(mask):
            rel = packed(mask, str(surface.get("name", "surface")))
            if rel:
                surface["mask_image_path"] = rel
    project = {
        "app": APP_NAME, "schema_version": SCHEMA_VERSION, "saved_at": datetime.now().isoformat(),
        "project_name": stem, "current_cue_index": current_index, "cues_count": len(cues),
        "settings": eff, "surfaces": eff.get("surfaces", []), "cues": cue_dicts,
    }
    tmp = Path(str(target) + ".part")
    try:
        # strict_timestamps off: a file dated before 1980 (a camera without a clock) gets 1980, no error.
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, allowZip64=True, strict_timestamps=False) as zf:
            zf.writestr(f"{stem}/{stem}.blindcue", json.dumps(project, indent=2, ensure_ascii=False))
            for source, name in to_add.values():
                # Media are compressed already: stored as they are (faster, no bigger).
                zf.write(source, f"{stem}/{media}/{name}", compress_type=zipfile.ZIP_STORED)
                result.files += 1
                result.size += _size(source)
        os.replace(tmp, target)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise
    return result


# ── unused files of the media folder ──
def references_in_show_file(show: str | Path, base: str | Path | None = None) -> set[str]:
    """Path keys of every media file a saved show file (or a backup copy) names; set() when unreadable.

    *base*: the folder relative paths start from - for a backup copy (in ``<name>_backups``) the
    show's own folder, as when it is restored.
    """
    path = Path(show)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if not isinstance(data, dict):
        return set()
    base = Path(base) if base is not None else path.parent
    out: set[str] = set()

    def add(raw: object, where: Path) -> None:
        if isinstance(raw, str) and raw.strip():
            p = Path(raw)
            out.add(path_key(p if p.is_absolute() else where / p))

    settings = data.get("settings", {})
    for item in data.get("cues", []) if isinstance(data.get("cues"), list) else []:
        if isinstance(item, dict):
            add(item.get("file_path"), base)
            add(item.get("original_file_path"), base)
    if isinstance(settings, dict):
        add(settings.get("layer0_image"), base)
        add(settings.get("layer0_video"), base)
        for surface in settings.get("surfaces", []) if isinstance(settings.get("surfaces"), list) else []:
            if isinstance(surface, dict):
                add(surface.get("mask_image_path"), base)
    return out


def references(cues: Iterable[Cue], settings: dict[str, Any] | None = None) -> set[str]:
    """Path keys of the media the open show uses."""
    out = set()
    for cue in cues:
        for raw in (cue.file_path, cue.original_file_path):
            if raw:
                out.add(path_key(raw))
    eff = settings or {}
    for key in ("layer0_image", "layer0_video"):
        if isinstance(eff.get(key), str) and eff[key]:
            out.add(path_key(eff[key]))
    for surface in eff.get("surfaces", []) if isinstance(eff.get("surfaces"), list) else []:
        if isinstance(surface, dict) and surface.get("mask_image_path"):
            out.add(path_key(surface["mask_image_path"]))
    return out


def unused_media(media_dir: str | Path, used: set[str]) -> list[Path]:
    """Files under *media_dir* (not in ``_unused``, not hidden) whose key is not in *used*."""
    base = Path(media_dir)
    if not base.is_dir():
        return []
    out = []
    for path in sorted(base.rglob("*")):
        rel = path.relative_to(base)
        if rel.parts[0] == UNUSED_FOLDER or any(part.startswith(".") for part in rel.parts):
            continue
        if path.is_file() and path_key(path) not in used:
            out.append(path)
    return out


def set_aside(media_dir: str | Path, files: Iterable[Path]) -> list[Path]:
    """Move *files* into ``<media_dir>/_unused`` (a free name each); the new paths. Never deletes."""
    target_dir = Path(media_dir) / UNUSED_FOLDER
    target_dir.mkdir(exist_ok=True)
    moved = []
    for source in files:
        target = target_dir / source.name
        index = 2
        while target.exists():
            target = target_dir / f"{source.stem}_{index}{source.suffix}"
            index += 1
        shutil.move(str(source), str(target))
        moved.append(target)
    return moved


# ── renaming a media file ──
def rename_target(path: str | Path, new_name: str) -> Path:
    """The new path in the same folder: *new_name* made safe, the old extension kept."""
    from engine.show_templates import safe_file_name

    old = Path(path)
    stem = new_name.strip()
    if stem.lower().endswith(old.suffix.lower()) and old.suffix:
        stem = stem[: -len(old.suffix)]
    return old.with_name(safe_file_name(stem, old.stem) + old.suffix)


def rename_in_cues(cues: Iterable[Cue], old: str, new: str) -> int:
    """Point every cue that used *old* to *new*; how many references changed."""
    key = path_key(old)
    count = 0
    for cue in cues:
        if cue.file_path and path_key(cue.file_path) == key:
            cue.file_path = str(new)
            count += 1
        if cue.original_file_path and path_key(cue.original_file_path) == key:
            cue.original_file_path = str(new)
            count += 1
    return count


def rename_in_dicts(cue_dicts: Iterable[dict], old: str, new: str) -> int:
    """The same for ``Cue.to_dict`` rows (the undo steps)."""
    key = path_key(old)
    count = 0
    for item in cue_dicts:
        for field_name in ("file_path", "original_file_path"):
            value = item.get(field_name)
            if isinstance(value, str) and value and path_key(value) == key:
                item[field_name] = str(new)
                count += 1
    return count
