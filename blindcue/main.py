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

    # ── Output window (Layer 0 + live rendering, bound after MainWindow) ─
    output_win = OutputWindow()

    # ── Live Native Wayland players (one independent player per Layer 1-3) ─
    live_players: dict[int, LivePlayer] = {}
    for layer in (1, 2, 3):
        try:
            live_players[layer] = LivePlayer(video_widget=output_win.get_video_widget(layer))
            logger.info("[MAIN] Live player L%d initialised", layer)
        except Exception as exc:
            logger.critical("[MAIN] Could not create live player L%d: %s", layer, exc)
            if layer == 1:
                QMessageBox.critical(
                    None, "BlindCue – Fatal Error",
                    f"Cannot initialise the live multimedia player:\n{exc}")

    # ── Main window (director panel) ALWAYS on primary monitor ────────
    main_win = MainWindow(output_window=output_win)
    main_win.bind_to_primary_screen(primary)
    main_win.show()

    # Attach OutputWindow strictly to target screen after MainWindow maps on primary
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

    # ── Connect GO signal to per-layer live engine ────────────────────
    active_live_cues: dict[int, Cue] = {}

    def _on_cue_fired(cue) -> None:
        """Handle GO: launch *cue* on cue.layer WITHOUT interrupting other layers."""
        layer = cue.layer if cue.layer in (1, 2, 3) else 1
        lp = live_players.get(layer)
        try:
            active_live_cues[layer] = cue
            target_vol = int(cue.volume * 100)

            if cue.media_type == MediaType.VIDEO:
                if lp is not None:
                    output_win.show_video_widget(
                        scale=cue.scale,
                        crop=cue.crop,
                        pos_x=cue.position_x,
                        pos_y=cue.position_y,
                        opacity=0.0 if cue.fade_in > 0 else cue.opacity,
                        layer=layer,
                        aspect_ratio=cue.aspect_ratio,
                    )
                    lp.load(
                        cue.file_path,
                        start=cue.in_point,
                        end=cue.out_point,
                    )
                    lp.set_aspect_ratio(cue.aspect_ratio)
                    lp.set_scale(cue.scale)
                    lp.set_crop(cue.crop)
                    lp.set_loop(cue.loop, cue.loop_count)

                    if cue.fade_in > 0:
                        lp.fade_in(target_vol, cue.fade_in)
                        output_win.fade_in_video(cue.fade_in, cue.opacity, layer=layer)
                    else:
                        lp.set_volume(target_vol)

                    lp.play()
                    logger.info("[MAIN] Video cue fired to live L%d: %s", layer, cue)

            elif cue.media_type == MediaType.AUDIO:
                if lp is not None:
                    # Clear visual elements ONLY on this target layer; other layers stay live!
                    output_win.clear_layer(layer)
                    lp.load(
                        cue.file_path,
                        start=cue.in_point,
                        end=cue.out_point,
                    )
                    lp.set_loop(cue.loop, cue.loop_count)

                    if cue.fade_in > 0:
                        lp.fade_in(target_vol, cue.fade_in)
                    else:
                        lp.set_volume(target_vol)

                    lp.play()
                    logger.info("[MAIN] Audio cue fired to live L%d: %s", layer, cue)

            elif cue.media_type == MediaType.IMAGE:
                # Replace ONLY content on this target layer; video/audio on other layers stay playing!
                if lp is not None:
                    lp.stop()
                output_win.show_image(
                    layer=layer,
                    file_path=cue.file_path,
                    opacity=0.0 if cue.fade_in > 0 else cue.opacity,
                    crop=cue.crop,
                    scale=cue.scale,
                    pos_x=cue.position_x,
                    pos_y=cue.position_y,
                    aspect_ratio=cue.aspect_ratio,
                )
                if cue.fade_in > 0:
                    output_win.fade_in_layer(layer, cue.fade_in, cue.opacity)
                logger.info("[MAIN] Image cue fired on Layer %d: %s", layer, cue)

                # Auto-removal if hold_time is set
                if cue.hold_time > 0:
                    def _clear_held_image(layer_idx=layer, target_cue=cue) -> None:
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
            logger.error("[MAIN] Error firing cue on L%d: %s", layer, exc, exc_info=True)
            output_win.clear_layer(layer)
            active_live_cues.pop(layer, None)

    main_win.cue_fired.connect(_on_cue_fired)

    # ── Handle per-layer EOF & Error cleanly ──────────────────────────
    def _on_live_eof(layer: int) -> None:
        """When media on *layer* reaches EOF, hide/clear ONLY *layer*."""
        try:
            if layer in live_players:
                live_players[layer].stop()
            output_win.hide_video_widget(layer=layer)
            c = active_live_cues.get(layer)
            if c and c.media_type in (MediaType.VIDEO, MediaType.AUDIO):
                active_live_cues.pop(layer, None)
                main_win._reset_live_label(layer)
                c.status = CueStatus.LOADED
                main_win._refresh_cue_list()
            logger.info("[MAIN] Live media finished on Layer %d (EOF) – layer cleared", layer)
        except Exception as exc:
            logger.error("[MAIN] Error on live L%d EOF: %s", layer, exc)

    def _on_live_error(layer: int, err_msg: str) -> None:
        """Per-layer failsafe recovery: clear failing layer (and reveal Tappo if no layers remain)."""
        logger.critical("[MAIN] LIVE PLAYBACK ERROR on Layer %d: %s", layer, err_msg)
        try:
            if layer in live_players:
                live_players[layer].stop()
            output_win.clear_layer(layer)
            c = active_live_cues.pop(layer, None)
            if c is not None:
                c.status = CueStatus.LOADED
            main_win._reset_live_label(layer)
            main_win._refresh_cue_list()
            main_win._status_label.setText(f"ATTENZIONE: Errore Live L{layer} ({err_msg})")
        except Exception as exc:
            logger.error("[MAIN] Error during live fallback recovery on L%d: %s", layer, exc)

    for layer, lp in live_players.items():
        lp.signals.eof_reached.connect(lambda l=layer: _on_live_eof(l))
        lp.signals.error_occurred.connect(lambda msg, l=layer: _on_live_error(l, msg))

    # ── Real-time Live Volume Adjustment ──────────────────────────────
    def _on_live_volume_changed(vol: int) -> None:
        """Adjust volume in real-time on the exact layer running the selected Live cue."""
        selected = main_win._selected_cue()
        if not selected:
            return
        for layer, c in active_live_cues.items():
            if c.cue_id == selected.cue_id and layer in live_players:
                live_players[layer].set_volume(vol)
                selected.volume = vol / 100.0
                logger.debug("[MAIN] Live L%d volume adjusted to %d%% for cue '%s'", layer, vol, selected.name)
                return
        if getattr(main_win, "_live_mirror_active", False) and selected.layer in live_players:
            live_players[selected.layer].set_volume(vol)

    main_win.live_volume_changed.connect(_on_live_volume_changed)

    # ── Connect Layer Clear and Blackout signals (with Micro-Fade) ─────
    def _on_layer_clear_requested(layer: int) -> None:
        """Clear media ONLY on *layer* with smooth fade without interrupting other layers."""
        try:
            cue = active_live_cues.get(layer)
            fade_time = max(0.2, cue.fade_out) if cue and cue.fade_out > 0 else 0.2
            lp = live_players.get(layer)

            def _clear_active_if_same(l_idx=layer, target_c=cue) -> None:
                if active_live_cues.get(l_idx) is target_c:
                    active_live_cues.pop(l_idx, None)

            if cue and cue.media_type == MediaType.VIDEO:
                if lp is not None:
                    lp.fade_out(fade_time, stop_after=True)
                output_win.fade_out_video(fade_time, callback=_clear_active_if_same, layer=layer)
            elif cue and cue.media_type == MediaType.AUDIO:
                if lp is not None:
                    lp.fade_out(fade_time, stop_after=True, callback=_clear_active_if_same)
                else:
                    _clear_active_if_same()
            elif cue and cue.media_type == MediaType.IMAGE:
                output_win.fade_out_layer(layer, fade_time, callback=_clear_active_if_same)
            else:
                output_win.clear_layer(layer)
                active_live_cues.pop(layer, None)
            logger.info("[MAIN] Layer %d cleared (fade %.2fs)", layer, fade_time)
        except Exception as exc:
            logger.error("[MAIN] Error clearing layer %d: %s", layer, exc)

    def _on_blackout_requested() -> None:
        """Master Blackout: micro-fade out ALL active layers and reveal Layer 0 (Tappo)."""
        try:
            for lp in live_players.values():
                lp.fade_out(0.2, stop_after=True)
            output_win.show_fallback(fade_duration_sec=0.2)
            active_live_cues.clear()
            logger.info("[MAIN] Master Blackout executed across all 3 layers (0.2s micro-fade)")
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
                    main_win.show_preview_video(
                        scale=cue.scale, crop=cue.crop,
                        pos_x=cue.position_x, pos_y=cue.position_y,
                        opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
                    )
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
                    main_win.show_preview_image(
                        cue.file_path, scale=cue.scale, crop=cue.crop,
                        pos_x=cue.position_x, pos_y=cue.position_y,
                        opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
                    )
                    main_win._waveform.set_playhead(None)
            except Exception as exc:
                logger.error("[MAIN] Cue preview request failed: %s", exc)

        main_win.cue_preview_requested.connect(_on_cue_preview_requested)

        def _test_play_selected(mw: MainWindow, tp: TestPlayer) -> None:
            cue = mw._selected_cue()
            if cue is None:
                return
            if cue.media_type == MediaType.IMAGE:
                mw.show_preview_image(
                    cue.file_path, scale=cue.scale, crop=cue.crop,
                    pos_x=cue.position_x, pos_y=cue.position_y,
                    opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
                )
                return
            try:
                if cue.media_type == MediaType.VIDEO:
                    mw.show_preview_video(
                        scale=cue.scale, crop=cue.crop,
                        pos_x=cue.position_x, pos_y=cue.position_y,
                        opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
                    )
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
                tp.set_loop(cue.loop, cue.loop_count)
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
        for lp in live_players.values():
            lp.shutdown()
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
