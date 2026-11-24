#!/usr/bin/env python3
"""BlindCue – Minimal failsafe cue player for live shows.

100% Native Wayland & Linux architecture.
Dual-window setup:
  • **MainWindow** (Director Panel) on the primary monitor
  • **OutputWindow** (Layer 0 + live media) on the external monitor (or windowed in single-screen test mode)

Usage
-----
    python main.py                  # auto-detect second screen
    python main.py --output-screen 1  # explicit screen index
"""

from __future__ import annotations

import argparse
import gc
import locale
import logging
import os
import shutil
import signal
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Ensure C locale for robust numeric parsing
os.environ["LC_NUMERIC"] = "C"

# ── Console encoding ──────────────────────────────────────────────────
# Windows consoles default to a legacy code page (cp850/cp1252) that cannot
# encode the box-drawing/emoji characters used in log messages; an encoding
# error inside a log handler is noise at best and a hard failure at worst.
# Force UTF-8 with a lossless fallback on every platform.
for _stream in (sys.stdout, sys.stderr):
    try:
        if _stream is not None and hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Logging ───────────────────────────────────────────────────────────
# INFO by default: DEBUG-level chatter is written synchronously by the console
# handler and can stall the GUI thread, which is unacceptable live.  Use
# ``--debug`` when troubleshooting.
_LOG_LEVEL = logging.DEBUG if "--debug" in sys.argv else logging.INFO
_LOG_HANDLERS: list[logging.Handler] = [
    logging.StreamHandler(sys.stderr) if sys.stderr is not None else logging.NullHandler()
]
logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=_LOG_HANDLERS,
)
logger = logging.getLogger("blindcue")

try:
    locale.setlocale(locale.LC_NUMERIC, "C")
except Exception:
    logger.debug("[MAIN] Could not force C numeric locale; using system default", exc_info=True)

# ── Ensure package imports work when running from the project root ────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

