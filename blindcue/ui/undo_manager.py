"""Lightweight bounded Undo / Redo snapshot manager for cue show state."""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import QObject, QTimer, Signal

from models.cue import Cue


class UndoManager(QObject):
    """Stores bounded metadata snapshots (<2 MB RAM) with debounced slider/spin edits."""

    commit_requested = Signal()
    history_changed = Signal(bool, bool)  # can_undo, can_redo

    def __init__(self, parent: QObject | None = None,
                 max_steps: int = 40, debounce_ms: int = 450) -> None:
        """Keep up to ``max_steps`` snapshots with a ``debounce_ms`` settle delay."""
        super().__init__(parent)
        self._undo_stack: deque[dict] = deque(maxlen=max_steps)
        self._redo_stack: deque[dict] = deque(maxlen=max_steps)
        self._committed_state: dict | None = None
        self.restoring: bool = False

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(debounce_ms)
        self._debounce_timer.timeout.connect(self.commit_requested)

    @property
    def can_undo(self) -> bool:
        """True when at least one undo step is available."""
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        """True when at least one redo step is available."""
        return bool(self._redo_stack)

    def is_debounce_active(self) -> bool:
        """True while a continuous edit is still being coalesced."""
        return self._debounce_timer.isActive()

    def stop_debounce(self) -> None:
        """Cancel a pending debounced commit (called before explicit commits)."""
        if self._debounce_timer.isActive():
            self._debounce_timer.stop()

    def schedule_commit(self) -> None:
        """Debounce continuous slider/spinbox/drag edits into one undo step."""
        if not self.restoring:
            self._debounce_timer.start()

    @staticmethod
    def capture_state(cues: list[Cue], current_index: int) -> dict:
        """Capture lightweight metadata snapshot of cues and selection."""
        return {
            "cues": [c.to_dict() for c in cues],
            "current_index": current_index,
        }

    @staticmethod
    def comparable_cues(cue_dicts: list[dict]) -> list[dict]:
        """Strip volatile playback status when comparing cue snapshots."""
        out: list[dict] = []
        for d in cue_dicts:
            copy_d = dict(d)
            copy_d.pop("status", None)
            out.append(copy_d)
        return out

    def update_current_index(self, row: int) -> None:
        """Track the selected row without creating a new undo step."""
        if self._committed_state is not None and not self.restoring:
            self._committed_state["current_index"] = row

    def set_committed_state(self, cues: list[Cue], current_index: int) -> None:
        """Record the baseline snapshot that the next commit is compared against."""
        self._committed_state = self.capture_state(cues, current_index)

    def commit(self, cues: list[Cue], current_index: int) -> None:
        """Record an undo step if cue data changed since the previous checkpoint."""
        if self.restoring:
            return
        self.stop_debounce()

        curr = self.capture_state(cues, current_index)
        if self._committed_state is None:
            self._committed_state = curr
            return

        if self.comparable_cues(curr["cues"]) != self.comparable_cues(self._committed_state["cues"]):
            self._undo_stack.append(self._committed_state)
            self._redo_stack.clear()
            self._committed_state = curr
            self.history_changed.emit(self.can_undo, self.can_redo)
        else:
            self._committed_state["current_index"] = curr["current_index"]

    def reset(self, cues: list[Cue], current_index: int) -> None:
        """Clear Undo/Redo history cleanly when opening or creating a project."""
        self.stop_debounce()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._committed_state = self.capture_state(cues, current_index)
        self.history_changed.emit(False, False)

    def pop_undo(self, cues: list[Cue], current_index: int) -> dict | None:
        """Push current snapshot to Redo and return the previous snapshot if available."""
        if not self._undo_stack:
            return None
        curr = self.capture_state(cues, current_index)
        self._redo_stack.append(curr)
        return self._undo_stack.pop()

    def pop_redo(self, cues: list[Cue], current_index: int) -> dict | None:
        """Push current snapshot to Undo and return the next redo snapshot if available."""
        if not self._redo_stack:
            return None
        curr = self.capture_state(cues, current_index)
        self._undo_stack.append(curr)
        return self._redo_stack.pop()

