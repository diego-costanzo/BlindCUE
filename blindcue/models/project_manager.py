"""Show file persistence and crash recovery for BlindCue.

Follows open-source best practices:
- Standard JSON format with schema versioning.
- Atomic file operations (write to .tmp then os.replace) to prevent file corruption.
- Automatic autosave every N seconds or on modification.
- Crash recovery detection on startup.
- Safe path handling and validation of referenced media.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from models.cue import Cue, CueStatus, MediaType

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"
APP_NAME = "BlindCue"
DEFAULT_AUTOSAVE_DIR = Path.home() / ".config" / "blindcue"
AUTOSAVE_FILENAME = "autosave.json"
# Folder created next to the project file when the operator wants a portable
# archive: "<project name>_media/".
MEDIA_DIR_SUFFIX = "_media"


class ProjectManager:
    """Manages saving, loading, autosaving, and crash recovery for show files."""

    def __init__(self, autosave_dir: Path | None = None) -> None:
        """Create the project manager and make sure the autosave folder exists."""
        self.autosave_dir = autosave_dir or DEFAULT_AUTOSAVE_DIR
        self.autosave_file = self.autosave_dir / AUTOSAVE_FILENAME
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Ensure config and autosave directories exist."""
        try:
            self.autosave_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("[PROJECT] Could not create autosave dir %s: %s", self.autosave_dir, exc)

    # ── Atomic JSON File Write ────────────────────────────────────────

    @staticmethod
    def _atomic_write_json(file_path: Path, data: dict[str, Any]) -> None:
        """Write JSON data atomically to avoid corrupting files on crash or power loss."""
        target_dir = file_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        # Create temporary file in the same directory to ensure same filesystem for os.replace
        temp_fd, temp_path = tempfile.mkstemp(
            prefix=f".{file_path.stem}_",
            suffix=".tmp",
            dir=str(target_dir),
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())  # Ensure data is flushed to physical storage
            # Atomic rename replaces existing file in a single operation
            os.replace(temp_path, str(file_path))
            logger.debug("[PROJECT] Atomically wrote: %s", file_path)
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

    # ── Project Save & Load ───────────────────────────────────────────

    @staticmethod
    def _absolute_media_key(file_path: str) -> str:
        """Normalise a media path so the same file maps to one archive copy."""
        try:
            return str(Path(file_path).expanduser().resolve())
        except OSError:
            return os.path.abspath(os.path.expanduser(file_path))

    def import_media(
        self, cues: list[Cue], project_path: str | Path
    ) -> tuple[dict[str, str], list[str]]:
        """Copy every referenced media file next to the project file.

        The archive lives in ``<project name>_media/`` beside the project and
        the returned mapping lets the saved show reference the copies with
        *relative* paths, so the whole folder can be moved to another machine.
        Originals are only read: they are never moved or deleted.  Re-saving
        the same show reuses the copies already present.

        Returns ``(mapping, problems)`` where *mapping* maps the absolute
        source path to the relative path to store in the project, and
        *problems* lists files that could not be copied.
        """
        project = Path(project_path)
        media_dir = project.parent / f"{project.stem}{MEDIA_DIR_SUFFIX}"
        mapping: dict[str, str] = {}
        problems: list[str] = []
        claimed: set[str] = set()

        for cue in cues:
            if cue.media_type == MediaType.GROUP or not cue.file_path:
                continue
            source = Path(cue.file_path).expanduser()
            key = self._absolute_media_key(str(source))
            if key in mapping:
                continue
            if not source.is_file():
                problems.append(f"{cue.name}: file non trovato ({source})")
                continue
            try:
                media_dir.mkdir(parents=True, exist_ok=True)
                target = self._media_target(media_dir, source, claimed)
                claimed.add(target.name)
                if not target.is_file() or target.stat().st_size != source.stat().st_size:
                    temp_target = target.with_name(f".{target.name}.tmp")
                    shutil.copy2(source, temp_target)
                    os.replace(temp_target, target)
                if target.stat().st_size != source.stat().st_size:
                    raise OSError("copia incompleta")
                mapping[key] = f"{media_dir.name}/{target.name}"
            except Exception as exc:
                logger.error("[PROJECT] Cannot archive media %s: %s", source, exc)
                problems.append(f"{cue.name}: copia non riuscita ({exc})")

        logger.info(
            "[PROJECT] Archived %d media file(s) into %s", len(mapping), media_dir
        )
        return mapping, problems

    @staticmethod
    def _media_target(media_dir: Path, source: Path, claimed: set[str]) -> Path:
        """Pick a free destination name, keeping same-named files side by side."""
        name = source.name or "media"
        target = media_dir / name
        if name in claimed or (
            target.is_file() and target.stat().st_size != source.stat().st_size
        ):
            stem, suffix = os.path.splitext(name)
            index = 2
            while True:
                candidate = f"{stem}_{index}{suffix}"
                candidate_path = media_dir / candidate
                if candidate not in claimed and not candidate_path.is_file():
                    return candidate_path
                if candidate not in claimed and candidate_path.is_file() and \
                        candidate_path.stat().st_size == source.stat().st_size:
                    return candidate_path
                index += 1
        return target

    def save_project(
        self,
        file_path: str | Path,
        cues: list[Cue],
        current_index: int = -1,
        settings: dict[str, Any] | None = None,
        surfaces: list[Any] | None = None,
        media_map: dict[str, str] | None = None,
    ) -> bool:
        """Save show cues, project state, and virtual surfaces to a .blindcue JSON file.

        ``media_map`` (absolute source → relative path), when given, makes the
        saved cues reference archived copies instead of the original paths.

        Returns True on success, False on error.
        """
        path = Path(file_path)
        try:
            eff_settings = dict(settings or {})
            if surfaces is not None:
                eff_settings["surfaces"] = [
                    s.to_dict() if hasattr(s, "to_dict") else s for s in surfaces
                ]

            cue_dicts = [cue.to_dict() for cue in cues]
            if media_map:
                for cue, item in zip(cues, cue_dicts):
                    if cue.media_type == MediaType.GROUP or not cue.file_path:
                        continue
                    relative = media_map.get(self._absolute_media_key(cue.file_path))
                    if relative:
                        item["file_path"] = relative

            project_data: dict[str, Any] = {
                "app": APP_NAME,
                "schema_version": SCHEMA_VERSION,
                "saved_at": datetime.now().isoformat(),
                "project_name": path.stem,
                "current_cue_index": current_index,
                "cues_count": len(cues),
                "settings": eff_settings,
                "surfaces": eff_settings.get("surfaces", []),
                "cues": cue_dicts,
            }

            self._atomic_write_json(path, project_data)
            logger.info("[PROJECT] Successfully saved show to: %s (%d cues)", path, len(cues))
            return True
        except Exception as exc:
            logger.error("[PROJECT] Failed to save show to %s: %s", path, exc, exc_info=True)
            return False

    def save_project_bundled(
        self,
        file_path: str | Path,
        cues: list[Cue],
        current_index: int = -1,
        settings: dict[str, Any] | None = None,
        surfaces: list[Any] | None = None,
    ) -> tuple[bool, list[str], int]:
        """Save the show as a self-contained folder (media copied next to it).

        Returns ``(saved, problems, copied)``.
        """
        media_map, problems = self.import_media(cues, file_path)
        saved = self.save_project(
            file_path,
            cues,
            current_index=current_index,
            settings=settings,
            surfaces=surfaces,
            media_map=media_map,
        )
        return saved, problems, len(media_map)

    def load_project(
        self, file_path: str | Path
    ) -> tuple[list[Cue], int, dict[str, Any]]:
        """Load show cues and project state from a .blindcue JSON file.

        Returns (cues, current_index, settings).
        Raises ValueError or IOError if the file is invalid.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Project file not found: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                raise ValueError("Corrupted show file: root is not a dictionary.")

            # Validate app compatibility
            app_id = data.get("app")
            if app_id != APP_NAME:
                logger.warning("[PROJECT] File app tag '%s' differs from '%s'", app_id, APP_NAME)

            current_index = data.get("current_cue_index", -1)
            try:
                current_index = int(current_index)
            except (TypeError, ValueError):
                logger.warning("[PROJECT] Invalid current_cue_index %r, defaulting to -1", current_index)
                current_index = -1

            settings = data.get("settings", {})
            if not isinstance(settings, dict):
                logger.warning("[PROJECT] Invalid settings block (%s), ignoring", type(settings).__name__)
                settings = {}
            if "surfaces" in data and "surfaces" not in settings:
                settings["surfaces"] = data["surfaces"]
            raw_cues = data.get("cues", [])
            if not isinstance(raw_cues, list):
                logger.warning("[PROJECT] Invalid cues block (%s), ignoring", type(raw_cues).__name__)
                raw_cues = []

            loaded_cues: list[Cue] = []
            proj_dir = path.parent.resolve()
            for item in raw_cues:
                try:
                    cue = Cue.from_dict(item, project_root=proj_dir)
                    # Check if file exists at recorded absolute path
                    file_p = Path(cue.file_path)
                    if not file_p.is_file():
                        # Attempt safe resolution by base filename in project folder
                        base_candidate = (proj_dir / file_p.name).resolve()
                        if not base_candidate.is_relative_to(proj_dir):
                            raise ValueError(
                                f"Path traversal detected: '{file_p.name}' resolves outside project root '{proj_dir}'"
                            )
                        if base_candidate.is_file():
                            cue.file_path = str(base_candidate)

                    # Reset LIVE or PREVIZ runtime status to OFFLINE or LOADED
                    cue.status = CueStatus.LOADED if Path(cue.file_path).is_file() else CueStatus.OFFLINE
                    loaded_cues.append(cue)
                except Exception as cue_exc:
                    # A single corrupted/traversal cue must never abort the whole show load
                    logger.warning("[PROJECT] Skipping invalid cue item: %s (%s)", item, cue_exc)

            logger.info("[PROJECT] Loaded %d cues from %s", len(loaded_cues), path)
            return loaded_cues, current_index, settings

        except json.JSONDecodeError as exc:
            logger.error("[PROJECT] JSON decode error in %s: %s", path, exc)
            raise ValueError(f"Invalid JSON format in {path}: {exc}") from exc
        except Exception as exc:
            logger.error("[PROJECT] Failed to load %s: %s", path, exc, exc_info=True)
            raise

    # ── Autosave & Crash Recovery ─────────────────────────────────────

    def build_autosave_payload(
        self,
        cues: list[Cue],
        current_index: int = -1,
        active_project_path: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the crash-recovery payload in memory.

        This must be called from the GUI thread: it reads the live ``cues``
        objects (which are mutated by the GUI thread) and produces a plain,
        deeply-serialized ``dict`` snapshot with no disk I/O.  The returned
        payload can then be handed to a worker thread for the actual write.
        """
        return {
            "app": APP_NAME,
            "schema_version": SCHEMA_VERSION,
            "saved_at": datetime.now().isoformat(),
            "clean_exit": False,  # Marked as false during runtime; set to true on clean shutdown
            "active_project_path": active_project_path,
            "current_cue_index": current_index,
            "cues_count": len(cues),
            "settings": settings or {},
            "cues": [cue.to_dict() for cue in cues],
        }

    def write_autosave_payload(self, payload: dict[str, Any]) -> bool:
        """Atomically persist a pre-built recovery payload.

        Safe to call from any thread: it only touches the filesystem (atomic
        write via ``_atomic_write_json``) and never reads GUI state.
        """
        try:
            self._ensure_dirs()
            self._atomic_write_json(self.autosave_file, payload)
            logger.debug("[AUTOSAVE] Saved %d cues to %s", payload.get("cues_count", 0), self.autosave_file)
            return True
        except Exception as exc:
            logger.warning("[AUTOSAVE] Autosave failed: %s", exc)
            return False

    def autosave(
        self,
        cues: list[Cue],
        current_index: int = -1,
        active_project_path: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> bool:
        """Perform a synchronous automatic save with recovery metadata."""
        try:
            payload = self.build_autosave_payload(
                cues,
                current_index=current_index,
                active_project_path=active_project_path,
                settings=settings,
            )
        except Exception as exc:
            logger.warning("[AUTOSAVE] Autosave payload build failed: %s", exc, exc_info=True)
            return False
        return self.write_autosave_payload(payload)

    def mark_clean_exit(self) -> None:
        """Mark the autosave state as cleanly closed so no crash prompt is shown next time."""
        try:
            if self.autosave_file.is_file():
                with open(self.autosave_file, encoding="utf-8") as f:
                    data = json.load(f)
                data["clean_exit"] = True
                data["exit_at"] = datetime.now().isoformat()
                self._atomic_write_json(self.autosave_file, data)
                logger.info("[PROJECT] Marked session clean exit")
        except Exception as exc:
            logger.debug("[PROJECT] Could not mark clean exit: %s", exc)

    def check_crash_recovery(self) -> dict[str, Any] | None:
        """Check if an unclosed session exists that can be recovered.

        Returns the recovery dictionary if an abnormal termination was detected,
        or None if previous session was clean or nonexistent.
        """
        if not self.autosave_file.is_file():
            return None

        try:
            with open(self.autosave_file, encoding="utf-8") as f:
                data = json.load(f)

            # If clean_exit is explicitly True, no crash occurred
            if data.get("clean_exit") is True:
                return None

            cues_list = data.get("cues", [])
            if not cues_list:
                return None

            logger.info("[PROJECT] Unclean session found! (saved_at: %s, cues: %d)",
                        data.get("saved_at"), len(cues_list))
            return data
        except Exception as exc:
            logger.warning("[PROJECT] Failed to read autosave for recovery check: %s", exc)
            return None

    def clear_autosave(self) -> None:
        """Remove the autosave file."""
        try:
            if self.autosave_file.is_file():
                self.autosave_file.unlink()
                logger.info("[PROJECT] Cleared autosave file")
        except Exception as exc:
            logger.warning("[PROJECT] Could not delete autosave file: %s", exc)