# ── Wayland only on Linux ─────────────────────────────────────────────
# X11 is not supported: BlindCUE targets native Wayland exclusively.
# Tests and headless tools set QT_QPA_PLATFORM explicitly (offscreen),
# and that choice must win over this default.
if sys.platform.startswith("linux") and not os.environ.get("QT_QPA_PLATFORM"):
    if os.environ.get("WAYLAND_DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "wayland"
    else:
        print(
            "BlindCue richiede Wayland: nessuna sessione Wayland attiva.\n"
            "X11 non è supportato. Avvia la sessione scegliendo Wayland.",
            file=sys.stderr,
        )
        raise SystemExit(1)

from PySide6.QtCore import QSettings, QStandardPaths, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from ui.main_window import MainWindow
from ui.output_window import OutputWindow
from engine.action_cues import (
    STOP_CANCEL_START,
    STOP_SILENCE,
    action_duration,
    level_trim_after,
    stop_plan,
    target_layers,
)
from engine.envelope import evaluate_cue_level
from engine import player_live as _player_live
from engine import player_mixer as _player_mixer
from engine.player_live import LivePlayer
from engine.player_test import TestPlayer
from engine.show_engine import ShowEngine
from engine.show_scheduler import ScheduledWindow, ShowScheduler
from engine.sleep_inhibitor import SleepInhibitor
from engine import undo_go
from i18n import tr as main_win_tr
from models.cue import (
    ACTION_CALL,
    ACTION_CHECKLIST,
    ACTION_COUNTDOWN,
    ACTION_FADE,
    ACTION_GOTO,
    ACTION_LEVEL,
    ACTION_NOTE,
    ACTION_OPACITY,
    ACTION_PAUSE,
    ACTION_RELEASE,
    ACTION_RESUME,
    ACTION_SEEK,
    ACTION_STOP,
    ACTION_STOPWATCH,
    ACTION_TARGET_ALL,
    ACTION_WAIT,
    Cue,
    CueStatus,
    FollowMode,
    GroupMode,
    MediaType,
    is_placeholder,
    resolve_output_target,
    runtime_layer,
)

# Logo di finestra: vive dentro il pacchetto, quindi è presente anche
# nell'installazione (dove la cartella "immagini di progetto" non esiste).
_LOGO_PATH = _HERE / "assets" / "BlindCue-logo.jpeg"


def _load_app_icon() -> QIcon:
    """Carica l'icona dell'applicazione cercando nel tema di sistema e negli assets."""
    theme_icon = QIcon.fromTheme("blindcue")
    if not theme_icon.isNull():
        return theme_icon

    icon = QIcon()
    assets = _HERE / "assets"
    for name in ("blindcue.ico", "blindcue.png", "blindcue-256.png", "BlindCue-logo.jpeg"):
        p = assets / name
        if p.is_file():
            icon.addFile(str(p))

    if not icon.isNull():
        return icon
    if _LOGO_PATH.is_file():
        return QIcon(str(_LOGO_PATH))
    return icon


def _install_file_logging() -> Path | None:
    """Mirror the log to a rotating file and record uncaught exceptions.

    A live show can crash days after the fact: without a persistent log there is
    nothing to diagnose.  Everything here is best-effort and must never prevent
    the application from starting.
    """
    try:
        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.GenericDataLocation
        )
        if not base:
            return None
        log_dir = Path(base) / "BlindCue"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "blindcue.log"
        handler = RotatingFileHandler(
            log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logging.getLogger().addHandler(handler)
    except Exception:
        logger.debug("[MAIN] Could not open the log file", exc_info=True)
        return None

    def _log_uncaught(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "[MAIN] Uncaught exception", exc_info=(exc_type, exc_value, exc_tb)
        )

    def _log_thread_uncaught(args) -> None:
        if args.exc_type is SystemExit:
            return
        logger.critical(
            "[MAIN] Uncaught exception in thread %s",
            getattr(args.thread, "name", "?"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _log_uncaught
    threading.excepthook = _log_thread_uncaught
    logger.info("[MAIN] Log file: %s", log_file)
    return log_file


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BlindCue – live cue player")
    parser.add_argument(
        "--output-screen", type=int, default=-1,
        help="Index of the screen for the live output (0-based). "
             "Default: auto-detect (first non-primary screen).")
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable verbose DEBUG logging (for troubleshooting only; "
             "INFO is the default for live shows).")
    return parser.parse_args()


def main() -> int:
    """Bootstrap BlindCue and run the Qt event loop.

    Boot order matters; each step depends on the previous one:

    1. ``QApplication`` + rotating file log (so a later failure is recorded).
    2. Preflight of optional FFmpeg tools (waveforms, loudness, normalisation).
    3. Screen detection: projectors are the external screens, never the
       director monitor. No projector → windowed output on the primary screen.
    4. Output windows A/B and the six live players (runtime layers 1-3 → A,
       4-6 → B).
    5. Director ``MainWindow``, then the ``DeviceManager`` that owns audio
       routing, screen assignment and the single/span/dual output mode.
    6. Remote control (HTTP + SSE and OSC), disabled until activated.
    7. Signal wiring: GO, scheduler, live position/duration/EOF, layer
       controls, autosave, shutdown.

    Everything that touches live playback lives in closures below so it can
    reach the players, the windows and the scheduler without global state.
    ``_perform_shutdown`` is the single exit path.
    """
    args = _parse_args()

    # ── Qt Application (100% Native Wayland) ───────────────────────────
    app = QApplication(sys.argv)
    from version import APP_NAME, APP_VERSION
    # Keep the internal name "BlindCue": it decides where settings and autosave live.
    app.setApplicationName("BlindCue")
    app.setOrganizationName("BlindCue")
    app.setApplicationVersion(APP_VERSION)
    logger.info("[MAIN] %s %s", APP_NAME, APP_VERSION)

    _install_file_logging()

    # ── UI language (IT / EN / PL): must run before any widget exists ──
    import i18n
    i18n.install()

    app_icon = _load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    # ── One copy per user: a second launch brings the first to the front ──
    from services.single_instance import SingleInstance, bring_to_front, show_file_from_args
    instance_guard = SingleInstance()
    show_file = show_file_from_args(sys.argv)  # 5.14: a double-click on a .blindcue file
    if not instance_guard.acquire():
        logger.warning("[MAIN] BlindCue is already running - asking it to come to the front")
        if not instance_guard.notify_running(show_file=show_file):
            QMessageBox.information(
                None, "BlindCue",
                "BlindCue è già in esecuzione ma non risponde.\n\n"
                "Potrebbe essere ancora in fase di avvio. Se la sua finestra non "
                "compare, chiudi BlindCue già aperto e riavvia il programma.")
        return 0

    logger.info("Running on native platform: '%s'", app.platformName())

    # ── Runtime dependency preflight ──────────────────────────────────
    # FFmpeg is optional for pure playback but mandatory for waveforms,
    # EBU R128 loudness analysis and audio normalisation.  Detect it once
    # at startup so a missing install is visible instead of silently
    # disabling features mid-show.
    _missing_tools = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if _missing_tools:
        logger.warning(
            "[MAIN] Missing optional media tool(s): %s. Waveforms, loudness "
            "analysis and audio normalisation will be unavailable. Install "
            "FFmpeg and restart BlindCue.", ", ".join(_missing_tools))
    else:
        logger.info("[MAIN] FFmpeg/FFprobe detected – full audio analysis available")

    # ── Screen detection ──────────────────────────────────────────────
    screens = app.screens()
    primary = app.primaryScreen()
    logger.info("Detected %d screen(s). Primary: '%s'",
                len(screens), primary.name() if primary is not None else "None")

    is_external = False
    external_screens = [s for s in screens if s != primary]
    if external_screens:
        logger.info(
            "External projector(s) detected: %s",
            ", ".join(f"'{s.name()}'" for s in external_screens),
        )
    else:
        logger.info("No external projector detected – director screen is the only output.")

    if args.output_screen >= 0:
        if args.output_screen < len(screens):
            output_screen = screens[args.output_screen]
            is_external = (output_screen != primary)
        else:
            logger.error("Screen index %d out of range (0–%d)",
                         args.output_screen, len(screens) - 1)
            return 1
    elif external_screens:
        # Projection always prefers an external display over the director one.
        output_screen = external_screens[0]
        is_external = True
    else:
        output_screen = primary if primary is not None else (screens[0] if screens else None)
        is_external = False
        logger.info("Single screen detected – output will run as a floating preview window.")

    if output_screen is not None:
        logger.info("Output screen: '%s' (%s, is_external=%s)",
                    output_screen.name(), output_screen.geometry(), is_external)
    else:
        logger.warning("No screen reported by Qt platform – running without screen binding.")

    # ── Prevent OS sleep / screen blanking during live shows ──────────
    sleep_inhibitor = SleepInhibitor()
    sleep_inhibitor.acquire()

    # ── Output windows (Layer 0 + live rendering) ─────────────────────
    # Window A is always in use. Window B drives a second independent
    # projector and stays hidden unless the operator selects the dual mode.
    output_win = OutputWindow()
    output_win_b = OutputWindow()

    # Live players: runtime layers 1-3 → output A, 4-6 → output B.
    _ALL_RUNTIME_LAYERS = (1, 2, 3, 4, 5, 6)

    def _out_window(layer: int) -> OutputWindow:
        """Return the projector window (A or B) that owns a runtime layer 1-6."""
        return output_win_b if int(layer) > 3 else output_win

    def _local_layer(layer: int) -> int:
        """Map a runtime layer 1-6 to the 1-3 layer index inside its window."""
        return int(layer) - 3 if int(layer) > 3 else int(layer)

    def _set_layer_opacity(layer: int, opacity: float) -> None:
        _out_window(layer).set_layer_opacity(_local_layer(layer), opacity)

    def _clear_layer(layer: int) -> None:
        _out_window(layer).clear_layer(_local_layer(layer))

    def _dual_output_active() -> bool:
        """True when the two independent projector outputs are currently active."""
        try:
            return device_mgr.get_output_mode() == "dual"
        except (NameError, AttributeError):
            return False

    # A cue that borrowed a spare player (phase D): cue_id -> runtime slot.
    # Shared with the window (``main_win._slot_override``) so the cards, the
    # stop / fade / pause requests and Undo GO all reach the right player.
    slot_override: dict[int, int] = {}
    slot_started_at: dict[int, float] = {}

    def _base_layer(cue: Cue) -> int:
        """Runtime layer 1-6 of *cue* for the active output mode (its own layer).

        A cue assigned to output B while the dual mode is off would land on the
        hidden second window and never reach the audience, so it is projected
        on output A instead.
        """
        return runtime_layer(
            cue.layer,
            resolve_output_target(cue.output_target, _dual_output_active()),
        )

    def _effective_layer(cue: Cue) -> int:
        """Runtime slot *cue* plays on: its layer, or the spare player it borrowed."""
        return slot_override.get(cue.cue_id) or _base_layer(cue)

    def _spare_slots() -> tuple[int, ...]:
        """Players free for borrowing: those of output B while the dual mode is off."""
        return () if _dual_output_active() else (4, 5, 6)

    def _free_spare() -> int | None:
        for slot in _spare_slots():
            if (slot not in active_live_cues and slot not in fading_layers
                    and scheduler.pending_for_layer(slot) is None):
                return slot
        return None

    def _set_override(cue: Cue, slot: int | None) -> None:
        if slot is None:
            slot_override.pop(cue.cue_id, None)
        else:
            # One cue per player: whoever borrowed this one before has lost it.
            for cid in [c for c, s in slot_override.items() if s == slot and c != cue.cue_id]:
                slot_override.pop(cid, None)
                main_win.set_slot_override(cid, None)
            slot_override[cue.cue_id] = slot
        main_win.set_slot_override(cue.cue_id, slot)

    def _spare_running(cue: Cue) -> int | None:
        """The spare player *cue* already plays or waits on (started again: same player)."""
        for slot in _spare_slots():
            on_air = active_live_cues.get(slot)
            waiting = scheduler.pending_for_layer(slot, "PRE")
            if (on_air is not None and on_air.cue_id == cue.cue_id) or (
                    waiting is not None and waiting.cue.cue_id == cue.cue_id):
                return slot
        return None

    def _drop_borrowed(stop: bool) -> None:
        """Forget every borrowed player (output mode changed); *stop*: silence them too."""
        for cid, slot in list(slot_override.items()):
            if stop:
                gone = active_live_cues.pop(slot, None)
                layer_fire_gen[slot] = layer_fire_gen.get(slot, 0) + 1
                scheduler.cancel_layer(slot)
                player = live_players.get(slot)
                if player is not None:
                    player.stop()
                main_win._reset_live_label(slot)
                if gone is not None:
                    gone.status = CueStatus.LOADED
                    for item in main_win._cues:
                        if item.cue_id == gone.cue_id and item.status == CueStatus.LIVE:
                            item.status = CueStatus.LOADED
            slot_override.pop(cid, None)
            main_win.set_slot_override(cid, None)

    def _cue_window(cue: Cue) -> OutputWindow:
        return _out_window(_effective_layer(cue))

    live_players: dict[int, LivePlayer] = {}
    for layer in _ALL_RUNTIME_LAYERS:
        try:
            live_players[layer] = LivePlayer(
                video_widget=_out_window(layer).get_video_widget(_local_layer(layer))
            )
            logger.info("[MAIN] Live player L%d initialised", layer)
        except Exception as exc:
            logger.critical("[MAIN] Could not create live player L%d: %s", layer, exc)
            if layer == 1:
                QMessageBox.critical(
                    None, "BlindCue – Fatal Error",
                    f"Cannot initialise the live multimedia player:\n{exc}")

    # ── Main window (director panel) ALWAYS on primary monitor ────────
    main_win = MainWindow(output_window=output_win, secondary_output_window=output_win_b)
    main_win.bind_to_primary_screen(primary)
    main_win.show()
    instance_guard.activation_requested.connect(lambda: bring_to_front(main_win))
    instance_guard.open_requested.connect(main_win.open_show_from_outside)

    # Attach OutputWindow strictly to target screen after MainWindow maps on primary
    if output_screen is not None:
        output_win.configure_screen(output_screen, is_external=is_external)

    main_win.raise_()
    main_win.activateWindow()

    # ── Test Native Wayland player (muted preview in director panel) ──
    test_player: TestPlayer | None = None
    try:
        test_player = TestPlayer(video_widget=main_win.get_preview_video_widget())
        logger.info("[MAIN] Test player initialised (MUTED)")
    except Exception as exc:
        logger.error("[MAIN] Could not create test player: %s", exc)

    # ── Device & Hardware Routing Manager ─────────────────────────────
    from engine.device_manager import DeviceManager
    device_mgr = DeviceManager()
    device_mgr.register_live_players(list(live_players.values()))
    device_mgr.register_test_player(test_player)
    device_mgr.register_earcon_manager(main_win._earcon_mgr)
    # An explicit --screen on the command line always wins; otherwise the
    # projector assignment restored by DeviceManager is kept untouched.
    if args.output_screen >= 0 and output_screen is not None:
        device_mgr.set_target_screen(output_screen)
    device_mgr.register_output_window(output_win)
    device_mgr.register_secondary_output_window(output_win_b)
    # Keep both projectors on the same surface calibration set
    output_win_b.set_surfaces(output_win.get_surfaces())
    main_win.set_device_manager(device_mgr)
    _player_mixer.install(device_mgr, lambda: main_win._cues)  # 3.2: own mixer: same map of outputs

    # ── LAN Remote Control (Web Server & OSC UDP Automation) ──────────
    # Disabled by default for maximum theatre network safety; activated manually when needed
    from services.remote_manager import RemoteManager
    remote_mgr = RemoteManager(main_win)
    main_win.set_remote_manager(remote_mgr)

    # ── Wire per-layer video deck swap + real-time opacity callbacks ──
    for layer, lp in live_players.items():
        win = _out_window(layer)
        local = _local_layer(layer)
        lp.set_secondary_video_output(win.get_secondary_video_item(local))
        lp.set_deck_switch_callback(lambda deck, w=win, l_idx=local: w.activate_video_deck(l_idx, deck))
        lp.set_opacity_callback(lambda op, w=win, l_idx=local: w.set_layer_opacity(l_idx, op))

    # 4.4: videos that keep their last frame on the layer (ui/held_frames.py).
    from ui.held_frames import HeldFrameController
    held = HeldFrameController(window=main_win, players=live_players,
                               out_window=_out_window, local_layer=_local_layer)

    # ── Connect GO signal to per-layer live engine & Timing Scheduler ─
    active_live_cues: dict[int, Cue] = {}
    known_file_durations: dict[str, float] = {}
    layer_fire_gen: dict[int, int] = {layer: 0 for layer in _ALL_RUNTIME_LAYERS}
    live_positions: dict[int, float] = {layer: 0.0 for layer in _ALL_RUNTIME_LAYERS}
    live_image_envelopes: dict[int, dict] = {}
    live_img_timer = QTimer(main_win)
    live_img_timer.setInterval(33)
    scheduler = ShowScheduler(main_win)
    paused_layers_by_global: set[int] = set()
    # Layers fading out after a stop (cut / Fade All): their EOF must not start
    # a Post-Delay or an auto-follow – the operator asked them to stop.
    fading_layers: set[int] = set()
    # 3.3: playlist transitions. cue_id -> (kind, seconds, extra) for the track about to start
    # ("crossfade" / "overlap": extra = seconds the old track holds its level; "wake": extra = level),
    # and per runtime layer what was already done for the track playing there.
    pending_transitions: dict[int, tuple[str, float, float]] = {}
    playlist_state: dict[int, dict] = {}

    # ── Live video-load guard ─────────────────────────────────────────
    # Measured on this hardware class: one 1080p video per output holds
    # 30 fps; two or more per output start dropping frames because both
    # windows are composited on the CPU by a single thread.  The hint is
    # advisory only and never blocks a GO: the operator stays in control.
    def _refresh_video_budget_hint() -> None:
        dual = str(device_mgr.get_output_mode()) == "dual"
        budget = 1 if dual else 3
        count_a = sum(
            1 for layer, cue in active_live_cues.items()
            if layer <= 3 and cue.media_type == MediaType.VIDEO and not held.holds(layer)
        )
        count_b = sum(
            1 for layer, cue in active_live_cues.items()
            if layer > 3 and cue.media_type == MediaType.VIDEO and not held.holds(layer)
        )
        overloaded: list[str] = []
        if count_a > budget:
            overloaded.append(f"{count_a} video su uscita A")
        if dual and count_b > budget:
            overloaded.append(f"{count_b} video su uscita B")
        if not overloaded:
            main_win.set_performance_hint("")
            return
        limit = (
            "con due uscite attive il limite fluido è 1 video per uscita"
            if dual else "oltre 3 video il proiettore perde fluidità"
        )
        main_win.set_performance_hint(
            "⚠ Carico video elevato: " + ", ".join(overloaded) + f" — {limit}"
        )

    video_budget_timer = QTimer(main_win)
    video_budget_timer.setInterval(1000)
    video_budget_timer.timeout.connect(_refresh_video_budget_hint)
    video_budget_timer.start()

    def _apply_cue_automation(player, cue: Cue, *, hot: bool = False) -> None:
        effective_vol = cue.volume
        is_jam = getattr(main_win, "_jam_mode_active", False)
        if (getattr(cue, "normalize_audio", False) or is_jam) and getattr(cue, "auto_gain_db", 0.0) != 0.0:
            gain_factor = 10.0 ** (cue.auto_gain_db / 20.0)
            effective_vol = max(0.0, min(1.0, cue.volume * gain_factor))
        if not (hasattr(player, "uses_mixer") and player.uses_mixer()):
            # 3.2: the level of the cue's own output row; Qt plays it up to 0 dB (the mixer does the rest).
            effective_vol *= _player_mixer.qt_level(cue)

        kwargs = dict(
            base_volume=effective_vol,
            base_opacity=cue.opacity,
            fade_in=cue.fade_in,
            fade_out=cue.fade_out,
            fade_curve=cue.fade_curve,
            volume_points=cue.volume_points,
            opacity_points=cue.opacity_points,
            sections=cue.sections,
        )
        if hot:
            player.hot_update_automation(**kwargs)
        else:
            player.configure_automation(is_video=(cue.media_type == MediaType.VIDEO), **kwargs)
        if hasattr(player, "set_rate"):  # 3.7: the tempo of this cue (preview and live alike)
            player.set_rate(getattr(cue, "playback_rate", 1.0), getattr(cue, "keep_pitch", True))

    def _eval_image_opacity(cue: Cue, elapsed: float) -> float:
        dur = cue.hold_time if cue.hold_time > 0 else cue.image_timeline_sec
        return evaluate_cue_level(
            elapsed,
            start_sec=0.0,
            end_sec=cue.hold_time if cue.hold_time > 0 else None,
            duration_sec=dur,
            fade_in=cue.fade_in,
            fade_out=cue.fade_out,
            fade_curve=cue.fade_curve,
            points=cue.opacity_points,
            base_level=cue.opacity,
            apply_fade_out_at_end=(cue.hold_time > 0),
        )

    def _resolve_current_cue(cue: Cue) -> Cue:
        """Reconcile *cue* with the current list in MainWindow (handles Undo object replacement)."""
        for item in main_win._cues:
            if item.cue_id == cue.cue_id:
                return item
        return cue

    def _on_live_img_tick() -> None:
        if not live_image_envelopes:
            live_img_timer.stop()
            return
        now = time.monotonic()
        done_layers: list[int] = []
        ticked = dict(live_image_envelopes)  # the entries of this tick (a picture that ends may start the next)
        for l_idx, entry in list(live_image_envelopes.items()):
            if "paused_at" in entry:
                continue  # held by Pause All; a picture started by GO during the pause runs
            try:
                cue_item: Cue = _resolve_current_cue(entry["cue"])
                active_on_layer = active_live_cues.get(l_idx)
                if active_on_layer is None or active_on_layer.cue_id != cue_item.cue_id:
                    done_layers.append(l_idx)
                    continue
                if active_on_layer is not cue_item:
                    active_live_cues[l_idx] = cue_item
                    entry["cue"] = cue_item
                elapsed = max(0.0, now - entry["started"])
                if "lead" not in entry:
                    entry["lead"] = _crossfade_lead(cue_item)  # once per picture: the list does not change
                if entry["lead"] > 0 and elapsed >= cue_item.hold_time - entry["lead"]:
                    # The next picture comes in over this one (#14): the layer is not cleared first.
                    done_layers.append(l_idx)
                    logger.info("[MAIN] Picture '%s' hands Layer %d to the next one (crossfade %.1fs)",
                                cue_item.name, l_idx, entry["lead"])
                    main_win.cue_ended(cue_item)
                    main_win.trigger_auto_follow_from(cue_item)
                    continue
                if cue_item.hold_time > 0 and elapsed >= cue_item.hold_time:
                    done_layers.append(l_idx)
                    op_end = _eval_image_opacity(cue_item, cue_item.hold_time)
                    _set_layer_opacity(l_idx, op_end)
                    _enter_post_delay_or_finalize(
                        cue_item, l_idx, layer_fire_gen.get(l_idx, 0)
                    )
                    logger.info("[MAIN] Image on Layer %d reached hold_time (%.1fs)", l_idx, cue_item.hold_time)
                    continue

                op = _eval_image_opacity(cue_item, elapsed)
                _set_layer_opacity(l_idx, op)
                if cue_item.hold_time > 0:
                    main_win.update_live_layer_progress(
                        l_idx,
                        elapsed,
                        end_sec=cue_item.hold_time,
                        start_sec=0.0,
                        is_looping_inf=False,
                    )

                sel = main_win._selected_cue()
                if (
                    sel is not None
                    and sel.cue_id == cue_item.cue_id
                    and not preview_manual_position
                    and not main_win._img_previz_timer.isActive()
                ):
                    dur = cue_item.hold_time if cue_item.hold_time > 0 else cue_item.image_timeline_sec
                    main_win.set_waveform_playhead_seconds(min(dur, elapsed), dur, source_tag=f"LIVE L{l_idx}")

                if cue_item.hold_time <= 0 and elapsed > entry["anim_end"] + 0.05:
                    done_layers.append(l_idx)
            except Exception as exc:
                logger.error("[MAIN] Error in live image envelope tick L%d: %s", l_idx, exc, exc_info=True)
                done_layers.append(l_idx)

        for l_idx in done_layers:
            if live_image_envelopes.get(l_idx) is ticked.get(l_idx):
                # Only the entry that ended: the next picture an Auto-GO / a scene started on the same
                # layer during this tick keeps its own (it used to be dropped and never ended).
                live_image_envelopes.pop(l_idx, None)
        if not live_image_envelopes:
            live_img_timer.stop()

    live_img_timer.timeout.connect(_on_live_img_tick)

    def _set_global_paused(paused: bool) -> None:
        """Freeze or resume all active live layers, timed image envelopes, and Pre/Post delays."""
        paused = bool(paused)
        if paused == scheduler.is_paused() and bool(getattr(main_win, "_is_global_paused", False)) == paused:
            return
        scheduler.set_paused(paused)
        _player_live.pause_all_tails(paused)
        for out in (output_win, output_win_b):
            out.set_master_fades_paused(paused)  # layer opacity changes from action cues
        now = time.monotonic()
        if paused:
            paused_layers_by_global.clear()
            if live_img_timer.isActive():
                live_img_timer.stop()
            for l_idx, entry in live_image_envelopes.items():
                if "paused_at" not in entry:
                    entry["paused_at"] = now
                    main_win.set_live_layer_paused(l_idx, True)
            for l_idx, lp in live_players.items():
                if l_idx in active_live_cues and lp.is_playing():
                    lp.pause()
                    paused_layers_by_global.add(l_idx)
                    main_win.set_live_layer_paused(l_idx, True)
            for l_idx in _ALL_RUNTIME_LAYERS:
                if scheduler.pending_for_layer(l_idx) is not None:
                    main_win.set_live_layer_paused(l_idx, True)
            main_win.set_global_paused(True)
            logger.info("[MAIN] PAUSA TUTTO activated")
        else:
            for l_idx, entry in live_image_envelopes.items():
                if "paused_at" in entry:
                    entry["started"] += max(0.0, now - entry.pop("paused_at"))
                    main_win.set_live_layer_paused(l_idx, False)
            if live_image_envelopes and not live_img_timer.isActive():
                live_img_timer.start()
            for l_idx in list(paused_layers_by_global):
                if l_idx in active_live_cues and scheduler.pending_for_layer(l_idx, "POST") is None:
                    live_players[l_idx].play()
                    main_win.set_live_layer_paused(l_idx, False)
            paused_layers_by_global.clear()
            for l_idx in _ALL_RUNTIME_LAYERS:
                if scheduler.pending_for_layer(l_idx) is not None:
                    main_win.set_live_layer_paused(l_idx, False)
            main_win.set_global_paused(False)
            logger.info("[MAIN] RIPRENDI TUTTO executed")

    def _finalize_cue_exit(cue: Cue, layer: int, *, expected_gen: int | None = None) -> None:
        """Clear output layer after playback + optional post_delay and trigger AUTO_FOLLOW if enabled."""
        if expected_gen is not None and layer_fire_gen.get(layer) != expected_gen:
            return
        cue = _resolve_current_cue(cue)
        if held.ended(cue, layer):
            # 4.4: it ended, its last frame stays on the layer (the cue stays on air).
            main_win.set_live_section_index(cue.cue_id, -1)
            main_win.cue_ended(cue)
            if _follows_on_its_own(cue):
                main_win.trigger_auto_follow_from(cue)
            return
        lp = live_players.get(layer)
        if lp is not None:
            lp.stop()
        _clear_layer(layer)
        live_image_envelopes.pop(layer, None)
        active_on_layer = active_live_cues.get(layer)
        if active_on_layer is not None and active_on_layer.cue_id == cue.cue_id:
            active_live_cues.pop(layer, None)
        if slot_override.get(cue.cue_id) == layer:
            _set_override(cue, None)  # the spare player is free again
        paused_layers_by_global.discard(layer)
        main_win._reset_live_label(layer)
        main_win.finish_live_cue_status(cue)
        main_win.set_live_section_index(cue.cue_id, -1)
        main_win.cue_ended(cue)  # 2.1: cues that start after its end

        sel = main_win._selected_cue()
        if (
            sel is not None
            and sel.cue_id == cue.cue_id
            and not preview_manual_position
            and (test_player is None or not test_player.is_playing())
            and main_win._active_test_duration > 0
        ):
            main_win.set_waveform_playhead_seconds(
                min(main_win._active_test_duration, cue.in_point),
                main_win._active_test_duration,
                source_tag="PRE-VIZ",
            )

        if _follows_on_its_own(cue):
            main_win.trigger_auto_follow_from(cue)

    def _follows_on_its_own(cue: Cue) -> bool:
        """True when the end of *cue* starts the next one without a GO.

        SEQUENCE ("Cascata") and LOOP ("Loop Scena") containers advance their
        children on their own: the operator picked the mode, so the single
        child does not need to be marked AUTO-GO as well.
        """
        if ShowEngine.outside_go_order(cue):
            return False  # an effect or a relative start never starts the next cue
        return cue.follow_mode == FollowMode.AUTO_FOLLOW.value or ShowEngine.group_mode_of(
            main_win._cues, cue
        ) in (GroupMode.SEQUENCE.value, GroupMode.LOOP.value)

    def _crossfade_lead(cue: Cue) -> float:
        """Seconds before its end a picture hands its layer to the next picture (evaluation #14).

        When the end of *cue* starts the next cue by itself (Auto-GO, a scene "one after
        another") and that cue is a picture with a crossfade on the same layer, the next
        picture starts this many seconds early, over the one still shown: a real crossfade
        instead of a fade in from black after the layer was cleared.
        """
        if cue.media_type != MediaType.IMAGE or cue.hold_time <= 0 or not _follows_on_its_own(cue):
            return 0.0
        if float(getattr(cue, "post_delay", 0.0) or 0.0) > 0.02 or cue.cue_id in main_win._held_auto_go:
            return 0.0
        nxt = main_win.playlist_peek_next(cue)  # 3.3: a photo playlist in random order
        if nxt is None:
            idx = ShowEngine.auto_follow_target(main_win._cues, cue, main_win._released_groups)
            if idx < 0:
                return 0.0
            nxt = main_win._cues[idx]
        seconds = float(getattr(nxt, "crossfade", 0.0) or 0.0)
        if nxt.media_type != MediaType.IMAGE or seconds <= 0 or not getattr(nxt, "enabled", True) \
                or float(getattr(nxt, "pre_delay", 0.0) or 0.0) > 0.02 or _base_layer(nxt) != _base_layer(cue):
            return 0.0
        return min(seconds, cue.hold_time / 2.0)

    def _enter_post_delay_or_finalize(cue: Cue, layer: int, expected_gen: int) -> None:
        if layer_fire_gen.get(layer) != expected_gen:
            return
        # 3.3: the "pause between tracks" of a playlist waits like a Post-Delay
        post_d = max(0.0, float(getattr(cue, "post_delay", 0.0))) + main_win.playlist_gap_after(cue)
        if post_d > 0.02:
            lp = live_players.get(layer)
            if lp is not None and not held.holds(layer, cue.cue_id):  # 4.4: a held frame is a still already
                if cue.media_type == MediaType.VIDEO:
                    # Keep video widget paused on its final frame until post_delay expires
                    lp.pause()
                else:
                    lp.stop()
            main_win.update_live_layer_phase(layer, cue, "POST", 0.0, post_d)
            main_win.set_cue_phase_badge(cue.cue_id, f"POST -{post_d:.1f}s")
            scheduler.schedule("POST", cue, layer, post_d, generation=expected_gen)
            logger.info("[MAIN] Layer %d entered Post-Delay (%.2fs) for '%s'", layer, post_d, cue.name)
        else:
            _finalize_cue_exit(cue, layer, expected_gen=expected_gen)

    def _fade_others_for(cue: Cue, layer: int, restoring: bool = False) -> None:
        """What *cue* replaces elsewhere when it really starts (phase D, 1.16).

        - "Fade the others (N s)": every other sound or video on air fades out
          over N s, except what started together with this cue.
        - A cue on its own layer replaces one that borrowed a spare player for
          that layer (one cue per layer, as before the spares existed).
        """
        if restoring:
            return  # Undo GO bringing a cue back must not fade the others again
        now = time.monotonic()
        seconds = float(getattr(cue, "fade_others", 0.0) or 0.0)
        base = _base_layer(cue)
        for slot, other in list(active_live_cues.items()):
            if slot == layer or other.cue_id == cue.cue_id or slot in fading_layers or held.holds(slot):
                continue  # 4.4: a held last frame is a picture, it is not "playing"
            same_go = now - slot_started_at.get(slot, 0.0) < 0.25
            if seconds > 0 and other.media_type in (MediaType.AUDIO, MediaType.VIDEO) and not same_go:
                fade_secs = seconds
            elif slot != base and slot_override.get(other.cue_id) == slot and _base_layer(other) == base \
                    and layer == base and not getattr(other, "adlib", False):
                fade_secs = 0.05
            else:
                continue
            # Undo GO brings it back from where it was cut off.
            cut_pos = live_positions.get(slot) if other.media_type in (MediaType.AUDIO, MediaType.VIDEO) else None
            main_win.note_replaced(cue, other, cut_pos)
            main_win.mark_layer_stopped(slot)
            if scheduler.pending_for_layer(slot, "PRE") is not None:
                _silence_layer(slot, fade_secs)  # another cue waits there: keep its start
            else:
                _on_layer_clear_requested(slot, fade_override=fade_secs)
            logger.info("[FADE-OTHERS] '%s' fades '%s' (slot %d) over %.2fs", cue.name, other.name, slot, fade_secs)

    def _remaining_from(cue: Cue, dur_sec: float, pos_sec: float) -> float | None:
        """Seconds *cue* still plays from *pos_sec* (None: unknown, looping forever, or sections)."""
        if getattr(cue, "sections", None):
            return None  # repeated / skipped sections: "before the end" waits for the end itself
        if cue.media_type == MediaType.IMAGE:
            return float(cue.hold_time) if cue.hold_time > 0 else None
        if dur_sec <= 0:
            return None
        start, end, infinite = _live_effective_bounds(cue, dur_sec)
        if infinite:
            return None
        passes = max(1, int(cue.loop_count)) if cue.loop else 1
        file_sec = max(0.0, (end - max(start, pos_sec)) + (passes - 1) * (end - start))
        return file_sec / max(0.5, float(getattr(cue, "playback_rate", 1.0)))  # 3.7: seconds of real time

    def _route_audio(cue: Cue, lp, quiet: bool = False) -> None:
        """3.1: the layer's player plays on the cue's logical output; say so when it falls back.

        Called after ``load()`` (which stops what played there): the cue being replaced never gets
        the new cue's device or gain.
        """
        from engine.audio_routes import LABELS, normalize_output

        out = normalize_output(getattr(cue, "audio_output", "stage"))
        route = device_mgr.route_player(lp, out)
        if out in ("hall", "foldback") and route.via != out and not quiet:
            where = main_win_tr(LABELS.get(route.via, route.via))
            main_win._status_label.setText(main_win_tr("'{}': {} non disponibile, suona su: {}").format(
                cue.name, main_win_tr(LABELS[out]), where))
            logger.warning("[AUDIO] '%s': output %s not available, plays via %s", cue.name, out, route.via)

    def _mixer_spec(cue: Cue):
        """3.2: the own mixer's settings for a sound cue that needs them (None: Qt Multimedia plays it)."""
        def _notice(why: str, c=cue) -> None:
            text = ("'{}': mixer disattivato su questo computer: panorama, uscite ed effetti non suonano"
                    if why == "mixer_off" else "'{}': FFmpeg mancante: panorama, uscite ed effetti non suonano")
            main_win._status_label.setText(main_win_tr(text).format(c.name))

        return _player_mixer.spec_for_launch(cue, device_mgr, _notice)

    def _launch_cue_now(cue: Cue, layer: int, expected_gen: int, start_at: float | None = None,
                        restoring: bool = False) -> None:
        """Start actual Audio/Video/Image playback/display for *cue* on *layer*.

        *start_at*: resume from this point of the file (Undo GO), fading in over 1 s.
        """
        if layer_fire_gen.get(layer) != expected_gen:
            return
        if restoring and start_at is None and held.restore(
                cue, layer, seconds=float(getattr(cue, "crossfade", 0.0) or 0.0)):
            # 4.4: Undo GO brings a held video back straight as its last frame.
            fading_layers.discard(layer)
            live_image_envelopes.pop(layer, None)
            active_live_cues[layer] = cue
            if cue.status != CueStatus.LIVE:
                main_win.promote_cue_to_live(cue)
            held.ended(cue, layer)
            return
        lp = live_players.get(layer)
        # Undo GO brings back a picture this cue pushes off its layer, and a
        # sound or video from where it was cut off - taken now, when the cue
        # really starts (after its Pre-Delay), and never for a cue the
        # operator was already fading out.
        before = active_live_cues.get(layer)
        if before is not None and layer not in fading_layers and before.cue_id != cue.cue_id:
            was_held = held.holds(layer, before.cue_id)  # 4.4: a held frame comes back as a picture
            cut_pos = live_positions.get(layer) if (
                before.media_type in (MediaType.AUDIO, MediaType.VIDEO) and not was_held) else None
            main_win.note_replaced(cue, before, cut_pos, held=was_held)
            main_win.rel_reference_gone([before.cue_id])  # its marker / "before the end" cues never come
        held.release(layer)
        # A cue silenced on this layer while this one waited in Pre-Delay is
        # replaced now: this cue's own end must count again.
        fading_layers.discard(layer)
        _fade_others_for(cue, layer, restoring=start_at is not None)
        # Same for a cue (or timed picture) held there by Pause All: this one replaces it.
        if layer in paused_layers_by_global or "paused_at" in live_image_envelopes.get(layer, {}):
            paused_layers_by_global.discard(layer)
            main_win.set_live_layer_paused(layer, False)
        try:
            if cue.status != CueStatus.LIVE:
                main_win.promote_cue_to_live(cue)
            active_live_cues[layer] = cue
            slot_started_at[layer] = time.monotonic()
            known_dur = known_file_durations.get(cue.file_path, 0.0)
            if known_dur <= 0 and main_win._selected_cue() is cue and main_win._active_test_duration > 0:
                known_dur = main_win._active_test_duration
            live_durations[layer] = known_dur
            live_positions[layer] = max(0.0, cue.in_point if start_at is None else start_at)
            live_image_envelopes.pop(layer, None)
            if start_at is None and not restoring:  # Undo GO bringing it back starts nothing relative to it
                # After this launch has finished: what starts relative to it never disturbs it.
                rest = _remaining_from(cue, known_dur, live_positions[layer])
                pos0 = live_positions[layer]
                QTimer.singleShot(0, lambda c=cue, r=rest, p=pos0: main_win.cue_launched(c, r, p))

            if known_dur > 0 and cue.media_type in (MediaType.VIDEO, MediaType.AUDIO):
                s_sec, e_sec, inf_flag = _live_effective_bounds(cue, known_dur)
                main_win.update_live_layer_progress(
                    layer, s_sec, end_sec=e_sec, start_sec=s_sec, is_looping_inf=inf_flag
                )

            # Crossfade: dissolve the picture currently on this layer
            # into the new cue instead of a hard cut.
            if getattr(cue, "crossfade", 0.0) > 0:
                _out_window(layer).begin_crossfade(_local_layer(layer), float(cue.crossfade),
                                                   getattr(cue, "crossfade_style", "dissolve"))
            # A layer dimmed by an action cue starts the new cue at full opacity.
            _out_window(layer).reset_layer_master_opacity(_local_layer(layer))
            # Crossfade of sound (evaluation 2026-11-24): the sound on this layer keeps
            # playing and fades out over the crossfade time instead of being cut.
            xfade = float(getattr(cue, "crossfade", 0.0) or 0.0)
            hold, wake = 0.0, None
            trans = pending_transitions.pop(cue.cue_id, None) if start_at is None else None
            if trans is not None:  # 3.3: the transition of a playlist into this track
                if trans[0] == "crossfade":
                    xfade = max(xfade, trans[1])
                elif trans[0] == "overlap":
                    xfade, hold = trans[1], trans[2]
                elif trans[0] == "wake":
                    wake = (trans[1], trans[2])
            handed = bool(
                xfade > 0 and lp is not None and start_at is None and before is not None
                and before.media_type in (MediaType.AUDIO, MediaType.VIDEO)
                and cue.media_type in (MediaType.AUDIO, MediaType.VIDEO)
                and lp.hand_over_tail(xfade, hold))
            if hold > 0:
                handed = False  # overlap: the track starts at its own level (no longer fade in)

            if cue.media_type == MediaType.VIDEO:
                if lp is not None:
                    init_op = 0.0 if cue.fade_in > 0 else (
                        cue.opacity_points[0][1] if cue.opacity_points else cue.opacity
                    )
                    _out_window(layer).show_video_widget(
                        scale=cue.scale,
                        crop=cue.crop,
                        pos_x=cue.position_x,
                        pos_y=cue.position_y,
                        opacity=init_op,
                        layer=_local_layer(layer),
                        aspect_ratio=cue.aspect_ratio,
                        surface_id=cue.surface_id,
                        rotation=cue.rotation,
                    )
                    lp.use_mixer(None)  # a video always plays on Qt decks
                    lp.load(
                        cue.file_path,
                        start=cue.in_point,
                        end=cue.out_point,
                        resume_at=start_at,
                    )
                    _route_audio(cue, lp)
                    _sleep_on_launch(layer, cue, lp)
                    lp.set_aspect_ratio(cue.aspect_ratio)
                    lp.set_scale(cue.scale)
                    lp.set_crop(cue.crop)
                    _apply_cue_automation(lp, cue, hot=False)
                    if handed:
                        lp.extend_fade_in(xfade)
                    lp.set_loop(cue.loop, cue.loop_count)
                    held.arm(cue, lp)  # 4.4: stops short of the end to keep its last frame
                    lp.play()
                    if start_at is not None:
                        lp.ramp_level(0.0, 0.0)
                        lp.ramp_level(1.0, 1.0)
                    logger.info("[MAIN] Video cue fired to live L%d: %s", layer, cue)

            elif cue.media_type == MediaType.AUDIO:
                if lp is not None:
                    # Clear visual elements ONLY on this target layer; other layers stay live!
                    _clear_layer(layer)
                    lp.use_mixer(_mixer_spec(cue))  # 3.2: pan / outputs / effects, else Qt as before
                    lp.load(
                        cue.file_path,
                        start=cue.in_point,
                        end=cue.out_point,
                        resume_at=start_at,
                    )
                    _route_audio(cue, lp)
                    _sleep_on_launch(layer, cue, lp)
                    _apply_cue_automation(lp, cue, hot=False)
                    if handed:
                        lp.extend_fade_in(xfade)
                    lp.set_loop(cue.loop, cue.loop_count, getattr(cue, "loop_crossfade", 0.0))  # 3.4
                    lp.play()
                    if start_at is not None:
                        lp.ramp_level(0.0, 0.0)
                        lp.ramp_level(1.0, 1.0)
                    logger.info("[MAIN] Audio cue fired to live L%d: %s", layer, cue)

            elif cue.media_type == MediaType.IMAGE:
                # Replace ONLY content on this target layer; video/audio on other layers stay playing!
                if lp is not None:
                    lp.stop()
                init_op = _eval_image_opacity(cue, 0.0)
                _out_window(layer).show_image(
                    layer=_local_layer(layer),
                    file_path=cue.file_path,
                    opacity=init_op,
                    crop=cue.crop,
                    scale=cue.scale,
                    pos_x=cue.position_x,
                    pos_y=cue.position_y,
                    aspect_ratio=cue.aspect_ratio,
                    surface_id=cue.surface_id,
                    rotation=cue.rotation,
                    mask_polygon=cue.mask_polygon,
                    mask_feather=cue.mask_feather,
                )
                anim_end = max(
                    cue.fade_in,
                    max((float(p[0]) for p in cue.opacity_points), default=0.0),
                )
                if cue.fade_in > 0 or cue.opacity_points or cue.hold_time > 0:
                    live_image_envelopes[layer] = {
                        "cue": cue,
                        "started": time.monotonic(),
                        "anim_end": anim_end,
                    }
                    if not live_img_timer.isActive():
                        live_img_timer.start()
                logger.info("[MAIN] Image cue fired on Layer %d: %s", layer, cue)
            if wake is not None and lp is not None and cue.media_type in (MediaType.AUDIO, MediaType.VIDEO):
                lp.ramp_level(0.0, 0.0)  # 3.3: woken with the next track: it comes in to the level it slept at
                lp.ramp_level(wake[1], wake[0])

        except Exception as exc:
            logger.error("[MAIN] Error firing cue on L%d: %s", layer, exc, exc_info=True)
            live_image_envelopes.pop(layer, None)
            _clear_layer(layer)
            active_live_cues.pop(layer, None)
            if slot_override.get(cue.cue_id) == layer:
                _set_override(cue, None)

    def _on_scheduler_tick(win: ScheduledWindow) -> None:
        if layer_fire_gen.get(win.layer) != win.generation:
            return
        if not _is_action_slot(win.layer):
            main_win.update_live_layer_phase(win.layer, win.cue, win.phase, win.elapsed_sec, win.total_sec)
        rem = max(0.0, win.total_sec - win.elapsed_sec)
        main_win.set_cue_phase_badge(win.cue.cue_id, f"{win.phase} -{rem:.1f}s")

    def _on_scheduler_finished(win: ScheduledWindow) -> None:
        if layer_fire_gen.get(win.layer) != win.generation:
            return
        try:
            main_win.set_cue_phase_badge(win.cue.cue_id, "")
            if _is_action_slot(win.layer):
                if win.phase == "PRE":
                    _run_action_now(_resolve_current_cue(win.cue), win.generation)
                elif win.phase == "POST":
                    main_win.trigger_auto_follow_from(_resolve_current_cue(win.cue))
            elif win.phase == "PRE":
                _launch_cue_now(_resolve_current_cue(win.cue), win.layer, win.generation)
            elif win.phase == "POST":
                _finalize_cue_exit(_resolve_current_cue(win.cue), win.layer, expected_gen=win.generation)
        except Exception as exc:
            logger.error("[MAIN] Scheduler finished error on L%d (%s): %s", win.layer, win.phase, exc, exc_info=True)

    scheduler.tick_updated.connect(_on_scheduler_tick)
    scheduler.window_finished.connect(_on_scheduler_finished)

    # ── Action cues: no media, no layer of their own ─────────────────
    # Their Pre-Delay and the wait before an Auto-GO run in the same scheduler
    # (so Pause All and PANIC cover them) under a private key per cue.
    _ACTION_SLOT_BASE = 1000

    def _action_slot(cue: Cue) -> int:
        return _ACTION_SLOT_BASE + int(cue.cue_id)

    def _is_action_slot(layer: int) -> bool:
        return int(layer) >= _ACTION_SLOT_BASE

    def _waiting_cues() -> dict[int, Cue]:
        """Cues counting down their Pre-Delay, by runtime layer."""
        waiting: dict[int, Cue] = {}
        for l_idx in _ALL_RUNTIME_LAYERS:
            win = scheduler.pending_for_layer(l_idx, "PRE")
            if win is not None and layer_fire_gen.get(l_idx) == win.generation:
                waiting[l_idx] = _resolve_current_cue(win.cue)
        return waiting

    def _silence_layer(layer: int, seconds: float) -> None:
        """Fade sound and picture of *layer* to nothing without stopping it.

        The cue waiting there resets both when it starts; meanwhile the end of
        the silenced media must not start a Post-Delay or an Auto-GO.
        """
        fading_layers.add(layer)
        post = scheduler.pending_for_layer(layer, "POST")
        if post is not None:
            # Already in its Post-Delay: that wait would still end in an Auto-GO.
            main_win.set_cue_phase_badge(post.cue.cue_id, "")
            scheduler.cancel_layer(layer, "POST")
        live_image_envelopes.pop(layer, None)  # a timed picture must not reach its end
        lp = live_players.get(layer)
        if lp is not None:
            lp.fade_out(seconds, stop_after=False)
        _out_window(layer).fade_layer_master(_local_layer(layer), 0.0, seconds)

    def _cancel_waiting_start(layer: int) -> None:
        """Cancel only the Pre-Delay start waiting on *layer*; what plays there goes on."""
        pre = scheduler.pending_for_layer(layer, "PRE")
        if pre is None:
            return
        main_win.set_cue_phase_badge(pre.cue.cue_id, "")
        scheduler.cancel_layer(layer, "PRE")
        if slot_override.get(pre.cue.cue_id) == layer:
            _set_override(pre.cue, None)  # the spare player it waited on is free again
        playing = active_live_cues.get(layer)
        if playing is not None:
            main_win._update_live_layer_label(playing, preserve_timing=True)
        else:
            main_win._reset_live_label(layer)

    def _cancel_action_wait(cue_id: int, *, except_slot: int | None = None) -> None:
        """Forget the Pre-Delay / Auto-GO wait of an action cue (deleted or stopped)."""
        slot = _ACTION_SLOT_BASE + int(cue_id)
        if slot == except_slot:
            return
        for phase in ("PRE", "POST"):
            win = scheduler.pending_for_layer(slot, phase)
            if win is not None:
                main_win.set_cue_phase_badge(win.cue.cue_id, "")
        scheduler.cancel_layer(slot)
        layer_fire_gen[slot] = layer_fire_gen.get(slot, 0) + 1

    main_win.action_cancel_requested.connect(_cancel_action_wait)

    def _fire_action_cue(cue: Cue, rel_extra: float = 0.0) -> None:
        """GO on an action cue: never touches a layer's own timing or generation."""
        slot = _action_slot(cue)
        scheduler.cancel_layer(slot)
        gen = layer_fire_gen.get(slot, 0) + 1
        layer_fire_gen[slot] = gen
        pre_d = max(0.0, float(getattr(cue, "pre_delay", 0.0))) + rel_extra
        if pre_d > 0.02:
            main_win.set_cue_phase_badge(cue.cue_id, f"PRE -{pre_d:.1f}s")
            scheduler.schedule("PRE", cue, slot, pre_d, generation=gen)
            logger.info("[ACTION] '%s' scheduled with Pre-Delay %.2fs", cue.name, pre_d)
        else:
            _run_action_now(cue, gen)

    def _seek_layer(l_idx: int, spec: dict) -> bool:
        """2.2: move what plays on *l_idx* (sound or video); False when nothing could move."""
        on_air = active_live_cues.get(l_idx)
        lp = live_players.get(l_idx)
        if on_air is None or lp is None or on_air.media_type not in (MediaType.AUDIO, MediaType.VIDEO) \
                or held.holds(l_idx):  # 4.4: a held last frame has ended
            return False
        dur = live_durations.get(l_idx, 0.0)
        start = max(0.0, on_air.in_point)
        end = _live_effective_bounds(on_air, dur)[1] if dur > 0 else None
        sec = float(spec.get("seek_sec", 0.0))
        mode = spec.get("seek_mode", "relative")
        if mode == "absolute":
            pos = sec
        elif mode == "before_end":
            if end is None:
                logger.info("[ACTION] seek before the end of '%s': its length is not known yet", on_air.name)
                return False
            pos = end - abs(sec)
        else:
            pos = live_positions.get(l_idx, start) + sec
        pos = max(start, pos if end is None else min(pos, end - 0.05))
        lp.seek(pos)
        live_positions[l_idx] = pos
        main_win.cue_retimed(on_air, _remaining_from(on_air, dur, pos), pos)  # its "before the end" / marker cues
        logger.info("[ACTION] seek '%s' (L%d) to %.2fs", on_air.name, l_idx, pos)
        return True

    def _run_action_now(cue: Cue, gen: int) -> None:
        """Carry out *cue*'s action on whatever its targets are playing right now."""
        if layer_fire_gen.get(_action_slot(cue)) != gen:
            return
        spec = cue.action_spec
        kind = spec.get("kind")
        layers: list[int] = []
        try:
            waiting = _waiting_cues()
            dual = _dual_output_active()
            layers = target_layers(spec, main_win._cues, active_live_cues, waiting, dual_active=dual)
            seconds = float(spec.get("duration", 0.0))
            curve = str(spec.get("curve", "linear"))
            if kind in (ACTION_STOP, ACTION_FADE):
                fade = 0.05 if kind == ACTION_STOP else max(0.05, seconds)
                plan = stop_plan(spec, main_win._cues, active_live_cues, waiting, dual_active=dual)
                for l_idx, how in plan.items():
                    if how == STOP_SILENCE:
                        # The layer already waits for a cue that is not a
                        # target (it replaces the chosen one when its
                        # Pre-Delay ends): silence the old cue, keep the start.
                        # The silenced cue is no longer on air for the lists.
                        _silence_layer(l_idx, fade)
                        main_win.mark_layer_stopped(l_idx)
                        pre = scheduler.pending_for_layer(l_idx, "PRE")
                        if pre is not None:  # the panel keeps the countdown of the waiting cue
                            main_win.update_live_layer_phase(
                                l_idx, pre.cue, "PRE", pre.elapsed_sec, pre.total_sec)
                    elif how == STOP_CANCEL_START:
                        _cancel_waiting_start(l_idx)
                    else:
                        main_win.mark_layer_stopped(l_idx)
                        _on_layer_clear_requested(l_idx, fade_override=fade)
                if spec.get("target") == ACTION_TARGET_ALL:
                    # "Everything" also covers other action cues still waiting.
                    for key in scheduler.pending_layers():
                        if _is_action_slot(key):
                            _cancel_action_wait(key - _ACTION_SLOT_BASE, except_slot=_action_slot(cue))
            elif kind == ACTION_RELEASE:
                released = []
                for l_idx in layers:
                    # A looping file or section, and/or a "Loop Scena" group
                    # that would start its first child again: both end after this pass.
                    by_player = live_players[l_idx].release_loop()
                    by_group = main_win.release_loop_scene_of(active_live_cues.get(l_idx))
                    if by_player or by_group:
                        released.append(l_idx)
                layers = released
            elif kind == ACTION_LEVEL:
                for l_idx in layers:
                    lp = live_players[l_idx]
                    st = _sleep_state(l_idx)
                    if st is not None:  # 3.3: asleep: the change is the level it wakes up to
                        st["trim"] = level_trim_after(spec, st["trim"], active_live_cues[l_idx].volume)
                        continue
                    trim = level_trim_after(spec, lp.level_trim(), active_live_cues[l_idx].volume)
                    lp.ramp_level(trim, seconds, curve)
                    main_win.note_level_ramp(l_idx, trim, seconds, cue)  # shown on that card
            elif kind == ACTION_OPACITY:
                for l_idx in layers:
                    _out_window(l_idx).fade_layer_master(
                        _local_layer(l_idx), float(spec.get("level", 1.0)), seconds, curve
                    )
            elif kind in (ACTION_NOTE, ACTION_CHECKLIST):
                main_win.show_operator_note(cue)
            elif kind in (ACTION_GOTO, ACTION_CALL):
                layers = []
                main_win.action_jump(cue)  # 2.2: the window moves GO or starts the cue
            elif kind == ACTION_SEEK:
                layers = [l_idx for l_idx in layers if _seek_layer(l_idx, spec)]
            elif kind == ACTION_COUNTDOWN:
                layers = []
                main_win.start_countdown(float(spec.get("countdown_sec", 0.0)), str(spec.get("text", "")).strip())
            elif kind in (ACTION_PAUSE, ACTION_RESUME):  # 2.11
                sleep = float(spec.get("sleep_sec", 0.0))
                wake_next = kind == ACTION_RESUME and bool(spec.get("wake_next"))  # 3.3
                layers = [l_idx for l_idx in layers if _pause_layer(l_idx, kind == ACTION_PAUSE, sleep, wake_next)]
            elif kind == ACTION_STOPWATCH:
                layers = []
                main_win.stopwatch(str(spec.get("sw_mode", "start")))
            elif kind == ACTION_WAIT:
                layers = []  # the wait itself is the Auto-GO below
            logger.info("[ACTION] '%s' (%s) on layers %s", cue.name, kind, layers)
        except Exception as exc:
            logger.error("[ACTION] '%s' failed: %s", cue.name, exc, exc_info=True)
        main_win.action_cue_done(cue, layers)
        if _follows_on_its_own(cue) or (kind == ACTION_WAIT and not ShowEngine.outside_go_order(cue)):
            # A wait (2.11) always goes on to the next cue: that is what it is for.
            # Wait for the action's own fade/ramp plus the Post-Delay; a short
            # floor keeps a looping group of instant actions from spinning.
            wait = max(0.1, action_duration(spec) + max(0.0, float(cue.post_delay)))
            scheduler.schedule("POST", cue, _action_slot(cue), wait, generation=gen)

    def _on_cue_fired(cue: Cue) -> None:
        """Handle GO: schedule Pre-Delay if set or immediately start cue on its target layer.

        A GO during Pause All starts this cue only: what the pause holds stays
        paused until the operator resumes it (it used to resume everything).
        """
        rel_extra = main_win.take_rel_extra(cue.cue_id)  # 2.1: N s after/before another cue
        if not getattr(cue, "enabled", True):
            logger.info("[MAIN] '%s' is off in this version of the show: not started", cue.name)
            return
        if is_placeholder(cue):
            logger.info("[MAIN] '%s' has no file yet (placeholder): nothing plays", cue.name)  # 3.4
            return
        if cue.media_type == MediaType.ACTION:
            # Branch before the layer logic: an action must not cancel the
            # schedule or bump the generation of the layer it acts on.
            _fire_action_cue(cue, rel_extra)
            return
        running = _spare_running(cue)
        _set_override(cue, None)
        layer = _base_layer(cue)
        adlib_sound = getattr(cue, "adlib", False) and cue.media_type == MediaType.AUDIO
        immediate = float(getattr(cue, "pre_delay", 0.0)) + rel_extra <= 0.02
        if running is not None:
            # Started again while it plays (or waits) on a spare player: from
            # the top on that same player, never a second copy.
            _set_override(cue, running)
            layer = running
            if adlib_sound and immediate:
                main_win._update_live_layer_label(cue)
        elif adlib_sound and _spare_slots():
            # An effect on demand plays on a free player, never over the show's layers.
            spare = _free_spare()
            if spare is None:
                effects = [(slot_started_at.get(s, 0.0), s) for s in _spare_slots()
                           if getattr(active_live_cues.get(s), "adlib", False)]
                if effects:
                    _started, spare = min(effects)
                    old = active_live_cues.get(spare)
                    main_win.mark_layer_stopped(spare)
                    _on_layer_clear_requested(spare, fade_override=0.05)
                    if old is not None:
                        _set_override(old, None)
                    main_win._status_label.setText(main_win_tr(
                        "Tutti i lettori degli effetti sono occupati: '{}' lascia il posto").format(old.name if old else ""))
            if spare is None:
                # Every spare player holds show cues: the effect must not cut the show's music.
                main_win.finish_live_cue_status(cue)
                main_win._status_label.setText(main_win_tr(
                    "Nessun lettore libero per l'effetto '{}': non parte").format(cue.name))
                return
            _set_override(cue, spare)
            layer = spare
            if immediate:
                main_win._update_live_layer_label(cue)
        elif adlib_sound and immediate:
            # No spare player (two outputs on): the effect takes its own layer
            # like any cue, so what played there is shown as replaced.
            main_win.promote_cue_to_live(cue)
        playing = active_live_cues.get(layer)
        if (running is None and getattr(cue, "fade_others", 0.0) > 0 and cue.media_type == MediaType.AUDIO
                and playing is not None and playing.cue_id != cue.cue_id
                and playing.media_type == MediaType.AUDIO and layer not in fading_layers):
            # 1.16: the music on this layer fades out instead of being cut –
            # the new one borrows a spare player (when one is free).
            spare = _free_spare()
            if spare is not None:
                _set_override(cue, spare)
                layer = spare
                if immediate:
                    main_win._update_live_layer_label(cue)  # its card on the spare player
        scheduler.cancel_layer(layer)
        cur_gen = layer_fire_gen.get(layer, 0) + 1
        layer_fire_gen[layer] = cur_gen
        # fading_layers and the Pause All hold of this layer are cleared when
        # this cue really starts (_launch_cue_now): until then the cue fading
        # out there must not start its Auto-GO, and a cue held by the pause
        # stays held (it resumes with the others if the pause ends first).

        pre_d = max(0.0, float(getattr(cue, "pre_delay", 0.0))) + rel_extra
        if pre_d > 0.02:
            main_win.set_cue_phase_badge(cue.cue_id, f"PRE -{pre_d:.1f}s")
            main_win.update_live_layer_phase(layer, cue, "PRE", 0.0, pre_d)
            scheduler.schedule("PRE", cue, layer, pre_d, generation=cur_gen)
            logger.info("[MAIN] Cue '%s' scheduled with Pre-Delay %.2fs on Layer %d", cue.name, pre_d, layer)
        else:
            _launch_cue_now(cue, layer, cur_gen)

    main_win.cue_fired.connect(_on_cue_fired)
    # 2.4: rehearse from here brings back the layer opacity set on the way.
    main_win.layer_opacity_requested.connect(
        lambda slot, level: _out_window(slot).fade_layer_master(_local_layer(slot), float(level), 0.05, "linear"))

    def _on_undo_go(steps: list) -> None:
        """Undo the last GO: only what it started, on the layers where it still is."""
        by_id = {c.cue_id: c for c in main_win._cues}
        main_win.rel_cancel_dependents([step.cue_id for step in steps])  # 2.1: nothing follows them
        for step in steps:
            cue = by_id.get(step.cue_id)
            if cue is not None and cue.media_type == MediaType.ACTION:
                # What it did stays; a Pre-Delay or an Auto-GO wait still running does not.
                _cancel_action_wait(cue.cue_id)
                continue
            if cue is None or step.how in (undo_go.KEEP, undo_go.CONTAINER, undo_go.ENDED):
                continue
            try:
                layer = _effective_layer(cue)
                if step.how == undo_go.CANCEL:
                    pre = scheduler.pending_for_layer(layer, "PRE")
                    if pre is not None and pre.cue.cue_id == cue.cue_id:
                        _cancel_waiting_start(layer)
                    continue
                on_air = active_live_cues.get(layer)
                if on_air is None or on_air.cue_id != cue.cue_id:
                    continue  # something else took the layer since: leave it
                back = by_id.get(step.restore_id) if step.restore_id is not None else None
                if back is not None and step.how != undo_go.RESTORE:
                    # 4.4: a sound / video took the layer of a held last frame: the frame comes back.
                    scheduler.cancel_layer(layer)
                    layer_fire_gen[layer] = layer_fire_gen.get(layer, 0) + 1
                    fading_layers.discard(layer)
                    if held.restore(back, layer, seconds=step.seconds):
                        active_live_cues[layer] = back
                        main_win.promote_cue_to_live(back)
                        held.ended(back, layer)
                    else:
                        main_win.mark_layer_stopped(layer)
                        _on_layer_clear_requested(layer, fade_override=step.seconds)
                elif back is not None:
                    # The picture this cue replaced dissolves back in.
                    scheduler.cancel_layer(layer)
                    gen = layer_fire_gen.get(layer, 0) + 1
                    layer_fire_gen[layer] = gen
                    if getattr(back, "crossfade", 0.0) <= 0:
                        _out_window(layer).begin_crossfade(_local_layer(layer), step.seconds)
                    _launch_cue_now(back, layer, gen, restoring=True)
                elif step.cut_id is not None and step.resume_at is not None and by_id.get(step.cut_id):
                    # The sound/video this GO cut off comes back from where it was (1 s fade in).
                    cut = by_id[step.cut_id]
                    scheduler.cancel_layer(layer)
                    gen = layer_fire_gen.get(layer, 0) + 1
                    layer_fire_gen[layer] = gen
                    _launch_cue_now(cut, layer, gen, start_at=step.resume_at)
                    if scheduler.is_paused():
                        # Undo during Pause All: it comes back paused, like everything else.
                        live_players[layer].pause()
                        paused_layers_by_global.add(layer)
                        main_win.set_live_layer_paused(layer, True)
                else:
                    main_win.mark_layer_stopped(layer)
                    _on_layer_clear_requested(layer, fade_override=step.seconds)
                logger.info("[UNDO-GO] L%d %s '%s'", layer, step.how, cue.name)
            except Exception as exc:
                logger.error("[UNDO-GO] '%s' failed: %s", cue.name, exc, exc_info=True)

    main_win.undo_go_requested.connect(_on_undo_go)

    def _on_release_loop(layer: int) -> None:
        """A card of "Now playing": the loop on *layer* ends after this pass."""
        lp = live_players.get(layer)
        by_player = lp.release_loop() if lp is not None else False
        by_group = main_win.release_loop_scene_of(active_live_cues.get(layer))
        logger.info("[LIVE] Loop released on L%d (file/section: %s, scene: %s)", layer, by_player, by_group)

    main_win.release_loop_requested.connect(_on_release_loop)

    def _on_layer_trim(layer: int, trim: float) -> None:
        """The level slider of a card: the operator's correction of that cue (not saved)."""
        lp = live_players.get(layer)
        if lp is not None and active_live_cues.get(layer) is not None:
            lp.ramp_level(trim, 0.15)

    main_win.layer_trim_requested.connect(_on_layer_trim)

    def _on_card_fade(layer: int) -> None:
        """Fade on a card: only that cue; another cue waiting there still starts."""
        playing = active_live_cues.get(layer)
        pre = scheduler.pending_for_layer(layer, "PRE")
        # A gentle fade: the cue's own fade-out, else the "Fade" time (3 s) - not 0.2 s (evaluation 2026-11-24).
        fade = main_win.button_fade_seconds(playing)
        if playing is not None and pre is not None and pre.cue.cue_id != playing.cue_id:
            _silence_layer(layer, fade)
            main_win.mark_layer_stopped(layer)
            main_win.update_live_layer_phase(layer, pre.cue, "PRE", pre.elapsed_sec, pre.total_sec)
        else:
            main_win.mark_layer_stopped(layer)
            _on_layer_clear_requested(layer, fade_override=fade if playing is not None else None)

    main_win.card_fade_requested.connect(_on_card_fade)
    main_win.layer_cancel_start_requested.connect(_cancel_waiting_start)

    # VU meter next to the master volume (1.14): peaks of every live player, 10 Hz.
    if QSettings("BlindCue", "BlindCue").value("live/vu_meter", True, type=bool):
        for lp in live_players.values():
            try:
                lp.enable_level_tap()
            except Exception as exc:  # noqa: BLE001 - no meter is better than no show
                logger.warning("[VU] level tap not available: %s", exc)
        vu_timer = QTimer(main_win)
        vu_timer.setInterval(100)

        def _vu_tick() -> None:
            level = max((lp.take_peak() for lp in live_players.values()), default=0.0)
            main_win.set_vu_level(level)

        vu_timer.timeout.connect(_vu_tick)
        vu_timer.start()
    # The rehearsal card's stop: at once (a 50 ms fade, no click in the speakers).
    main_win.layer_stop_requested.connect(lambda layer: _on_layer_clear_requested(layer, fade_override=0.05))

    # ── Handle per-layer EOF & Error cleanly ──────────────────────────
    def _on_live_eof(layer: int) -> None:
        """When media on *layer* reaches EOF, enter Post-Delay or clean up immediately."""
        if layer in fading_layers:
            logger.info("[MAIN] EOF on Layer %d while it fades out after a stop: no follow-up", layer)
            return
        try:
            c = active_live_cues.get(layer)
            gen = layer_fire_gen.get(layer, 0)
            if c and c.media_type in (MediaType.VIDEO, MediaType.AUDIO):
                if c.media_type == MediaType.VIDEO:
                    held.freeze(_resolve_current_cue(c), layer)  # 4.4: its last frame stays (when asked)
                _enter_post_delay_or_finalize(c, layer, gen)
            else:
                if layer in live_players:
                    live_players[layer].stop()
                _out_window(layer).hide_video_widget(layer=_local_layer(layer))
            logger.info("[MAIN] Live media finished on Layer %d (EOF)", layer)
        except Exception as exc:
            logger.error("[MAIN] Error on live L%d EOF: %s", layer, exc)

    def _on_live_error(layer: int, err_msg: str) -> None:
        """Per-layer failsafe recovery: clear failing layer (and reveal Tappo if no layers remain)."""
        logger.critical("[MAIN] LIVE PLAYBACK ERROR on Layer %d: %s", layer, err_msg)
        try:
            if layer in live_players:
                live_players[layer].stop()
            _clear_layer(layer)
            c = active_live_cues.pop(layer, None)
            if c is not None:
                c.status = CueStatus.LOADED
                if slot_override.get(c.cue_id) == layer:
                    _set_override(c, None)
            main_win._reset_live_label(layer)
            main_win._refresh_cue_list()
            name = f" '{c.name}'" if c is not None else ""
            main_win._status_label.setText(
                main_win_tr("⚠ Impossibile riprodurre{} (L{}): file mancante, danneggiato o non supportato").format(
                    name, layer))
            main_win._status_label.setToolTip(err_msg)  # Qt's own words stay in the tooltip
        except Exception as exc:
            logger.error("[MAIN] Error during live fallback recovery on L%d: %s", layer, exc)

    live_durations: dict[int, float] = {layer: 0.0 for layer in _ALL_RUNTIME_LAYERS}
    preview_manual_position = False
    test_duration = 0.0

    def _live_effective_bounds(cue: Cue, dur_sec: float) -> tuple[float, float, bool]:
        start_sec = max(0.0, cue.in_point)
        eff_end = dur_sec
        if cue.out_point is not None and cue.out_point > start_sec:
            eff_end = min(dur_sec, cue.out_point)
        is_inf = bool(
            (cue.loop and cue.loop_count <= 0)
            or any(sec.loops == 0 and not sec.skip for sec in cue.sections)
        )
        return start_sec, max(start_sec + 0.001, eff_end), is_inf

    def _playlist_tick(layer: int, cue: Cue, pos_sec: float, dur: float) -> None:
        """3.3: near the end of a playlist track: open the next track in advance (gapless) and, for a
        crossfade / overlap, start it before this one ends (it fades out / plays on as a tail)."""
        from engine import playlist_flow

        if cue.media_type != MediaType.AUDIO or dur <= 0 or layer in fading_layers or cue.loop:
            return
        st = playlist_state.get(layer)
        if st is None or st["cue"] != cue.cue_id:
            st = playlist_state[layer] = {"cue": cue.cue_id, "pre": False, "led": False}
        if st["led"] or _sleep_state(layer) is not None or scheduler.is_paused():
            return
        plan = main_win.playlist_lead(cue)
        if plan is None:
            return
        mode, seconds, nxt = plan
        if (nxt.media_type != MediaType.AUDIO or _base_layer(nxt) != layer or not getattr(nxt, "enabled", True)
                or float(getattr(nxt, "pre_delay", 0.0) or 0.0) > 0.02 or is_placeholder(nxt)):
            return  # another layer, a wait of its own, no file yet: the next track starts at the end, as before
        rest = _remaining_from(cue, dur, pos_sec)
        lp = live_players.get(layer)
        if rest is None or lp is None:
            return
        if not st["pre"] and rest <= playlist_flow.PRELOAD_SEC:
            st["pre"] = True
            lp.preload_next(nxt.file_path, nxt.in_point)
        start, end, _inf = _live_effective_bounds(cue, dur)
        lead = playlist_flow.lead_seconds(mode, seconds, (end - start) / max(0.5, float(cue.playback_rate)))
        if lead <= 0.05 or rest > lead or float(getattr(cue, "post_delay", 0.0) or 0.0) > 0.02:
            return
        st["led"] = True
        hold = max(0.0, rest - float(cue.fade_out or 0.0)) if mode == playlist_flow.OVERLAP else 0.0
        pending_transitions[nxt.cue_id] = (mode, rest, hold)
        logger.info("[PLAYLIST] '%s' -> '%s': %s over %.1fs", cue.name, nxt.name, mode, rest)
        try:
            main_win.cue_ended(cue)
            main_win.trigger_auto_follow_from(cue)
        finally:
            pending_transitions.pop(nxt.cue_id, None)

    def _on_live_duration(layer: int, dur_sec: float) -> None:
        live_durations[layer] = max(0.001, dur_sec)
        live_cue = active_live_cues.get(layer)
        if live_cue is not None:
            known_file_durations[live_cue.file_path] = live_durations[layer]
            main_win.set_known_duration(live_cue.file_path, live_durations[layer])
            if live_cue.media_type in (MediaType.VIDEO, MediaType.AUDIO):
                start_sec, eff_end, is_inf = _live_effective_bounds(live_cue, live_durations[layer])
                cur_pos = max(start_sec, live_positions.get(layer, start_sec))
                main_win.cue_duration_known(live_cue, _remaining_from(live_cue, live_durations[layer], cur_pos))
                main_win.update_live_layer_progress(
                    layer,
                    cur_pos,
                    end_sec=eff_end,
                    start_sec=start_sec,
                    is_looping_inf=is_inf,
                )

    def _on_live_position(layer: int, pos_sec: float) -> None:
        live_positions[layer] = pos_sec
        if scheduler.pending_for_layer(layer, "POST") is not None:
            return
        live_cue = active_live_cues.get(layer)
        dur = live_durations.get(layer, 0.0)
        lp = live_players.get(layer)
        if dur <= 0 and lp is not None and lp.duration_seconds() > 0:
            dur = lp.duration_seconds()
            live_durations[layer] = dur
            if live_cue is not None:
                known_file_durations[live_cue.file_path] = dur

        if live_cue is not None and live_cue.media_type in (MediaType.VIDEO, MediaType.AUDIO):
            start_sec = max(0.0, live_cue.in_point)
            is_inf = bool(
                (live_cue.loop and live_cue.loop_count <= 0)
                or any(sec.loops == 0 and not sec.skip for sec in live_cue.sections)
            )
            if dur > 0:
                start_sec, eff_end, is_inf = _live_effective_bounds(live_cue, dur)
                main_win.update_live_layer_progress(
                    layer,
                    pos_sec,
                    end_sec=eff_end,
                    start_sec=start_sec,
                    is_looping_inf=is_inf,
                )
            elif live_cue.out_point is not None and live_cue.out_point > start_sec:
                main_win.update_live_layer_progress(
                    layer,
                    pos_sec,
                    end_sec=live_cue.out_point,
                    start_sec=start_sec,
                    is_looping_inf=is_inf,
                )
            else:
                # Never cap end_sec to pos_sec while total duration is still unknown
                main_win.update_live_layer_progress(
                    layer,
                    pos_sec,
                    end_sec=None,
                    start_sec=start_sec,
                    is_looping_inf=is_inf,
                )
            _playlist_tick(layer, live_cue, pos_sec, dur)

        if preview_manual_position:
            return
        if test_player is not None and test_player.is_playing():
            return
        sel = main_win._selected_cue()
        if sel is None or live_cue is None or sel.cue_id != live_cue.cue_id:
            return
        wf_dur = dur or main_win._active_test_duration
        if wf_dur > 0:
            main_win.set_waveform_playhead_seconds(pos_sec, wf_dur, source_tag=f"LIVE L{layer}")

    def _on_live_section_changed(layer: int, sec_idx: int) -> None:
        live_cue = active_live_cues.get(layer)
        if live_cue is not None:
            main_win.set_live_section_index(live_cue.cue_id, sec_idx)

    for layer, lp in live_players.items():
        lp.signals.eof_reached.connect(lambda l=layer: _on_live_eof(l))
        lp.signals.error_occurred.connect(lambda msg, l=layer: _on_live_error(l, msg))
        lp.signals.duration_changed.connect(lambda d, l=layer: _on_live_duration(l, d))
        lp.signals.position_changed.connect(lambda p, l=layer: _on_live_position(l, p))
        lp.signals.section_changed.connect(lambda idx, l=layer: _on_live_section_changed(l, idx))

    def _on_live_automation_updated(cue: Cue) -> None:
        """Hot-refresh fades, envelope keyframes, and sections on active Live/Test players."""
        if test_player is not None and main_win._selected_cue() is cue and cue.media_type in (MediaType.VIDEO, MediaType.AUDIO):
            _apply_cue_automation(test_player, cue, hot=True)
        for l_idx, active_c in list(active_live_cues.items()):
            if active_c.cue_id == cue.cue_id and not held.holds(l_idx):  # 4.4: a held frame has ended
                if cue.media_type in (MediaType.VIDEO, MediaType.AUDIO) and l_idx in live_players:
                    _route_audio(cue, live_players[l_idx], quiet=True)  # 3.1: its output changed
                    _apply_cue_automation(live_players[l_idx], cue, hot=True)
                    if cue.media_type == MediaType.VIDEO:
                        held.arm(cue, live_players[l_idx])  # 4.4: "keep the last frame" changed
                    live_players[l_idx].update_mixer(_player_mixer.spec_of(cue))  # 3.2: pan, rows, effects
                elif cue.media_type == MediaType.IMAGE and l_idx not in live_image_envelopes:
                    _set_layer_opacity(l_idx, cue.opacity)

    def _on_section_jump_requested(cue: Cue, idx: int, is_live_jump: bool) -> None:
        nonlocal preview_manual_position
        target_sec = cue.sections[idx].start if 0 <= idx < len(cue.sections) else 0.0
        if is_live_jump and not preview_manual_position and (test_player is None or not test_player.is_playing()):
            for l_idx, active_c in active_live_cues.items():
                if active_c.cue_id == cue.cue_id and l_idx in live_players:
                    live_players[l_idx].jump_to_section(idx)
                    return
        if test_player is not None:
            preview_manual_position = True
            _apply_cue_automation(test_player, cue, hot=False)
            test_player.jump_to_section(idx)
            main_win.set_preview_time(target_sec, test_duration)
            if test_duration > 0:
                main_win.set_waveform_playhead_seconds(target_sec, test_duration, "PRE-VIZ")

    def _on_section_break_loop_requested(cue: Cue, is_live_jump: bool) -> None:
        if is_live_jump and not preview_manual_position and (test_player is None or not test_player.is_playing()):
            for l_idx, active_c in active_live_cues.items():
                if active_c.cue_id == cue.cue_id and l_idx in live_players:
                    live_players[l_idx].break_section_loop()
                    return
        if test_player is not None:
            test_player.break_section_loop()

    main_win.live_automation_updated.connect(_on_live_automation_updated)
    main_win.section_jump_requested.connect(_on_section_jump_requested)
    main_win.section_break_loop_requested.connect(_on_section_break_loop_requested)

    # ── Real-time Live Volume Adjustment ──────────────────────────────
    def _on_live_volume_changed(vol: int) -> None:
        """Adjust volume in real-time on the exact layer running the selected Live cue."""
        selected = main_win._selected_cue()
        if not selected:
            return
        effective_vol_int = vol
        is_jam = getattr(main_win, "_jam_mode_active", False)
        if (getattr(selected, "normalize_audio", False) or is_jam) and getattr(selected, "auto_gain_db", 0.0) != 0.0:
            gain_factor = 10.0 ** (selected.auto_gain_db / 20.0)
            effective_vol_int = int(round(max(0, min(100, vol * gain_factor))))
        for layer, c in active_live_cues.items():
            if c.cue_id == selected.cue_id and layer in live_players:
                live_players[layer].set_volume(effective_vol_int)
                if not main_win.is_live_mode():  # in the show only the player changes
                    selected.volume = vol / 100.0
                logger.debug("[MAIN] Live L%d volume adjusted to %d%% (eff %d%%) for cue '%s'", layer, vol, effective_vol_int, selected.name)
                return
        mirror_layer = _effective_layer(selected)
        if getattr(main_win, "_live_mirror_active", False) and mirror_layer in live_players:
            live_players[mirror_layer].set_volume(effective_vol_int)

    main_win.live_volume_changed.connect(_on_live_volume_changed)

    # ── Connect Layer Clear and Blackout signals (with Micro-Fade) ─────
    def _on_layer_clear_requested(layer: int, fade_override: float | None = None) -> None:
        """Clear media ONLY on *layer* with smooth fade without interrupting other layers.

        *fade_override* (seconds) replaces the cue's own fade-out time; Fade All
        uses it to bring every layer down together.
        """
        try:
            for ph in ("PRE", "POST"):
                pw = scheduler.pending_for_layer(layer, ph)
                if pw is not None:
                    main_win.set_cue_phase_badge(pw.cue.cue_id, "")
            scheduler.cancel_layer(layer)
            cue = active_live_cues.get(layer)
            layer_fire_gen[layer] = layer_fire_gen.get(layer, 0) + 1
            clear_gen = layer_fire_gen[layer]
            paused_layers_by_global.discard(layer)
            fading_layers.add(layer)
            if fade_override is not None:
                fade_time = max(0.05, fade_override)
            else:
                fade_time = max(0.2, cue.fade_out) if cue and cue.fade_out > 0 else 0.2
            lp = live_players.get(layer)

            def _clear_active_if_same(l_idx=layer, expected_gen=clear_gen) -> None:
                if layer_fire_gen.get(l_idx) == expected_gen:
                    gone = active_live_cues.pop(l_idx, None)
                    if gone is not None and slot_override.get(gone.cue_id) == l_idx:
                        _set_override(gone, None)  # the spare player is free again
                    fading_layers.discard(l_idx)
                    live_durations[l_idx] = 0.0
                    live_positions[l_idx] = 0.0

            if cue and held.holds(layer, cue.cue_id):
                live_image_envelopes.pop(layer, None)
                held.fade_out(layer, fade_time, callback=_clear_active_if_same)  # 4.4: like a picture
            elif cue and cue.media_type == MediaType.VIDEO:
                if lp is not None:
                    lp.fade_out(fade_time, stop_after=True)
                _out_window(layer).fade_out_video(fade_time, callback=_clear_active_if_same, layer=_local_layer(layer))
            elif cue and cue.media_type == MediaType.AUDIO:
                if lp is not None:
                    lp.fade_out(fade_time, stop_after=True, callback=_clear_active_if_same)
                else:
                    _clear_active_if_same()
            elif cue and cue.media_type == MediaType.IMAGE:
                live_image_envelopes.pop(layer, None)
                _out_window(layer).fade_out_layer(_local_layer(layer), fade_time, callback=_clear_active_if_same)
            else:
                live_image_envelopes.pop(layer, None)
                held.release(layer)
                _clear_layer(layer)
                active_live_cues.pop(layer, None)
                fading_layers.discard(layer)
            logger.info("[MAIN] Layer %d cleared (fade %.2fs)", layer, fade_time)
        except Exception as exc:
            logger.error("[MAIN] Error clearing layer %d: %s", layer, exc)

    def _on_blackout_requested() -> None:
        """Master Blackout: micro-fade out ALL active layers and reveal Layer 0 (Tappo)."""
        try:
            _player_live.stop_all_tails()
            scheduler.cancel_all()
            scheduler.set_paused(False)
            for out in (output_win, output_win_b):
                out.set_master_fades_paused(False)
            paused_layers_by_global.clear()
            main_win.set_global_paused(False, silent=True)
            live_image_envelopes.clear()
            live_img_timer.stop()
            held.clear_all()  # 4.4: the output fades the held frames with the pictures
            for l_idx in _ALL_RUNTIME_LAYERS:
                layer_fire_gen[l_idx] = layer_fire_gen.get(l_idx, 0) + 1
                live_durations[l_idx] = 0.0
                live_positions[l_idx] = 0.0
            for lp in live_players.values():
                lp.fade_out(0.2, stop_after=True)
            active_live_cues.clear()
            fading_layers.clear()
            for cid in list(slot_override):
                slot_override.pop(cid, None)
                main_win.set_slot_override(cid, None)
            logger.info("[MAIN] Master Blackout executed across all layers (0.2s micro-fade)")
        except Exception as exc:
            logger.error("[MAIN] Error executing blackout: %s", exc)

    def _on_panic_requested() -> None:
        """Immediate 0ms PANIC hard stop across every player, timer, and output layer."""
        try:
            _player_live.stop_all_tails()
            scheduler.cancel_all()
            scheduler.set_paused(False)
            for out in (output_win, output_win_b):
                out.set_master_fades_paused(False)
            paused_layers_by_global.clear()
            main_win.set_global_paused(False, silent=True)
            live_image_envelopes.clear()
            live_img_timer.stop()
            held.clear_all()  # 4.4: the output cuts the held frames with everything else
            for l_idx in _ALL_RUNTIME_LAYERS:
                layer_fire_gen[l_idx] = layer_fire_gen.get(l_idx, 0) + 1
                live_durations[l_idx] = 0.0
                live_positions[l_idx] = 0.0
            for lp in live_players.values():
                lp.stop()
            _player_mixer.panic()  # 3.2: the sound the mixer already queued goes too
            active_live_cues.clear()
            fading_layers.clear()
            for cid in list(slot_override):
                slot_override.pop(cid, None)
                main_win.set_slot_override(cid, None)
            logger.warning("[MAIN] 0ms PANIC STOP ALL completed")
        except Exception as exc:
            logger.error("[MAIN] Error executing PANIC: %s", exc)

    def _on_fade_all_requested(seconds: float) -> None:
        """Fade All: every live layer fades out together over *seconds*, then stops."""
        try:
            _player_live.fade_all_tails(seconds)
            scheduler.cancel_all()
            scheduler.set_paused(False)
            for out in (output_win, output_win_b):
                out.set_master_fades_paused(False)
            paused_layers_by_global.clear()
            main_win.set_global_paused(False, silent=True)
            for layer in list(active_live_cues):
                _on_layer_clear_requested(layer, fade_override=seconds)
            logger.info("[MAIN] Fade All over %.2fs", seconds)
        except Exception as exc:
            logger.error("[MAIN] Error executing Fade All: %s", exc)

    main_win.layer_clear_requested.connect(_on_layer_clear_requested)
    main_win.fade_all_requested.connect(_on_fade_all_requested)
    main_win.blackout_requested.connect(_on_blackout_requested)
    main_win.panic_requested.connect(_on_panic_requested)
    main_win.pause_all_toggled.connect(lambda: _set_global_paused(not scheduler.is_paused()))

    def _on_master_gain(gain: float) -> None:
        """Master volume × mute on every live player (the preview player is not one)."""
        for lp in live_players.values():
            lp.set_master_gain(gain)

    main_win.master_gain_changed.connect(_on_master_gain)
    main_win.pause_all_set.connect(_set_global_paused)

    # 3.3: music put to sleep: layer -> {"token", "cue_id", "parent_id", "trim" (level to wake up to),
    # "falling" (still fading out)}. Valid only for the cue that plays on that layer now.
    sleeping: dict[int, dict] = {}
    sleep_token = [0]

    def _sleep_state(layer: int) -> dict | None:
        st = sleeping.get(layer)
        cue = active_live_cues.get(layer)
        if st is None or cue is None or st["cue_id"] != cue.cue_id:
            sleeping.pop(layer, None)  # another cue plays there now: that sleep is over
            return None
        return st

    def _sleep_on_launch(layer: int, cue: Cue, lp) -> None:
        """A cue starts on *layer*: the sleep there ends - except for the next track of a playlist that
        was falling asleep, which starts silent and falls asleep with it."""
        st = sleeping.pop(layer, None)
        if st is not None and st["falling"] and cue.parent_id is not None and cue.parent_id == st["parent_id"]:
            st["cue_id"] = cue.cue_id
            sleeping[layer] = st
            lp.ramp_level(0.0, 0.0)

    def _asleep(layer: int, token: int) -> None:
        """The fade-out of a sleep is over: pause (also when Pause All came in between)."""
        st = _sleep_state(layer)
        lp = live_players.get(layer)
        if st is None or st["token"] != token or not st["falling"] or lp is None:
            return
        if lp.is_playing() and lp.level_trim() > 0.02:
            QTimer.singleShot(300, lambda: _asleep(layer, token))  # the fade was held (Pause All): wait for it
            return
        st["falling"] = False
        paused_layers_by_global.discard(layer)  # Resume All must not wake it
        if lp.is_playing():
            lp.pause()
        main_win.set_live_layer_paused(layer, True)
        main_win.cue_paused(active_live_cues[layer])
        logger.info("[MAIN] Live Layer %d asleep", layer)

    def _wake_with_next_track(layer: int, live_cue: Cue, lp, st: dict | None, fade: float) -> bool:
        """3.3: a playlist wakes up with its next track (after a break), not where it slept."""
        nxt = main_win.playlist_peek_next(live_cue)
        if nxt is None:
            return False
        level = st["trim"] if st is not None else lp.level_trim()
        sleeping.pop(layer, None)
        paused_layers_by_global.discard(layer)
        main_win.set_live_layer_paused(layer, False)
        if _base_layer(nxt) != layer or is_placeholder(nxt):
            main_win.mark_layer_stopped(layer)  # the next track plays elsewhere (or not at all): this one goes
            _on_layer_clear_requested(layer, fade_override=0.05)
        pending_transitions[nxt.cue_id] = ("wake", max(0.0, fade), level)
        try:
            started = main_win.playlist_skip_to_next(live_cue)
        finally:
            pending_transitions.pop(nxt.cue_id, None)
        logger.info("[MAIN] Live Layer %d woken with the next track '%s'", layer, nxt.name)
        return started

    def _pause_layer(layer: int, pause: bool, fade: float = 0.0, wake_next: bool = False) -> bool:
        """Pause or resume the sound / video on *layer* (its card, a pause action); False: nothing changed.

        3.3: with *fade* the music goes to sleep (fades out, then pauses) or wakes up (plays on from
        where it slept, fading in to the level it had). *wake_next*: a playlist wakes up with its
        next track instead.
        """
        live_cue = active_live_cues.get(layer)
        lp = live_players.get(layer)
        if live_cue is None or lp is None or live_cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return False
        if held.holds(layer):
            return False  # 4.4: a held last frame has ended - "resume" would play the video again
        st = _sleep_state(layer)
        if (not pause and wake_next and (st is not None or not lp.is_playing())
                and _wake_with_next_track(layer, live_cue, lp, st, fade)):
            return True
        if pause:
            if st is not None and st["falling"] and fade <= 0.02:
                st["falling"] = False  # paused at once while falling asleep: asleep now, same level to wake to
            elif st is not None or not lp.is_playing():
                return False  # already asleep / paused
            elif fade > 0.02:
                sleep_token[0] += 1
                token = sleep_token[0]
                sleeping[layer] = {"token": token, "cue_id": live_cue.cue_id, "parent_id": live_cue.parent_id,
                                   "trim": lp.level_trim(), "falling": True}
                lp.ramp_level(0.0, fade)
                QTimer.singleShot(int(fade * 1000) + 30, lambda: _asleep(layer, token))
                logger.info("[MAIN] Live Layer %d goes to sleep in %.1fs", layer, fade)
                return True
            lp.pause()
            main_win.set_live_layer_paused(layer, True)
            main_win.cue_paused(live_cue)  # what waits for its marker / end waits with it
            logger.info("[MAIN] Live Layer %d paused", layer)
            return True
        level = None
        if st is not None:
            sleeping.pop(layer, None)
            level = st["trim"]
            if st["falling"] and lp.is_playing():
                lp.ramp_level(level, max(0.0, fade))  # woken while falling asleep: back up from where it is
                logger.info("[MAIN] Live Layer %d woken while falling asleep", layer)
                return True
        elif lp.is_playing():
            return False  # already playing
        paused_layers_by_global.discard(layer)
        if fade > 0.02:
            level = lp.level_trim() if level is None else level
            lp.ramp_level(0.0, 0.0)
        lp.play()
        if fade > 0.02:
            lp.ramp_level(level, fade)  # wakes up to the level it had
        elif level is not None:
            lp.ramp_level(level, 0.0)
        main_win.set_live_layer_paused(layer, False)
        pos = live_positions.get(layer, max(0.0, live_cue.in_point))
        main_win.cue_resumed(live_cue, _remaining_from(live_cue, live_durations.get(layer, 0.0), pos), pos)
        logger.info("[MAIN] Live Layer %d resumed", layer)
        return True

    def _on_layer_play_pause_requested(layer: int) -> None:
        """Toggle rehearsal pause/resume for active Audio/Video live layer."""
        lp = live_players.get(layer)
        if lp is not None:
            _pause_layer(layer, lp.is_playing())

    main_win.layer_play_pause_requested.connect(_on_layer_play_pause_requested)

    def _on_layer_seek_requested(layer: int, position_sec: float) -> None:
        """Seek active Audio/Video live player to position_sec (rehearsal scrub & skip)."""
        live_cue = active_live_cues.get(layer)
        lp = live_players.get(layer)
        if live_cue is None or lp is None or live_cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return
        if held.holds(layer):
            return  # 4.4: a held last frame is a still, nothing to seek
        dur = live_durations.get(layer, 0.0)
        if dur <= 0 and lp.duration_seconds() > 0:
            dur = lp.duration_seconds()
            live_durations[layer] = dur
        start_sec, eff_end, is_inf = _live_effective_bounds(live_cue, dur if dur > 0 else 999999.0)
        target = max(start_sec, min(eff_end, position_sec))
        lp.seek(target)
        live_positions[layer] = target
        main_win.cue_retimed(live_cue, _remaining_from(live_cue, dur, target), target)  # marker / end waits
        main_win.update_live_layer_progress(
            layer,
            target,
            start_sec=start_sec,
            end_sec=eff_end,
            is_looping_inf=is_inf,
        )
        sel = main_win._selected_cue()
        if sel is not None and sel.cue_id == live_cue.cue_id:
            main_win.set_waveform_playhead_seconds(target, eff_end, "LIVE")
        logger.info("[MAIN] Live Layer %d seeked to %.2fs for cue '%s'", layer, target, live_cue.name)

    main_win.layer_seek_requested.connect(_on_layer_seek_requested)

    # ── Connect preview transport and mute controls ───────────────────
    if test_player is not None:
        main_win.preview_mute_toggled.connect(test_player.set_mute)
        def _on_test_video_opacity(op: float) -> None:
            sel = main_win._selected_cue()
            if sel is not None and sel.media_type == MediaType.VIDEO:
                main_win._preview_monitor.set_opacity(op)
                if main_win._live_mirror_active and sel.status != CueStatus.LIVE:
                    _cue_window(sel).set_layer_opacity(sel.layer, op)

        test_player.set_opacity_callback(_on_test_video_opacity)

        def _is_selected_cue_live() -> bool:
            sel = main_win._selected_cue()
            return (
                sel is not None
                and sel.status == CueStatus.LIVE
                and any(c.cue_id == sel.cue_id for c in active_live_cues.values())
            )

        def _reset_preview_to_in() -> None:
            nonlocal preview_manual_position
            preview_manual_position = False
            main_win.set_preview_audio_playing(False)
            sel = main_win._selected_cue()
            if test_duration > 0 and sel is not None and sel.media_type in (MediaType.VIDEO, MediaType.AUDIO):
                in_pt = min(test_duration, max(0.0, sel.in_point))
                main_win.set_preview_time(in_pt, test_duration)
                main_win.set_waveform_playhead_seconds(in_pt, test_duration, "PRE-VIZ")
            else:
                main_win.set_preview_time(0.0, test_duration)
                main_win.set_waveform_playhead_seconds(None, 0.0)

        def _on_test_duration(d: float) -> None:
            nonlocal test_duration
            test_duration = max(0.001, d)
            sel_for_dur = main_win._selected_cue()
            if sel_for_dur is not None and sel_for_dur.file_path:
                known_file_durations[sel_for_dur.file_path] = test_duration
                main_win.set_known_duration(sel_for_dur.file_path, test_duration)
            main_win.update_waveform_duration(test_duration)
            if not preview_manual_position and not test_player.is_playing() and not _is_selected_cue_live():
                sel = main_win._selected_cue()
                init_pos = (
                    min(test_duration, max(0.0, sel.in_point))
                    if (sel and sel.media_type in (MediaType.VIDEO, MediaType.AUDIO))
                    else 0.0
                )
                main_win.set_preview_time(init_pos, test_duration)
                main_win.set_waveform_playhead_seconds(init_pos, test_duration, "PRE-VIZ")

        def _on_test_position(pos: float) -> None:
            if not test_player.is_playing() and not preview_manual_position and _is_selected_cue_live():
                return
            if test_duration > 0:
                main_win.set_waveform_playhead_seconds(pos, test_duration, "PRE-VIZ")
            main_win.set_preview_time(pos, test_duration)

        def _on_test_stop() -> None:
            cue = main_win._selected_cue()
            if cue is not None and cue.media_type == MediaType.IMAGE:
                main_win.stop_image_preview_playback()
                return
            test_player.stop()
            _reset_preview_to_in()
            if cue is not None:
                main_win._preview_monitor.set_opacity(cue.opacity)
                if main_win._live_mirror_active and cue.status != CueStatus.LIVE:
                    _cue_window(cue).set_layer_opacity(cue.layer, cue.opacity)

        def _on_preview_seek(sec: float) -> None:
            nonlocal preview_manual_position
            preview_manual_position = True
            test_player.seek(sec)
            main_win.set_preview_time(sec, test_duration)
            if test_duration > 0:
                main_win.set_waveform_playhead_seconds(sec, test_duration, "PRE-VIZ")

        test_player.signals.duration_changed.connect(_on_test_duration)
        test_player.signals.position_changed.connect(_on_test_position)
        test_player.signals.eof_reached.connect(_reset_preview_to_in)

        def _on_test_error(msg: str) -> None:
            logger.warning("[MAIN] Pre-Viz error notice: %s", msg)
            main_win._status_label.setText(f"Avviso Pre-Viz: {msg}")

        test_player.signals.error_occurred.connect(_on_test_error)

        def _on_preview_in_out(start: float, end, seek_to_start: bool = True) -> None:
            """Update IN/OUT bounds on TestPlayer; seek only when IN itself changed."""
            if test_player is not None:
                test_player.set_in_out(start, end, seek_to_start=seek_to_start)
                if seek_to_start:
                    main_win.set_preview_time(start, test_duration)
                    if test_duration > 0:
                        main_win.set_waveform_playhead_seconds(start, test_duration, "PRE-VIZ")

        main_win.preview_in_out_changed.connect(_on_preview_in_out)
        main_win.preview_seek_requested.connect(_on_preview_seek)

        def _on_cue_preview_requested(cue) -> None:
            nonlocal test_duration, preview_manual_position
            try:
                test_duration = 0.0
                preview_manual_position = False
                main_win.set_preview_time(0.0, 0.0)
                main_win.set_preview_audio_playing(False)
                if is_placeholder(cue):
                    test_player.stop()  # 3.4: no file yet, nothing to preview
                    return
                if cue.media_type in (MediaType.VIDEO, MediaType.AUDIO):
                    # Prime the waveform section toolbar with a duration measured
                    # earlier: QMediaPlayer emits durationChanged only once per
                    # source, so re-selecting a file may never re-emit it and the
                    # split/zoom controls would stay disabled until another cue
                    # forced the chain.
                    known_dur = known_file_durations.get(cue.file_path, 0.0)
                    if known_dur <= 0:
                        known_dur = main_win._known_file_durations.get(cue.file_path, 0.0)
                    if known_dur > 0:
                        test_duration = known_dur
                        main_win.update_waveform_duration(known_dur)
                if cue.media_type == MediaType.VIDEO:
                    # Load video paused at in_point so first frame appears in preview
                    main_win.show_preview_video(
                        scale=cue.scale, crop=cue.crop,
                        pos_x=cue.position_x, pos_y=cue.position_y,
                        opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
                        rotation=cue.rotation,
                    )
                    test_player.load(cue.file_path, start=cue.in_point, end=cue.out_point, pause=True)
                    _apply_cue_automation(test_player, cue, hot=False)
                    test_player.set_aspect_ratio(cue.aspect_ratio)
                    test_player.set_scale(cue.scale)
                    test_player.set_crop(cue.crop)
                elif cue.media_type == MediaType.AUDIO:
                    # Load audio paused at in_point to extract duration immediately
                    main_win.show_preview_audio()
                    test_player.load(cue.file_path, start=cue.in_point, end=cue.out_point, pause=True)
                    _apply_cue_automation(test_player, cue, hot=False)
                elif cue.media_type == MediaType.IMAGE:
                    test_player.stop()
                    main_win.show_preview_image(
                        cue.file_path, scale=cue.scale, crop=cue.crop,
                        pos_x=cue.position_x, pos_y=cue.position_y,
                        opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
                        rotation=cue.rotation, mask_polygon=cue.mask_polygon,
                        mask_feather=cue.mask_feather,
                    )
                    dur_img = cue.hold_time if cue.hold_time > 0 else cue.image_timeline_sec
                    main_win.set_preview_time(0.0, dur_img)
            except Exception as exc:
                logger.error("[MAIN] Cue preview request failed: %s", exc)

        main_win.cue_preview_requested.connect(_on_cue_preview_requested)

        def _test_play_selected(mw: MainWindow, tp: TestPlayer) -> None:
            nonlocal preview_manual_position
            cue = mw._selected_cue()
            if cue is None or not cue.media_type.has_file or is_placeholder(cue):
                return  # groups, action cues and placeholders (3.4) have nothing to rehearse here
            if cue.media_type == MediaType.IMAGE:
                preview_manual_position = True
                mw.start_image_preview_playback(cue)
                return
            try:
                preview_manual_position = True
                if cue.media_type == MediaType.VIDEO:
                    mw.show_preview_video(
                        scale=cue.scale, crop=cue.crop,
                        pos_x=cue.position_x, pos_y=cue.position_y,
                        opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
                        rotation=cue.rotation,
                    )
                elif cue.media_type == MediaType.AUDIO:
                    mw.show_preview_audio()
                    mw.set_preview_audio_playing(True)

                # If paused, apply latest automation & loop and resume directly from current playhead!
                if tp.is_paused() and not tp.is_idle():
                    _apply_cue_automation(tp, cue, hot=True)
                    tp.set_loop(cue.loop, cue.loop_count)
                    tp.play()
                    return
                tp.load(cue.file_path, start=cue.in_point, end=cue.out_point)
                _apply_cue_automation(tp, cue, hot=False)
                tp.set_aspect_ratio(cue.aspect_ratio)
                tp.set_scale(cue.scale)
                tp.set_crop(cue.crop)
                tp.set_loop(cue.loop, cue.loop_count)
                tp.play()
                logger.info("[MAIN] Preview playing: %s", cue.file_path)
            except Exception as exc:
                logger.error("[MAIN] Test play failed: %s", exc)

        def _on_test_pause() -> None:
            cue = main_win._selected_cue()
            if cue is not None and cue.media_type == MediaType.IMAGE:
                main_win.pause_image_preview_playback()
                return
            test_player.pause()
            main_win.set_preview_audio_playing(False)

        main_win._btn_test_play.clicked.connect(
            lambda: _test_play_selected(main_win, test_player))
        main_win._btn_test_pause.clicked.connect(_on_test_pause)
        main_win._btn_test_stop.clicked.connect(_on_test_stop)

    # ── Output mode safety: never leave media running on a hidden projector ──
    def _on_output_mode_changed(mode: str) -> None:
        """Stop whatever is still playing on output B when dual mode is left.

        The second projector window is hidden as soon as dual mode is disabled:
        keeping a cue live there would leave audio running with no visible
        layer to control it.
        """
        # Players 4-6 change role (spares <-> output B): nothing keeps a borrowed one.
        _drop_borrowed(stop=str(mode) == "dual")
        if str(mode) == "dual":
            main_win._refresh_cue_list()
            return
        stopped: list[str] = []
        for layer in (4, 5, 6):
            cue = active_live_cues.pop(layer, None)
            held.release(layer)
            layer_fire_gen[layer] = layer_fire_gen.get(layer, 0) + 1
            live_durations[layer] = 0.0
            live_positions[layer] = 0.0
            live_image_envelopes.pop(layer, None)
            player = live_players.get(layer)
            if player is not None:
                player.stop()
            _clear_layer(layer)
            main_win._reset_live_label(layer)
            if cue is not None:
                cue.status = CueStatus.LOADED
                stopped.append(cue.name)
                logger.warning(
                    "[MAIN] Output B disabled – stopped live layer %d ('%s')",
                    layer, cue.name,
                )
        if stopped:
            main_win._refresh_cue_list()
            main_win._status_label.setText(
                "Uscita B disattivata: interrotti " + ", ".join(stopped)
            )

    device_mgr.output_mode_changed.connect(_on_output_mode_changed)

    # ── Graceful shutdown on SIGINT / SIGTERM / UI close (aboutToQuit) ─
    _shutdown_state = {"signalled": False, "performed": False}

    def _perform_shutdown(*, from_about_to_quit: bool = False) -> None:
        if _shutdown_state["performed"]:
            return
        _shutdown_state["performed"] = True
        logger.info("[MAIN] Performing graceful shutdown")
        try:
            remote_mgr.stop_all()
        except Exception:
            logger.debug("[MAIN] remote_mgr.stop_all failed during shutdown", exc_info=True)
        try:
            scheduler.cancel_all()
        except Exception:
            pass
        live_img_timer.stop()
        video_budget_timer.stop()
        timer.stop()
        main_win._force_closing = True
        for lp in live_players.values():
            try:
                lp.shutdown()
            except Exception:
                logger.debug("[MAIN] LivePlayer shutdown failed", exc_info=True)
        try:
            _player_mixer.shutdown()  # 3.2: audio thread and decoders
        except Exception:
            logger.debug("[MAIN] mixer shutdown failed", exc_info=True)
        if test_player is not None:
            try:
                test_player.shutdown()
            except Exception:
                logger.debug("[MAIN] TestPlayer shutdown failed", exc_info=True)
        try:
            sleep_inhibitor.release()
        except Exception:
            pass
        output_win.force_close()
        output_win_b.force_close()
        if not from_about_to_quit:
            main_win.close()
            app.quit()

    app.aboutToQuit.connect(lambda: _perform_shutdown(from_about_to_quit=True))

    def _shutdown(*_args) -> None:
        # Python signal handlers run in the main thread, but may fire mid-slot
        # (re-entrant). Defer the teardown to the next event-loop turn and run once.
        if _shutdown_state["signalled"]:
            return
        _shutdown_state["signalled"] = True
        logger.info("[MAIN] Shutdown signal received")
        QTimer.singleShot(0, _perform_shutdown)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Allow Python signal handlers to run while the Qt event loop blocks
    timer = QTimer(main_win)
    timer.start(200)
    timer.timeout.connect(lambda: None)

    logger.info("═══ %s %s started (platform: %s) ═══", APP_NAME, APP_VERSION, app.platformName())

    # ── Python GC tuning for live stability ───────────────────────────
    # Long-lived objects (Qt widget tree, modules, the loaded show) are moved
    # to the permanent generation, so full collections no longer scan them.
    # Measured effect: the worst GUI-thread stall drops from seconds to a
    # fraction of a second while several videos are decoding.
    try:
        gc.collect()
        gc.freeze()
        logger.info(
            "[MAIN] GC frozen: %d objects excluded from future collections",
            gc.get_freeze_count(),
        )
    except Exception:
        logger.warning("[MAIN] Could not freeze the GC", exc_info=True)

    # Ask about an interrupted session only now, with the output windows,
    # the DeviceManager and the monitor hotplug handling in place. Scheduled
    # from the MainWindow constructor, the question ran inside the
    # processEvents() of OutputWindow.configure_screen(), half-way through
    # this boot: the output stayed full screen and on top, and unplugging the
    # projector left it covering the director screen.
    def _startup_questions() -> None:
        main_win._check_crash_recovery()
        if show_file:
            main_win.open_show_from_outside(show_file)  # after the restore question, never inside it
        else:
            main_win._show_start_page_if_wanted()  # 5.16: no show yet - what to do first

    QTimer.singleShot(150, _startup_questions)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
