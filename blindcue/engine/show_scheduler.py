"""Show-time timing scheduler for Cue Pre-Delay, Post-Delay, Auto-Follow, and Global Pause.

Designed for theatrical predictability:
- A single lightweight 33ms QTimer drives all active Pre-Delay and Post-Delay windows
  without allocating per-cue threads or leaking timers across restarts/Panics.
- Supports instantaneous Global Pause All (freezing every Pre/Post countdown with exact
  monotonic delta preservation) and 0ms Panic cancellation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal

from models.cue import Cue


@dataclass
class ScheduledWindow:
    """Active timing wait window bound to a cue and target output layer."""

    phase: str          # "PRE" | "POST"
    cue: Cue
    layer: int
    total_sec: float
    elapsed_sec: float = 0.0
    generation: int = 0


class ShowScheduler(QObject):
    """Precision monotonic scheduler for Cue Pre-Delay and Post-Delay timers."""

    tick_updated = Signal(object)       # ScheduledWindow (on ~30fps tick during active wait)
    window_finished = Signal(object)    # ScheduledWindow (when elapsed >= total)

    def __init__(self, parent: QObject | None = None) -> None:
        """Create the scheduler and its 33 ms (~30 fps) control tick."""
        super().__init__(parent)
        self._windows: dict[tuple[str, int], ScheduledWindow] = {}
        self._paused: bool = False
        self._last_tick: float = time.monotonic()

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._on_tick)

    def is_paused(self) -> bool:
        """True while Global Pause is freezing every countdown."""
        return self._paused

    def has_pending(self) -> bool:
        """True when at least one Pre/Post wait window is counting down."""
        return bool(self._windows)

    def pending_for_layer(self, layer: int, phase: str | None = None) -> ScheduledWindow | None:
        """Return the active wait window for *layer*, optionally for one phase only."""
        if phase is not None:
            return self._windows.get((phase, layer))
        return self._windows.get(("PRE", layer)) or self._windows.get(("POST", layer))

    def schedule(self, phase: str, cue: Cue, layer: int, duration_sec: float, generation: int = 0) -> ScheduledWindow:
        """Start (or replace) a monotonic wait window for *(phase, layer)*."""
        win = ScheduledWindow(
            phase=phase,
            cue=cue,
            layer=layer,
            total_sec=max(0.01, float(duration_sec)),
            elapsed_sec=0.0,
            generation=generation,
        )
        self._windows[(phase, layer)] = win
        if not self._timer.isActive() and not self._paused:
            self._last_tick = time.monotonic()
            self._timer.start()
        self.tick_updated.emit(win)
        return win

    def cancel_layer(self, layer: int, phase: str | None = None) -> None:
        """Cancel pending wait windows for *layer* (both phases unless specified)."""
        if phase is not None:
            self._windows.pop((phase, layer), None)
        else:
            self._windows.pop(("PRE", layer), None)
            self._windows.pop(("POST", layer), None)
        if not self._windows:
            self._timer.stop()

    def cancel_all(self) -> None:
        """Cancel all Pre/Post timing windows immediately (used by Blackout/Panic)."""
        self._windows.clear()
        self._timer.stop()

    def set_paused(self, paused: bool) -> None:
        """Freeze or resume all active delay timers cleanly without drift."""
        if self._paused == paused:
            return
        self._paused = paused
        if paused:
            self._advance_by_delta()
            self._timer.stop()
        else:
            self._last_tick = time.monotonic()
            if self._windows and not self._timer.isActive():
                self._timer.start()

    def step_for_test(self, dt_sec: float) -> None:
        """Deterministic helper for unit tests to advance timers without real wall sleeps."""
        if self._paused or dt_sec <= 0:
            return
        self._advance_windows(dt_sec)

    def _advance_by_delta(self) -> None:
        now = time.monotonic()
        dt = max(0.0, now - self._last_tick)
        self._last_tick = now
        if dt > 0:
            self._advance_windows(dt)

    def _on_tick(self) -> None:
        if self._paused or not self._windows:
            self._timer.stop()
            return
        self._advance_by_delta()

    def _advance_windows(self, dt: float) -> None:
        completed: list[tuple[tuple[str, int], ScheduledWindow]] = []
        for key, win in list(self._windows.items()):
            win.elapsed_sec = min(win.total_sec, win.elapsed_sec + dt)
            if win.elapsed_sec >= win.total_sec - 1e-4:
                completed.append((key, win))
            else:
                self.tick_updated.emit(win)

        for key, win in completed:
            # Verify the slot was not replaced before completion
            if self._windows.get(key) is win:
                self._windows.pop(key, None)
                self.window_finished.emit(win)

        if not self._windows:
            self._timer.stop()

