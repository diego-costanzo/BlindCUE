"""Device & Hardware Routing Manager for BlindCue.

Coordinates:
- Audio Master device (PA / Stage Sala output)
- Audio Monitor device (Headphones / Director PFL pre-viz)
- Live Video Output Screen (External projector / Secondary display)
- Hardware Profiler & Performance Profile (Eco / Standard / Performance)

Routing contract maintained by this module
------------------------------------------
* Output **A** is the first external projector, output **B** the second.
* Runtime layers **1-3** belong to output A, **4-6** to output B
  (see ``models.cue.runtime_layer``).
* Three output modes: ``single`` (one screen), ``span`` (all external screens
  merged into one canvas), ``dual`` (two independent projectors).
* With ``dual`` inactive, a cue assigned to B is projected on A
  (``models.cue.resolve_output_target``) — never silently lost.
* The director screen is used for projection only when no external display
  exists, so a projector is never blacked out by a UI window.

100% Native Wayland & Linux, zero external dependencies.
"""

from __future__ import annotations

import logging
from typing import Any
from collections.abc import Sequence

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtGui import QGuiApplication, QScreen
from PySide6.QtMultimedia import QAudioDevice, QMediaDevices

from models.cue import normalize_output_target
from models.output_config import OutputMode, normalize_output_mode
from ui.hardware_info import (
    PROFILE_AUTO,
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
    output_mode_changed = Signal(str)
    # Operator-facing message about the speakers chosen on this computer
    # (missing, or back again). Empty string = nothing to report.
    audio_notice = Signal(str)

    # Speakers chosen in the device dialog are remembered per computer in
    # QSettings (``audio/<role>_id`` + ``audio/<role>_name``), never in the
    # show file: a show opened on another computer uses that computer's own
    # choice, or the Windows default when nothing was chosen there.
    AUDIO_ROLES = ("master", "monitor")

    def __init__(self, parent: QObject | None = None) -> None:
        """Discover audio devices and resolve the projector assignment at startup."""
        super().__init__(parent)

        self._master_device: QAudioDevice | None = None
        self._monitor_device: QAudioDevice | None = None
        self._target_screen: QScreen | None = None
        # Physical projector assigned to each output. The director screen is
        # never used for projection while at least one external display exists.
        self._output_a_screen: QScreen | None = None
        self._output_b_screen: QScreen | None = None
        self._profile_preference: str = PROFILE_AUTO
        self._output_mode: str = OutputMode.SINGLE.value

        # Registered consumers
        self._live_players: list[Any] = []
        self._test_player: Any | None = None
        self._output_window: Any | None = None
        self._secondary_output_window: Any | None = None
        self._media_devices: QMediaDevices | None = None
        # Roles whose remembered speakers are not connected right now
        # (role -> remembered name); the Windows default plays meanwhile.
        self._audio_missing: dict[str, str] = {}

        self._init_defaults()
        self._wire_hotplug_detectors()

    # ── Initialization & Discovery ────────────────────────────────────

    def _init_defaults(self) -> None:
        """Initialize default audio devices, screens, and hardware profile."""
        try:
            self._media_devices = QMediaDevices(self)
            self._master_device = self._resolve_audio("master")
            self._monitor_device = self._resolve_audio("monitor")
        except Exception as exc:
            logger.warning("[DEVICE-MGR] Could not query default audio output: %s", exc)

        # Detect screens: projectors are always preferred over the director
        # monitor. Output A gets the first external display, output B the
        # second one when present.
        self._resolve_output_screens()

        # Apply initial hardware profile thread pool settings
        prof = self.get_effective_profile()
        ShowRuntimeGuard.configure_thread_pool(prof)

        # Restore the last output routing mode. The actual window is configured
        # only once the OutputWindow is registered, so the span is applied on a
        # live widget and not on a half-built one.
        saved_mode = QSettings("BlindCue", "BlindCue").value("output/mode", OutputMode.SINGLE.value)
        self._output_mode = normalize_output_mode(saved_mode)

        logger.info(
            "[DEVICE-MGR] Initialized: MasterAudio='%s', MonitorAudio='%s', TargetScreen='%s', Profile='%s', OutputMode='%s'",
            self._device_label(self._master_device),
            self._device_label(self._monitor_device),
            self._target_screen.name() if self._target_screen else "None",
            prof,
            self._output_mode,
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

    def register_test_player(self, player: Any | None) -> None:
        """Register test player to receive monitor/PFL audio device updates."""
        self._test_player = player
        if self._test_player is not None and self._monitor_device is not None:
            if hasattr(self._test_player, "set_audio_device"):
                self._test_player.set_audio_device(self._monitor_device)

    def register_output_window(self, output_window: Any | None) -> None:
        """Register output window to receive screen routing updates."""
        self._output_window = output_window
        if self._output_window is None:
            return
        if (
            self._output_mode == OutputMode.DUAL.value
            and self._secondary_output_window is None
        ):
            # Dual mode needs both windows: configuring the first one alone
            # would trigger a fallback to single before the second registers.
            return
        self._apply_output_mode()

    def register_secondary_output_window(self, output_window: Any | None) -> None:
        """Register the second output window used by the dual independent mode."""
        self._secondary_output_window = output_window
        if self._secondary_output_window is not None:
            self._apply_output_mode()

    # ── Audio Devices Management ──────────────────────────────────────

    @staticmethod
    def get_available_audio_devices() -> list[QAudioDevice]:
        """Return list of all recognized audio output devices."""
        try:
            return list(QMediaDevices.audioOutputs())
        except Exception as exc:
            logger.warning("[DEVICE-MGR] Error querying audioOutputs: %s", exc)
            return []

    def audio_output_count(self) -> int:
        """Number of audio outputs exposed by the operating system."""
        return len(self.get_available_audio_devices())

    def has_multiple_audio_outputs(self) -> bool:
        """True when master audio and headphone PFL can use separate cards.

        A normal machine exposes a single stereo output: in that case the PFL
        preview would play on the same speakers as the audience, so the UI must
        not offer a separate headphone monitor.
        """
        return self.audio_output_count() > 1

    def get_master_audio_device(self) -> QAudioDevice | None:
        """Audio output used by the live players (audience / PA)."""
        return self._master_device

    def get_monitor_audio_device(self) -> QAudioDevice | None:
        """Audio output used by the preview player (headphones / PFL)."""
        return self._monitor_device

    def set_master_audio_device(self, device: QAudioDevice | None) -> None:
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

    def set_monitor_audio_device(self, device: QAudioDevice | None) -> None:
        """Set output device for Director Headphones / PFL pre-viz audio."""
        if device is None or device.isNull():
            device = QMediaDevices.defaultAudioOutput()
        self._monitor_device = device
        if self._test_player is not None and hasattr(self._test_player, "set_audio_device"):
            self._test_player.set_audio_device(device)
        desc = self._device_label(device)
        logger.info("[DEVICE-MGR] Monitor (PFL) audio device updated to '%s'", desc)
        self.monitor_device_changed.emit(desc)

    # ── Remembered speakers (per computer) ────────────────────────────

    @staticmethod
    def saved_audio_choice(role: str) -> tuple[str, str] | None:
        """``(device id as hex, device name)`` chosen for *role*, or None
        when *role* follows the Windows default."""
        settings = QSettings("BlindCue", "BlindCue")
        dev_id = str(settings.value(f"audio/{role}_id", "") or "")
        name = str(settings.value(f"audio/{role}_name", "") or "")
        return (dev_id, name) if (dev_id or name) else None

    @staticmethod
    def _store_audio_choice(role: str, device: QAudioDevice | None) -> None:
        settings = QSettings("BlindCue", "BlindCue")
        if device is None or device.isNull():
            settings.remove(f"audio/{role}_id")
            settings.remove(f"audio/{role}_name")
        else:
            settings.setValue(f"audio/{role}_id", bytes(device.id()).hex())
            settings.setValue(f"audio/{role}_name", device.description())

    @staticmethod
    def find_audio_device(choice: tuple[str, str], devices: Sequence[QAudioDevice]) -> QAudioDevice | None:
        """The connected device matching a remembered *choice*: same system
        id first (two identical sound cards stay apart), then same name (the
        id of a USB card can change when it goes into another port)."""
        dev_id, name = choice
        if dev_id:
            for dev in devices:
                if bytes(dev.id()).hex() == dev_id:
                    return dev
        if name:
            for dev in devices:
                if dev.description() == name:
                    return dev
        return None

    def _resolve_audio(self, role: str) -> QAudioDevice:
        """Device *role* should play on now: the remembered one when it is
        connected, otherwise the Windows default (and *role* is marked missing)."""
        default = QMediaDevices.defaultAudioOutput()
        choice = self.saved_audio_choice(role)
        if choice is None:
            self._audio_missing.pop(role, None)
            return default
        found = self.find_audio_device(choice, self.get_available_audio_devices())
        if found is not None:
            self._audio_missing.pop(role, None)
            return found
        self._audio_missing[role] = choice[1] or choice[0]
        logger.warning("[DEVICE-MGR] Remembered %s audio '%s' not connected - using the default '%s'",
                       role, self._audio_missing[role], self._device_label(default))
        return default

    def is_audio_remembered(self, role: str) -> bool:
        """True when speakers were chosen for *role* on this computer."""
        return self.saved_audio_choice(role) is not None

    def missing_audio_name(self, role: str) -> str | None:
        """Name of the remembered speakers of *role* while they are unplugged."""
        return self._audio_missing.get(role)

    def audio_notice_text(self) -> str:
        """Status-bar text about remembered speakers that are not connected."""
        if not self._audio_missing:
            return ""
        names = ", ".join(sorted(set(self._audio_missing.values())))
        return (f"Uscita audio scelta non collegata ({names}): "
                f"suona l'uscita predefinita ({self._device_label(QMediaDevices.defaultAudioOutput())})")

    def choose_master_audio(self, device: QAudioDevice | None) -> None:
        """Operator choice for the audience speakers; None = follow Windows."""
        self._store_audio_choice("master", device)
        self._audio_missing.pop("master", None)
        self.set_master_audio_device(device)
        self.audio_notice.emit(self.audio_notice_text())

    def choose_monitor_audio(self, device: QAudioDevice | None) -> None:
        """Operator choice for the headphones (PFL); None = follow Windows."""
        self._store_audio_choice("monitor", device)
        self._audio_missing.pop("monitor", None)
        self.set_monitor_audio_device(device)
        self.audio_notice.emit(self.audio_notice_text())

    def _on_audio_outputs_changed(self) -> None:
        """Handle hardware audio plug/unplug safely.

        Remembered speakers that come back are used again at once (a projector
        plugged in again gets its sound back); remembered speakers that go away
        give way to the Windows default until they return. A role that follows
        the default only moves when its device disappears.
        """
        logger.info("[DEVICE-MGR] Audio outputs hardware change detected!")
        devs = self.get_available_audio_devices()
        dev_ids = {bytes(d.id()) for d in devs}
        missing_before = dict(self._audio_missing)

        for role, current, setter in (
            ("master", self._master_device, self.set_master_audio_device),
            ("monitor", self._monitor_device, self.set_monitor_audio_device),
        ):
            choice = self.saved_audio_choice(role)
            wanted = self.find_audio_device(choice, devs) if choice is not None else None
            if wanted is not None:
                self._audio_missing.pop(role, None)
                if current is None or bytes(current.id()) != bytes(wanted.id()):
                    logger.info("[DEVICE-MGR] Remembered %s audio '%s' is connected again", role,
                                wanted.description())
                    setter(wanted)
                continue
            if choice is not None:
                self._audio_missing[role] = choice[1] or choice[0]
            if current is not None and bytes(current.id()) not in dev_ids:
                logger.warning("[DEVICE-MGR] %s audio device disconnected! Falling back to default.",
                               role.capitalize())
                setter(QMediaDevices.defaultAudioOutput())

        if self._audio_missing != missing_before:
            back = [name for role, name in missing_before.items() if role not in self._audio_missing]
            text = self.audio_notice_text()
            if not text and back:
                text = f"Uscita audio scelta di nuovo collegata: {', '.join(sorted(set(back)))}"
            self.audio_notice.emit(text)

        self.audio_devices_changed.emit()

    # ── Screen Management ─────────────────────────────────────────────

    @staticmethod
    def get_available_screens() -> list[QScreen]:
        """Return list of currently connected screens."""
        app = QGuiApplication.instance()
        return list(app.screens()) if app is not None else []

    def _resolve_output_screens(self) -> None:
        """Assign the physical projectors to outputs A and B.

        The director screen is used for projection only when no external
        display is connected: with one projector everything goes to output A,
        with two or more the second one becomes output B. Manual assignments
        made by the operator are kept as long as those screens stay connected.
        """
        externals = self.get_external_screens()
        if not externals:
            primary = QGuiApplication.primaryScreen()
            self._output_a_screen = primary
            self._output_b_screen = None
            self._target_screen = primary
            return

        settings = QSettings("BlindCue", "BlindCue")
        by_name = {s.name(): s for s in externals}

        saved_a = str(settings.value("output/screen_a", "") or "")
        screen_a = by_name.get(saved_a)
        if screen_a is None:
            screen_a = self._output_a_screen if self._output_a_screen in externals else externals[0]

        screen_b: QScreen | None = None
        if len(externals) >= 2:
            saved_b = str(settings.value("output/screen_b", "") or "")
            screen_b = by_name.get(saved_b)
            if screen_b is None or screen_b == screen_a:
                screen_b = self._output_b_screen
                if screen_b not in externals or screen_b == screen_a:
                    screen_b = next((s for s in externals if s != screen_a), None)

        self._output_a_screen = screen_a
        self._output_b_screen = screen_b
        self._target_screen = screen_a

        settings.setValue("output/screen_a", screen_a.name())
        if screen_b is not None:
            settings.setValue("output/screen_b", screen_b.name())

    def get_output_screens(self) -> tuple[QScreen | None, QScreen | None]:
        """Return the projectors currently assigned to outputs A and B."""
        return self._output_a_screen, self._output_b_screen

    def get_output_screen(self, output: str) -> QScreen | None:
        """Return the projector assigned to *output* (``"A"`` or ``"B"``)."""
        return self._output_b_screen if normalize_output_target(output) == "B" else self._output_a_screen

    def set_output_screen(self, output: str, screen: QScreen | None) -> bool:
        """Assign *screen* to output A or B.

        Choosing the projector already used by the other output swaps the two
        outputs, so the operator never ends up with both windows on the same
        display. Returns ``False`` when the request cannot be honoured
        (unknown screen or output B without two projectors), leaving the
        previous routing untouched.
        """
        if screen is None:
            return False

        target = normalize_output_target(output)
        externals = self.get_external_screens()
        if externals and screen not in externals:
            # A projector window must land on an external display, never on
            # the director monitor.
            logger.warning("[DEVICE-MGR] '%s' non è un proiettore esterno", screen.name())
            return False

        settings = QSettings("BlindCue", "BlindCue")

        if target == "B":
            if not self.is_dual_available():
                return False
            if screen == self._output_a_screen:
                # Swap: output A takes the projector that was driving B.
                self._output_a_screen, self._output_b_screen = screen, self._output_a_screen
            else:
                self._output_b_screen = screen
            settings.setValue("output/screen_b", self._output_b_screen.name())
            settings.setValue("output/screen_a", self._output_a_screen.name())
            logger.info("[DEVICE-MGR] Output B → '%s'", screen.name())
            if self._output_mode == OutputMode.DUAL.value:
                self._apply_output_mode()
            self.screens_changed.emit()
            return True

        if screen == self._output_b_screen:
            # Swap: output B takes the projector that was driving A.
            self._output_b_screen = self._output_a_screen
        self._output_a_screen = screen
        self._target_screen = screen
        settings.setValue("output/screen_a", screen.name())
        if self._output_b_screen is not None:
            settings.setValue("output/screen_b", self._output_b_screen.name())
        logger.info("[DEVICE-MGR] Output A → '%s'", screen.name())
        if self._output_mode == OutputMode.SINGLE.value:
            if self._output_window is not None and hasattr(self._output_window, "set_target_screen"):
                self._output_window.set_target_screen(screen)
            self.target_screen_changed.emit(screen.name())
        else:
            self._apply_output_mode()
        self.screens_changed.emit()
        return True

    def get_target_screen(self) -> QScreen | None:
        """Screen currently used as the main projection output (output A)."""
        return self._target_screen

    def set_target_screen(self, screen: QScreen | None) -> None:
        """Route the live output window to *screen*."""
        if screen is None:
            return
        self._target_screen = screen
        self._output_a_screen = screen
        QSettings("BlindCue", "BlindCue").setValue("output/screen_a", screen.name())
        if self._output_window is not None and hasattr(self._output_window, "set_target_screen"):
            self._output_window.set_target_screen(screen)
        name = screen.name()
        logger.info("[DEVICE-MGR] Target screen updated to '%s'", name)
        self.target_screen_changed.emit(name)

    # ── Output Mode (single screen vs spanned surface) ────────────────

    def get_output_mode(self) -> str:
        """Return the active output routing mode: ``single``, ``span`` or ``dual``."""
        return self._output_mode

    @staticmethod
    def get_external_screens() -> list[QScreen]:
        """Return every screen that is not the primary/director display."""
        app = QGuiApplication.instance()
        if app is None:
            return []
        primary = app.primaryScreen()
        return [s for s in app.screens() if s != primary]

    def is_span_available(self) -> bool:
        """True when at least one external display exists to span onto."""
        return bool(self.get_external_screens())

    def span_warning(self) -> str | None:
        """Return a human-readable warning when spanning may not work here."""
        externals = self.get_external_screens()
        if not externals:
            return (
                "Nessun secondo schermo rilevato: la superficie unica richiede "
                "almeno un proiettore esterno."
            )
        app = QGuiApplication.instance()
        platform_name = (app.platformName() if app is not None else "").lower()
        if platform_name.startswith("wayland") and len(externals) > 1:
            return (
                "Su Wayland un'unica finestra che copre due uscite può essere "
                "rifiutata dal compositore. Se i due proiettori non si uniscono, "
                "usa X11 oppure la modalità due uscite indipendenti."
            )
        return None

    def get_dual_screens(self) -> list[QScreen]:
        """Return the two external screens used by the independent dual mode.

        The operator can swap which projector drives output A and B; the
        manual assignment wins as long as both screens stay connected.
        """
        externals = self.get_external_screens()
        a, b = self._output_a_screen, self._output_b_screen
        if (
            a is not None
            and b is not None
            and a != b
            and a in externals
            and b in externals
        ):
            return [a, b]
        return externals[:2]

    def is_dual_available(self) -> bool:
        """True when two external displays exist for independent outputs."""
        return len(self.get_external_screens()) >= 2

    def dual_warning(self) -> str | None:
        """Return a human-readable warning when dual output cannot run here."""
        if not self.is_dual_available():
            return (
                "La doppia uscita indipendente richiede due proiettori esterni "
                "(oltre al monitor di regia). Con un solo schermo esterno usa "
                "la modalità singola o la superficie unica."
            )
        return None

    def set_output_mode(self, mode: str) -> bool:
        """Apply *mode* to the output window.

        Returns ``False`` when the requested mode cannot be honoured (for
        example spanning with no external display, or dual with fewer than two
        external displays), leaving the previous mode untouched so the show
        never loses its output.
        """
        resolved = normalize_output_mode(mode)
        if resolved == OutputMode.SPAN.value and not self.is_span_available():
            logger.warning("[DEVICE-MGR] Span non disponibile: nessuno schermo esterno")
            return False
        if resolved == OutputMode.DUAL.value and not self.is_dual_available():
            logger.warning("[DEVICE-MGR] Doppia uscita non disponibile: servono due schermi esterni")
            return False

        self._output_mode = resolved
        if not self._apply_output_mode():
            logger.warning("[DEVICE-MGR] Impossibile applicare la modalità '%s'", resolved)
            return False

        QSettings("BlindCue", "BlindCue").setValue("output/mode", resolved)
        logger.info("[DEVICE-MGR] Output mode set to '%s'", resolved)
        self.output_mode_changed.emit(resolved)
        return True

    def _fallback_to_single(self, reason: str) -> None:
        """Switch back to single output so a projector is never left black."""
        logger.warning("[DEVICE-MGR] %s: ritorno a uscita singola", reason)
        self._output_mode = OutputMode.SINGLE.value
        self._apply_output_mode()
        self.output_mode_changed.emit(self._output_mode)

    def _hide_secondary_output(self) -> None:
        window = self._secondary_output_window
        hide = getattr(window, "hide", None)
        if hide is not None:
            hide()

    def _apply_output_mode(self) -> bool:
        """Push the current mode to the registered output window(s)."""
        window = self._output_window
        if window is None:
            return True

        if self._output_mode == OutputMode.DUAL.value:
            screens = self.get_dual_screens()
            secondary = self._secondary_output_window
            if len(screens) < 2 or secondary is None:
                self._fallback_to_single("Doppia uscita non disponibile")
                return False
            try:
                window.configure_screen(screens[0], is_external=True)
                secondary.configure_screen(screens[1], is_external=True)
            except Exception as exc:
                logger.error("[DEVICE-MGR] Errore configurazione doppia uscita: %s", exc)
                self._fallback_to_single("Configurazione doppia uscita fallita")
                return False
            self._target_screen = screens[0]
            logger.info(
                "[DEVICE-MGR] Doppia uscita indipendente: A=%s | B=%s",
                screens[0].name(), screens[1].name(),
            )
            return True

        # Leaving dual mode: hide the second projector window so it cannot
        # keep showing stale frames.
        self._hide_secondary_output()

        if self._output_mode == OutputMode.SPAN.value:
            enter = getattr(window, "enter_span_mode", None)
            if enter is None or not enter(self.get_external_screens()):
                # Fall back to a single output rather than leaving the projector black.
                self._fallback_to_single("Span non applicabile")
                return False
            return True

        target = self._target_screen
        if target is None:
            return True
        primary = QGuiApplication.primaryScreen()
        is_external = target != primary
        spanning = bool(getattr(window, "is_spanning", lambda: False)())
        if spanning:
            # set_target_screen() is a no-op on the same screen; force a fresh
            # configuration so the window leaves the spanned geometry.
            window.configure_screen(target, is_external=is_external)
        elif hasattr(window, "set_target_screen"):
            window.set_target_screen(target)
        return True

    def _on_screens_changed(self, *_args: Any) -> None:
        """Handle monitor plug/unplug events."""
        screens = self.get_available_screens()
        logger.info("[DEVICE-MGR] Display configuration changed (%d screens connected)", len(screens))
        # Re-detect which screens are projectors before applying anything: an
        # unplugged projector must never keep the output window on a dead
        # screen, and a newly connected one becomes the default projection.
        self._resolve_output_screens()
        if self._output_mode == OutputMode.DUAL.value:
            if not self.is_dual_available():
                self._fallback_to_single("Doppia uscita persa: schermo esterno rimosso")
            else:
                self._apply_output_mode()
        elif self._output_mode == OutputMode.SPAN.value:
            if not self.is_span_available():
                logger.warning("[DEVICE-MGR] Span perso: nessuno schermo esterno, torno a singolo")
                self._output_mode = OutputMode.SINGLE.value
                self._apply_output_mode()
                self.output_mode_changed.emit(self._output_mode)
            else:
                self._apply_output_mode()
        elif self._output_mode == OutputMode.SINGLE.value:
            # Follow the projector that was just plugged or unplugged.
            self._apply_output_mode()
        self.screens_changed.emit()

    # ── Hardware Profile Management ───────────────────────────────────

    def get_profile_preference(self) -> str:
        """Operator choice: ``auto``, ``eco``, ``standard`` or ``performance``."""
        return self._profile_preference

    def get_effective_profile(self) -> str:
        """Resolved profile (``auto`` is expanded to a concrete profile)."""
        info = evaluate_hardware_profile(self._profile_preference)
        return info["profile"]

    def get_profile_info(self) -> dict:
        """Full hardware evaluation dict (profile, limits, reasons)."""
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
    def _device_label(dev: QAudioDevice | None) -> str:
        if dev is None or dev.isNull():
            return "Predefinito di Sistema"
        name = dev.description().strip()
        return name if name else "Audio Device"
