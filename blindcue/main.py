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
import locale
import logging
import os
import signal
import sys
from pathlib import Path

# Ensure C locale for robust numeric parsing
os.environ["LC_NUMERIC"] = "C"
try:
    locale.setlocale(locale.LC_NUMERIC, "C")
except Exception:
    pass

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("blindcue")

# ── Ensure package imports work when running from the project root ────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from ui.main_window import MainWindow
from ui.output_window import OutputWindow
from engine.player_live import LivePlayer
from engine.player_test import TestPlayer
from models.cue import MediaType

_PROJECT_ROOT = _HERE.parent
_LOGO_PATH = _PROJECT_ROOT / "immagini di progetto" / "BlindCue-logo.jpeg"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BlindCue – live cue player")
    parser.add_argument(
        "--output-screen", type=int, default=-1,
        help="Index of the screen for the live output (0-based). "
             "Default: auto-detect (first non-primary screen).")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    # ── Qt Application (100% Native Wayland) ───────────────────────────
    app = QApplication(sys.argv)
    app.setApplicationName("BlindCue")
    app.setOrganizationName("BlindCue")
    app.setApplicationVersion("0.1")

    if _LOGO_PATH.is_file():
        app.setWindowIcon(QIcon(str(_LOGO_PATH)))

    logger.info("Running on native platform: '%s'", app.platformName())

    # ── Screen detection ──────────────────────────────────────────────
    screens = app.screens()
    primary = app.primaryScreen()
    logger.info("Detected %d screen(s). Primary: '%s'",
                len(screens), primary.name())

    is_external = False
    if args.output_screen >= 0:
        if args.output_screen < len(screens):
            output_screen = screens[args.output_screen]
            is_external = (output_screen != primary)
        else:
            logger.error("Screen index %d out of range (0–%d)",
                         args.output_screen, len(screens) - 1)
            return 1
    elif len(screens) > 1:
        # Pick first non-primary screen
        output_screen = next(
            (s for s in screens if s != primary), screens[-1])
        is_external = True
    else:
        output_screen = primary
        is_external = False
        logger.info("Single screen detected – output will run as a floating preview window.")

    logger.info("Output screen: '%s' (%s, is_external=%s)",
                output_screen.name(), output_screen.geometry(), is_external)

    # ── Output window (Layer 0 + live rendering) ──────────────────────
    output_win = OutputWindow()
    output_win.configure_screen(output_screen, is_external=is_external)

    # ── Live Native Wayland player ────────────────────────────────────
    live_player: LivePlayer | None = None
    try:
        live_player = LivePlayer(video_widget=output_win.get_video_widget())
        logger.info("[MAIN] Live player initialised")
    except Exception as exc:
        logger.critical("[MAIN] Could not create live player: %s", exc)
        QMessageBox.critical(
            None, "BlindCue – Fatal Error",
            f"Cannot initialise the live multimedia player:\n{exc}")

    # ── Main window (director panel) ──────────────────────────────────
    main_win = MainWindow(output_window=output_win)
    main_win.show()
    main_win.raise_()
    main_win.activateWindow()

    # ── Test Native Wayland player (muted preview in director panel) ──
    test_player: TestPlayer | None = None
    try:
        test_player = TestPlayer(video_widget=main_win.get_preview_video_widget())
        logger.info("[MAIN] Test player initialised (MUTED)")
    except Exception as exc:
        logger.error("[MAIN] Could not create test player: %s", exc)

    # ── Connect GO signal to live player ──────────────────────────────
    active_live_cues: dict[int, Cue] = {}

    def _on_cue_fired(cue) -> None:
        """Handle the GO button: load & play the cue on the live output."""
        try:
            active_live_cues[cue.layer] = cue
            target_vol = int(cue.volume * 100)

            if cue.media_type == MediaType.VIDEO:
                if live_player is not None:
                    output_win.show_video_widget(
                        scale=cue.scale,
                        crop=cue.crop,
                        pos_x=cue.position_x,
                        pos_y=cue.position_y,
                        opacity=cue.opacity,
                    )
                    live_player.load(
                        cue.file_path,
                        start=cue.in_point,
                        end=cue.out_point,
                    )
                    live_player.set_aspect_ratio(cue.aspect_ratio)
                    live_player.set_scale(cue.scale)
                    live_player.set_crop(cue.crop)
                    live_player.set_loop(cue.loop)

                    if cue.fade_in > 0:
                        live_player.fade_in(target_vol, cue.fade_in)
                    else:
                        live_player.set_volume(target_vol)

                    live_player.play()
                    logger.info("[MAIN] Video cue fired to live: %s", cue)

            elif cue.media_type == MediaType.AUDIO:
                if live_player is not None:
                    # Hide video player container to keep Layer 0 (Tappo) visible
                    output_win.hide_video_widget()
                    live_player.load(
                        cue.file_path,
                        start=cue.in_point,
                        end=cue.out_point,
                    )
                    live_player.set_loop(cue.loop)

                    if cue.fade_in > 0:
                        live_player.fade_in(target_vol, cue.fade_in)
                    else:
                        live_player.set_volume(target_vol)

                    live_player.play()
                    logger.info("[MAIN] Audio cue fired to live: %s", cue)

            elif cue.media_type == MediaType.IMAGE:
                # Stop video stream if any, and render static image on specified layer
                if live_player is not None:
                    live_player.stop()
                output_win.hide_video_widget()
                output_win.show_image(
                    layer=cue.layer,
                    file_path=cue.file_path,
                    opacity=cue.opacity,
                    crop=cue.crop,
                    scale=cue.scale,
                    pos_x=cue.position_x,
                    pos_y=cue.position_y,
                )
                logger.info("[MAIN] Image cue fired on Layer %d: %s", cue.layer, cue)

                # Auto-removal if hold_time is set
                if cue.hold_time > 0:
                    l_target = cue.layer
                    def _clear_held_image(layer_idx=l_target, target_cue=cue) -> None:
                        if active_live_cues.get(layer_idx) == target_cue:
                            output_win.clear_layer(layer_idx)
                            active_live_cues.pop(layer_idx, None)
                            main_win._reset_live_label(layer_idx)
                            target_cue.status = CueStatus.LOADED
                            main_win._refresh_cue_list()
                            logger.info("[MAIN] Image on Layer %d auto-expired after %.1fs",
                                        layer_idx, target_cue.hold_time)

                    QTimer.singleShot(int(cue.hold_time * 1000), _clear_held_image)

        except Exception as exc:
            logger.error("[MAIN] Error firing cue: %s", exc, exc_info=True)
            output_win.show_fallback()

    main_win.cue_fired.connect(_on_cue_fired)

    # ── Handle EOF on live player (auto-hide video and reset live state) ─
    if live_player is not None:
        def _on_live_eof() -> None:
            """When live video or audio reaches EOF, hide video and clear live status."""
            try:
                output_win.hide_video_widget()
                for layer, c in list(active_live_cues.items()):
                    if c.media_type in (MediaType.VIDEO, MediaType.AUDIO):
                        active_live_cues.pop(layer, None)
                        main_win._reset_live_label(layer)
                        c.status = CueStatus.LOADED
                main_win._refresh_cue_list()
                logger.info("[MAIN] Live media finished (EOF) – video hidden, layer cleared")
            except Exception as exc:
                logger.error("[MAIN] Error on live EOF: %s", exc)

        live_player.signals.eof_reached.connect(_on_live_eof)

        def _on_live_error(err_msg: str) -> None:
            """Failsafe recovery: restore Layer 0 (Tappo) immediately if live media fails."""
            logger.critical("[MAIN] LIVE PLAYBACK ERROR: %s — Restoring Layer 0 (Tappo) immediately!", err_msg)
            try:
                output_win.show_fallback()
                for layer in list(active_live_cues.keys()):
                    main_win._reset_live_label(layer)
                active_live_cues.clear()
                main_win._refresh_cue_list()
                main_win._status_label.setText(f"ATTENZIONE: Errore Live ({err_msg}) — Tappo Failsafe attivo")
            except Exception as exc:
                logger.error("[MAIN] Error during live fallback recovery: %s", exc)

        live_player.signals.error_occurred.connect(_on_live_error)

    # ── Real-time Live Volume Adjustment ──────────────────────────────
    def _on_live_volume_changed(vol: int) -> None:
        """Adjust volume in real-time when editing an active Live cue."""
        if live_player is not None:
            selected = main_win._selected_cue()
            if selected and any(c.cue_id == selected.cue_id for c in active_live_cues.values()):
                live_player.set_volume(vol)
                selected.volume = vol / 100.0
                logger.debug("[MAIN] Live volume adjusted in real-time to %d%% for cue '%s'", vol, selected.name)
            elif main_win._btn_mirror_live.isChecked():
                live_player.set_volume(vol)

    main_win.live_volume_changed.connect(_on_live_volume_changed)

    # ── Connect Layer Clear and Blackout signals (with 0.2s Micro-Fade) ─
    def _on_layer_clear_requested(layer: int) -> None:
        """Clear media on a specific layer with a 0.2s micro-fade to avoid harsh cuts / audio pops."""
        try:
            cue = active_live_cues.get(layer)
            if cue and cue.media_type in (MediaType.VIDEO, MediaType.AUDIO):
                if live_player is not None:
                    live_player.fade_out(0.2, stop_after=True)
                output_win.fade_out_video(0.2, callback=lambda: active_live_cues.pop(layer, None))
            elif cue and cue.media_type == MediaType.IMAGE:
                output_win.fade_out_layer(layer, 0.2, callback=lambda: active_live_cues.pop(layer, None))
            else:
                output_win.clear_layer(layer)
                active_live_cues.pop(layer, None)
            logger.info("[MAIN] Layer %d cleared (micro-fade 0.2s)", layer)
        except Exception as exc:
            logger.error("[MAIN] Error clearing layer %d: %s", layer, exc)

    def _on_blackout_requested() -> None:
        """Master Blackout: micro-fade out all live media and reveal Layer 0 (Tappo)."""
        try:
            if live_player is not None:
                live_player.fade_out(0.2, stop_after=True)
            output_win.show_fallback(fade_duration_sec=0.2)
            active_live_cues.clear()
            logger.info("[MAIN] Master Blackout executed with 0.2s micro-fade")
        except Exception as exc:
            logger.error("[MAIN] Error executing blackout: %s", exc)

    main_win.layer_clear_requested.connect(_on_layer_clear_requested)
    main_win.blackout_requested.connect(_on_blackout_requested)

    # ── Connect preview transport and mute controls ───────────────────
    if test_player is not None:
        main_win.preview_mute_toggled.connect(test_player.set_mute)

        test_duration = 0.0

        def _on_test_duration(d: float) -> None:
            nonlocal test_duration
            test_duration = max(0.001, d)
            main_win.set_preview_time(0.0, test_duration)
            main_win.update_waveform_duration(test_duration)

        def _on_test_position(pos: float) -> None:
            if test_duration > 0:
                norm = min(1.0, max(0.0, pos / test_duration))
                main_win._waveform.set_playhead(norm)
            main_win.set_preview_time(pos, test_duration)

        def _on_test_stop() -> None:
            test_player.stop()
            main_win.set_preview_audio_playing(False)
            main_win._waveform.set_playhead(None)
            main_win.set_preview_time(0.0, test_duration)

        test_player.signals.duration_changed.connect(_on_test_duration)
        test_player.signals.position_changed.connect(_on_test_position)
        test_player.signals.eof_reached.connect(
            lambda: (
                main_win.set_preview_audio_playing(False),
                main_win._waveform.set_playhead(None),
                main_win.set_preview_time(0.0, test_duration),
            )
        )

        def _on_test_error(msg: str) -> None:
            logger.warning("[MAIN] Pre-Viz error notice: %s", msg)
            main_win._status_label.setText(f"Avviso Pre-Viz: {msg}")

        test_player.signals.error_occurred.connect(_on_test_error)

        def _on_preview_in_out(start: float, end) -> None:
            """Immediate seek to IN point when modifying in/out markers."""
            if test_player is not None:
                test_player.set_in_out(start, end, seek_to_start=True)
                main_win.set_preview_time(start, test_duration)

        main_win.preview_in_out_changed.connect(_on_preview_in_out)

        def _on_cue_preview_requested(cue) -> None:
            nonlocal test_duration
            try:
                test_duration = 0.0
                main_win.set_preview_time(0.0, 0.0)
                main_win.set_preview_audio_playing(False)
                if cue.media_type == MediaType.VIDEO:
                    # Load video paused at in_point so first frame appears in preview
                    main_win.show_preview_video(scale=cue.scale, crop=cue.crop)
                    test_player.load(cue.file_path, start=cue.in_point, end=cue.out_point, pause=True)
                    test_player.set_aspect_ratio(cue.aspect_ratio)
                    test_player.set_scale(cue.scale)
                    test_player.set_crop(cue.crop)
                elif cue.media_type == MediaType.AUDIO:
                    # Load audio paused at in_point to extract duration immediately
                    main_win.show_preview_audio()
                    test_player.load(cue.file_path, start=cue.in_point, end=cue.out_point, pause=True)
                elif cue.media_type == MediaType.IMAGE:
                    test_player.stop()
                    main_win._waveform.set_playhead(None)
            except Exception as exc:
                logger.error("[MAIN] Cue preview request failed: %s", exc)

        main_win.cue_preview_requested.connect(_on_cue_preview_requested)

        def _test_play_selected(mw: MainWindow, tp: TestPlayer) -> None:
            cue = mw._selected_cue()
            if cue is None:
                return
            if cue.media_type == MediaType.IMAGE:
                mw.show_preview_image(cue.file_path, scale=cue.scale, crop=cue.crop)
                return
            try:
                if cue.media_type == MediaType.VIDEO:
                    mw.show_preview_video(scale=cue.scale, crop=cue.crop)
                elif cue.media_type == MediaType.AUDIO:
                    mw.show_preview_audio()
                    mw.set_preview_audio_playing(True)

                # If paused, simply resume!
                if tp.is_paused() and not tp.is_idle():
                    tp.play()
                    return
                tp.load(cue.file_path, start=cue.in_point, end=cue.out_point)
                tp.set_aspect_ratio(cue.aspect_ratio)
                tp.set_scale(cue.scale)
                tp.set_crop(cue.crop)
                tp.set_loop(cue.loop)
                tp.play()
                logger.info("[MAIN] Preview playing: %s", cue.file_path)
            except Exception as exc:
                logger.error("[MAIN] Test play failed: %s", exc)

        main_win._btn_test_play.clicked.connect(
            lambda: _test_play_selected(main_win, test_player))
        main_win._btn_test_pause.clicked.connect(
            lambda: (test_player.pause(), main_win.set_preview_audio_playing(False)))
        main_win._btn_test_stop.clicked.connect(_on_test_stop)

    # ── Graceful shutdown on SIGINT / SIGTERM ──────────────────────────
    def _shutdown(*_args) -> None:
        logger.info("[MAIN] Shutdown signal received")
        main_win._force_closing = True
        if live_player is not None:
            live_player.shutdown()
        if test_player is not None:
            test_player.shutdown()
        output_win.force_close()
        main_win.close()
        app.quit()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Allow Python signal handlers to run while the Qt event loop blocks
    timer = QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)

    logger.info("═══ BlindCue v0.1 started (100% Native Wayland) ═══")

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
