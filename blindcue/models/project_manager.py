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
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from models.cue import Cue, CueStatus

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"
APP_NAME = "BlindCue"
DEFAULT_AUTOSAVE_DIR = Path.home() / ".config" / "blindcue"
AUTOSAVE_FILENAME = "autosave.json"


class ProjectManager:
    """Manages saving, loading, autosaving, and crash recovery for show files."""

    def __init__(self, autosave_dir: Path | None = None) -> None:
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

    def save_project(
        self,
        file_path: str | Path,
        cues: list[Cue],
        current_index: int = -1,
        settings: dict[str, Any] | None = None,
        surfaces: list[Any] | None = None,
    ) -> bool:
        """Save show cues, project state, and virtual surfaces to a .blindcue JSON file.

        Returns True on success, False on error.
        """
        path = Path(file_path)
        try:
            eff_settings = dict(settings or {})
            if surfaces is not None:
                eff_settings["surfaces"] = [
                    s.to_dict() if hasattr(s, "to_dict") else s for s in surfaces
                ]

            project_data: dict[str, Any] = {
                "app": APP_NAME,
                "schema_version": SCHEMA_VERSION,
                "saved_at": datetime.now().isoformat(),
                "project_name": path.stem,
                "current_cue_index": current_index,
                "cues_count": len(cues),
                "settings": eff_settings,
                "surfaces": eff_settings.get("surfaces", []),
                "cues": [cue.to_dict() for cue in cues],
            }

            self._atomic_write_json(path, project_data)
            logger.info("[PROJECT] Successfully saved show to: %s (%d cues)", path, len(cues))
            return True
        except Exception as exc:
            logger.error("[PROJECT] Failed to save show to %s: %s", path, exc, exc_info=True)
            return False

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
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                raise ValueError("Corrupted show file: root is not a dictionary.")

            # Validate app compatibility
            app_id = data.get("app")
            if app_id != APP_NAME:
                logger.warning("[PROJECT] File app tag '%s' differs from '%s'", app_id, APP_NAME)

            current_index = data.get("current_cue_index", -1)
            settings = data.get("settings", {})
            if "surfaces" in data and "surfaces" not in settings:
                settings["surfaces"] = data["surfaces"]
            raw_cues = data.get("cues", [])

            loaded_cues: list[Cue] = []
            proj_dir = path.parent.resolve()
            for item in raw_cues:
                try:
                    cue = Cue.from_dict(item)
                    # Check if file exists at recorded absolute path
                    file_p = Path(cue.file_path)
                    if not file_p.is_file():
                        # Attempt safe resolution relative to project directory (Anti-Path-Traversal)
                        try:
                            rel_candidate = (path.parent / file_p).resolve()
                            if rel_candidate.is_file() and rel_candidate.is_relative_to(proj_dir):
                                cue.file_path = str(rel_candidate)
                            else:
                                # Also check by base filename in the project folder
                                base_candidate = (path.parent / file_p.name).resolve()
                                if base_candidate.is_file() and base_candidate.is_relative_to(proj_dir):
                                    cue.file_path = str(base_candidate)
                        except (ValueError, OSError) as path_err:
                            logger.debug("[PROJECT] Path resolution skipped for %s: %s", cue.file_path, path_err)

                    # Reset LIVE or PREVIZ runtime status to OFFLINE or LOADED
                    cue.status = CueStatus.LOADED if Path(cue.file_path).is_file() else CueStatus.OFFLINE
                    loaded_cues.append(cue)
                except Exception as cue_exc:
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

    def autosave(
        self,
        cues: list[Cue],
        current_index: int = -1,
        active_project_path: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> bool:
        """Perform an automatic background save with recovery metadata."""
        try:
            self._ensure_dirs()
            recovery_data: dict[str, Any] = {
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
            self._atomic_write_json(self.autosave_file, recovery_data)
            logger.debug("[AUTOSAVE] Saved %d cues to %s", len(cues), self.autosave_file)
            return True
        except Exception as exc:
            logger.warning("[AUTOSAVE] Autosave failed: %s", exc)
            return False

    def mark_clean_exit(self) -> None:
        """Mark the autosave state as cleanly closed so no crash prompt is shown next time."""
        try:
            if self.autosave_file.is_file():
                with open(self.autosave_file, "r", encoding="utf-8") as f:
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
            with open(self.autosave_file, "r", encoding="utf-8") as f:
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

