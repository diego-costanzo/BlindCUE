"""Cross-platform sleep and screensaver inhibition for live shows.

Keeps the stage machine awake while BlindCue is open using only open-source OS
mechanisms and Python's standard library (zero external dependencies):

- Linux: ``systemd-inhibit --what=sleep:idle --mode=block cat`` connected to a
  private pipe. If BlindCue crashes or is killed with SIGKILL, the OS closes
  the pipe automatically so ``cat`` exits and the inhibit lock never leaks.
- macOS: ``caffeinate -di -w <pid>`` bound to the current process PID.
- Windows: Win32 ``SetThreadExecutionState`` via ``ctypes``.

Every operation is best-effort and never prevents BlindCue from starting.
"""

from __future__ import annotations

import atexit
import logging
import os
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)


class SleepInhibitor:
    """Acquire and release an OS-level sleep/screensaver inhibition lock."""

    def __init__(self, reason: str = "Live show playback in progress") -> None:
        self._reason = reason
        self._proc: subprocess.Popen | None = None
        self._win_active: bool = False
        self._active: bool = False

    @property
    def is_active(self) -> bool:
        """True when an OS sleep/idle inhibitor is currently held."""
        return self._active

    def acquire(self) -> bool:
        """Prevent automatic suspend and screen blanking until :meth:`release`."""
        if self._active:
            return True

        if sys.platform.startswith("linux"):
            inhibit = shutil.which("systemd-inhibit")
            cat_bin = shutil.which("cat")
            if not inhibit or not cat_bin:
                logger.info("[POWER] systemd-inhibit not available; sleep inhibition skipped")
                return False
            try:
                # Hold stdin open so `cat` stays alive for the duration of the
                # session and exits immediately if this process dies.
                self._proc = subprocess.Popen(
                    [
                        inhibit,
                        "--what=sleep:idle",
                        "--who=BlindCue",
                        f"--why={self._reason}",
                        "--mode=block",
                        cat_bin,
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._active = True
                atexit.register(self.release)
                logger.info("[POWER] Sleep/idle inhibition active via systemd-inhibit (pid=%d)", self._proc.pid)
                return True
            except Exception as exc:
                logger.warning("[POWER] Could not start systemd-inhibit: %s", exc)
                self._proc = None
                return False

        if sys.platform == "darwin":
            caffeinate = shutil.which("caffeinate")
            if not caffeinate:
                return False
            try:
                self._proc = subprocess.Popen(
                    [caffeinate, "-di", "-w", str(os.getpid())],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._active = True
                atexit.register(self.release)
                logger.info("[POWER] Sleep/idle inhibition active via caffeinate (pid=%d)", self._proc.pid)
                return True
            except Exception as exc:
                logger.warning("[POWER] Could not start caffeinate: %s", exc)
                self._proc = None
                return False

        if sys.platform.startswith("win"):
            try:
                import ctypes

                ES_CONTINUOUS = 0x80000000
                ES_SYSTEM_REQUIRED = 0x00000001
                ES_DISPLAY_REQUIRED = 0x00000002
                res = ctypes.windll.kernel32.SetThreadExecutionState(
                    ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
                )
                if res:
                    self._win_active = True
                    self._active = True
                    atexit.register(self.release)
                    logger.info("[POWER] Sleep/display inhibition active via SetThreadExecutionState")
                    return True
            except Exception as exc:
                logger.warning("[POWER] Could not set Windows execution state: %s", exc)
            return False

        return False

    def release(self) -> None:
        """Release the OS sleep/idle lock cleanly (idempotent)."""
        if not self._active and self._proc is None and not self._win_active:
            return

        proc = self._proc
        self._proc = None
        if proc is not None:
            try:
                if proc.stdin is not None:
                    proc.stdin.close()
            except OSError:
                pass
            try:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=1.5)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=1.0)
                except Exception:
                    pass

        if self._win_active:
            self._win_active = False
            try:
                import ctypes

                ES_CONTINUOUS = 0x80000000
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            except Exception:
                pass

        self._active = False
        logger.debug("[POWER] Sleep/idle inhibition released")
