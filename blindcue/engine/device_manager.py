"""Device & Hardware Routing Manager for BlindCue.

Coordinates:
- Audio Master device (PA / Stage Sala output)
- Audio Monitor device (Headphones / Director PFL pre-viz)
- Live Video Output Screen (External projector / Secondary display)
- Hardware Profiler & Performance Profile (Eco / Standard / Performance)

100% Native Wayland & Linux, zero external dependencies.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from PySide6.QtCore import QByteArray, QObject, Signal
from PySide6.QtGui import QGuiApplication, QScreen
from PySide6.QtMultimedia import QAudioDevice, QMediaDevices

from ui.hardware_info import (
    PROFILE_AUTO,
    PROFILE_ECO,
    PROFILE_PERFORMANCE,
    PROFILE_STANDARD,
    ShowRuntimeGuard,
    evaluate_hardware_profile,
)

logger = logging.getLogger(__name__)


class DeviceManager(QObject):
    """Central manager for audio devices, output displays, and performance profiles."""

    audio_devices_changed = Signal()
    screens_changed = Signal()
    master_device_changed = Signal(str)
    monitor_device_changed = Signal(str)
    target_screen_changed = Signal(str)
    profile_changed = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

        self._master_device: Optional[QAudioDevice] = None
        self._monitor_device: Optional[QAudioDevice] = None
        self._target_screen: Optional[QScreen] = None
        self._profile_preference: str = PROFILE_AUTO

        # Registered consumers
        self._live_players: list[Any] = []
        self._test_player: Optional[Any] = None
        self._output_window: Optional[Any] = None
        self._media_devices: Optional[QMediaDevices] = None

        self._init_defaults()
        self._wire_hotplug_detectors()

    # ── Initialization & Discovery ────────────────────────────────────

    def _init_defaults(self) -> None:
        """Initialize default audio devices, screens, and hardware profile."""
        try:
            self._media_devices = QMediaDevices(self)
            self._master_device = QMediaDevices.defaultAudioOutput()
            self._monitor_device = QMediaDevices.defaultAudioOutput()
        except Exception as exc:
            logger.warning("[DEVICE-MGR] Could not query default audio output: %s", exc)

        # Detect screens
        app = QGuiApplication.instance()
        if app is not None:
            screens = app.screens()
            primary = app.primaryScreen()
            if len(screens) > 1:
                # Default to first non-primary screen
                self._target_screen = next((s for s in screens if s != primary), screens[0])
            elif screens:
                self._target_screen = screens[0]

        # Apply initial hardware profile thread pool settings
        prof = self.get_effective_profile()
        ShowRuntimeGuard.configure_thread_pool(prof)
        logger.info(
            "[DEVICE-MGR] Initialized: MasterAudio='%s', MonitorAudio='%s', TargetScreen='%s', Profile='%s'",
            self._device_label(self._master_device),
            self._device_label(self._monitor_device),
            self._target_screen.name() if self._target_screen else "None",
            prof,
        )

    def _wire_hotplug_detectors(self) -> None:
        """Listen to USB soundcard and monitor plug/unplug events."""
        if self._media_devices is not None:
            try:
                self._media_devices.audioOutputsChanged.connect(self._on_audio_outputs_changed)
            except Exception as exc:
                logger.debug("[DEVICE-MGR] audioOutputsChanged signal connect failed: %s", exc)

        app = QGuiApplication.instance()
        if app is not None:
            try:
                app.screenAdded.connect(self._on_screens_changed)
                app.screenRemoved.connect(self._on_screens_changed)
            except Exception as exc:
                logger.debug("[DEVICE-MGR] screenAdded/Removed signals not available: %s", exc)

    # ── Consumers Registration ────────────────────────────────────────

    def register_live_players(self, players: Sequence[Any]) -> None:
        """Register live players (Layer 1..3) to receive master audio device updates."""
        self._live_players = list(players)
        if self._master_device is not None:
            for p in self._live_players:
                if hasattr(p, "set_audio_device"):
                    p.set_audio_device(self._master_device)

    def register_test_player(self, player: Optional[Any]) -> None:
        """Register test player to receive monitor/PFL audio device updates."""
        self._test_player = player
        if self._test_player is not None and self._monitor_device is not None:
            if hasattr(self._test_player, "set_audio_device"):
                self._test_player.set_audio_device(self._monitor_device)

    def register_output_window(self, output_window: Optional[Any]) -> None:
        """Register output window to receive screen routing updates."""
        self._output_window = output_window
        if self._output_window is not None and self._target_screen is not None:
            if hasattr(self._output_window, "set_target_screen"):
                self._output_window.set_target_screen(self._target_screen)

    # ── Audio Devices Management ──────────────────────────────────────

    @staticmethod
    def get_available_audio_devices() -> list[QAudioDevice]:
        """Return list of all recognized audio output devices."""
        try:
            return list(QMediaDevices.audioOutputs())
        except Exception as exc:
            logger.warning("[DEVICE-MGR] Error querying audioOutputs: %s", exc)
            return []

    def get_master_audio_device(self) -> Optional[QAudioDevice]:
        return self._master_device

    def get_monitor_audio_device(self) -> Optional[QAudioDevice]:
        return self._monitor_device

    def set_master_audio_device(self, device: Optional[QAudioDevice]) -> None:
        """Set output device for Sala / PA Master audio."""
        if device is None or device.isNull():
            device = QMediaDevices.defaultAudioOutput()
        self._master_device = device
        for p in self._live_players:
            if hasattr(p, "set_audio_device"):
                p.set_audio_device(device)
        desc = self._device_label(device)
        logger.info("[DEVICE-MGR] Master audio device updated to '%s'", desc)
        self.master_device_changed.emit(desc)

    def set_monitor_audio_device(self, device: Optional[QAudioDevice]) -> None:
        """Set output device for Director Headphones / PFL pre-viz audio."""
        if device is None or device.isNull():
            device = QMediaDevices.defaultAudioOutput()
        self._monitor_device = device
        if self._test_player is not None and hasattr(self._test_player, "set_audio_device"):
            self._test_player.set_audio_device(device)
        desc = self._device_label(device)
        logger.info("[DEVICE-MGR] Monitor (PFL) audio device updated to '%s'", desc)
        self.monitor_device_changed.emit(desc)

    def _on_audio_outputs_changed(self) -> None:
        """Handle hardware audio plug/unplug safely."""
        logger.info("[DEVICE-MGR] Audio outputs hardware change detected!")
        devs = self.get_available_audio_devices()
        dev_ids = {bytes(d.id()) for d in devs}

        # Check if master device was unplugged
        if self._master_device is not None and bytes(self._master_device.id()) not in dev_ids:
            logger.warning("[DEVICE-MGR] Master audio device disconnected! Falling back to default.")
            self.set_master_audio_device(QMediaDevices.defaultAudioOutput())

        # Check if monitor device was unplugged
        if self._monitor_device is not None and bytes(self._monitor_device.id()) not in dev_ids:
            logger.warning("[DEVICE-MGR] Monitor audio device disconnected! Falling back to default.")
            self.set_monitor_audio_device(QMediaDevices.defaultAudioOutput())

        self.audio_devices_changed.emit()

    # ── Screen Management ─────────────────────────────────────────────

    @staticmethod
    def get_available_screens() -> list[QScreen]:
        """Return list of currently connected screens."""
        app = QGuiApplication.instance()
        return list(app.screens()) if app is not None else []

    def get_target_screen(self) -> Optional[QScreen]:
        return self._target_screen

    def set_target_screen(self, screen: Optional[QScreen]) -> None:
        """Route the live output window to *screen*."""
        if screen is None:
            return
        self._target_screen = screen
        if self._output_window is not None and hasattr(self._output_window, "set_target_screen"):
            self._output_window.set_target_screen(screen)
        name = screen.name()
        logger.info("[DEVICE-MGR] Target screen updated to '%s'", name)
        self.target_screen_changed.emit(name)

    def _on_screens_changed(self, *args: Any) -> None:
        """Handle monitor plug/unplug events."""
        screens = self.get_available_screens()
        logger.info("[DEVICE-MGR] Display configuration changed (%d screens connected)", len(screens))
        if self._target_screen not in screens and screens:
            primary = QGuiApplication.primaryScreen()
            new_target = next((s for s in screens if s != primary), screens[0])
            self.set_target_screen(new_target)
        self.screens_changed.emit()

    # ── Hardware Profile Management ───────────────────────────────────

    def get_profile_preference(self) -> str:
        return self._profile_preference

    def get_effective_profile(self) -> str:
        info = evaluate_hardware_profile(self._profile_preference)
        return info["profile"]

    def get_profile_info(self) -> dict:
        return evaluate_hardware_profile(self._profile_preference)

    def set_hardware_profile(self, profile: str) -> None:
        """Change performance profile ('auto', 'eco', 'standard', 'performance')."""
        self._profile_preference = profile.strip().lower()
        effective = self.get_effective_profile()
        ShowRuntimeGuard.configure_thread_pool(effective)
        logger.info("[DEVICE-MGR] Profile changed to '%s' (effective: '%s')", self._profile_preference, effective)
        self.profile_changed.emit(effective)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _device_label(dev: Optional[QAudioDevice]) -> str:
        if dev is None or dev.isNull():
            return "Predefinito di Sistema"
        name = dev.description().strip()
        return name if name else "Audio Device"
