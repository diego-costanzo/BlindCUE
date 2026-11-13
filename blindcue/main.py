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
import time
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
from engine.envelope import evaluate_cue_level
from engine.player_live import LivePlayer
from engine.player_test import TestPlayer
from engine.show_scheduler import ScheduledWindow, ShowScheduler
from models.cue import Cue, CueStatus, FollowMode, MediaType

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

    # ── Device & Hardware Routing Manager ─────────────────────────────
    from engine.device_manager import DeviceManager
    device_mgr = DeviceManager()
    device_mgr.register_live_players(list(live_players.values()))
    device_mgr.register_test_player(test_player)
    device_mgr.register_output_window(output_win)
    if output_screen is not None:
        device_mgr.set_target_screen(output_screen)
    main_win.set_device_manager(device_mgr)

    # ── Wire per-layer video deck swap + real-time opacity callbacks ──
    for layer, lp in live_players.items():
        lp.set_secondary_video_output(output_win.get_secondary_video_item(layer))
        lp.set_deck_switch_callback(lambda deck, l_idx=layer: output_win.activate_video_deck(l_idx, deck))
        lp.set_opacity_callback(lambda op, l_idx=layer: output_win.set_layer_opacity(l_idx, op))

    # ── Connect GO signal to per-layer live engine & Timing Scheduler ─
    active_live_cues: dict[int, Cue] = {}
    known_file_durations: dict[str, float] = {}
    layer_fire_gen: dict[int, int] = {1: 0, 2: 0, 3: 0}
    live_positions: dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0}
    live_image_envelopes: dict[int, dict] = {}
    live_img_timer = QTimer(main_win)
    live_img_timer.setInterval(33)
    scheduler = ShowScheduler(main_win)
    paused_layers_by_global: set[int] = set()

    def _apply_cue_automation(player, cue: Cue, *, hot: bool = False) -> None:
        kwargs = dict(
            base_volume=cue.volume,
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

    def _on_live_img_tick() -> None:
        if not live_image_envelopes:
            live_img_timer.stop()
            return
        now = time.monotonic()
        done_layers: list[int] = []
        for l_idx, entry in list(live_image_envelopes.items()):
            cue_item: Cue = entry["cue"]
            if active_live_cues.get(l_idx) is not cue_item:
                done_layers.append(l_idx)
                continue
            elapsed = max(0.0, now - entry["started"])
            if cue_item.hold_time > 0 and elapsed >= cue_item.hold_time:
                done_layers.append(l_idx)
                op_end = _eval_image_opacity(cue_item, cue_item.hold_time)
                output_win.set_layer_opacity(l_idx, op_end)
                _enter_post_delay_or_finalize(
                    cue_item, l_idx, layer_fire_gen.get(l_idx, 0)
                )
                logger.info("[MAIN] Image on Layer %d reached hold_time (%.1fs)", l_idx, cue_item.hold_time)
                continue

            op = _eval_image_opacity(cue_item, elapsed)
            output_win.set_layer_opacity(l_idx, op)
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

        for l_idx in done_layers:
            live_image_envelopes.pop(l_idx, None)
        if not live_image_envelopes:
            live_img_timer.stop()

    live_img_timer.timeout.connect(_on_live_img_tick)

    def _set_global_paused(paused: bool) -> None:
        """Freeze or resume all active live layers, timed image envelopes, and Pre/Post delays."""
        scheduler.set_paused(paused)
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
            for l_idx in (1, 2, 3):
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
            for l_idx in (1, 2, 3):
                if scheduler.pending_for_layer(l_idx) is not None:
                    main_win.set_live_layer_paused(l_idx, False)
            main_win.set_global_paused(False)
            logger.info("[MAIN] RIPRENDI TUTTO executed")

    def _finalize_cue_exit(cue: Cue, layer: int, *, expected_gen: Optional[int] = None) -> None:
        """Clear output layer after playback + optional post_delay and trigger AUTO_FOLLOW if enabled."""
        if expected_gen is not None and layer_fire_gen.get(layer) != expected_gen:
            return
        lp = live_players.get(layer)
        if lp is not None:
            lp.stop()
        output_win.clear_layer(layer)
        live_image_envelopes.pop(layer, None)
        if active_live_cues.get(layer) is cue:
            active_live_cues.pop(layer, None)
        paused_layers_by_global.discard(layer)
        main_win._reset_live_label(layer)
        main_win.finish_live_cue_status(cue)
        main_win.set_live_section_index(cue.cue_id, -1)

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

        if cue.follow_mode == FollowMode.AUTO_FOLLOW.value:
            main_win.trigger_auto_follow_from(cue)

    def _enter_post_delay_or_finalize(cue: Cue, layer: int, expected_gen: int) -> None:
        if layer_fire_gen.get(layer) != expected_gen:
            return
        post_d = max(0.0, float(getattr(cue, "post_delay", 0.0)))
        if post_d > 0.02:
            lp = live_players.get(layer)
            if lp is not None:
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

    def _launch_cue_now(cue: Cue, layer: int, expected_gen: int) -> None:
        """Start actual Audio/Video/Image playback/display for *cue* on *layer*."""
        if layer_fire_gen.get(layer) != expected_gen:
            return
        lp = live_players.get(layer)
        try:
            if cue.status != CueStatus.LIVE:
                main_win.promote_cue_to_live(cue)
            active_live_cues[layer] = cue
            known_dur = known_file_durations.get(cue.file_path, 0.0)
            if known_dur <= 0 and main_win._selected_cue() is cue and main_win._active_test_duration > 0:
                known_dur = main_win._active_test_duration
            live_durations[layer] = known_dur
            live_positions[layer] = max(0.0, cue.in_point)
            live_image_envelopes.pop(layer, None)

            if known_dur > 0 and cue.media_type in (MediaType.VIDEO, MediaType.AUDIO):
                s_sec, e_sec, inf_flag = _live_effective_bounds(cue, known_dur)
                main_win.update_live_layer_progress(
                    layer, s_sec, end_sec=e_sec, start_sec=s_sec, is_looping_inf=inf_flag
                )

            if cue.media_type == MediaType.VIDEO:
                if lp is not None:
                    init_op = 0.0 if cue.fade_in > 0 else (
                        cue.opacity_points[0][1] if cue.opacity_points else cue.opacity
                    )
                    output_win.show_video_widget(
                        scale=cue.scale,
                        crop=cue.crop,
                        pos_x=cue.position_x,
                        pos_y=cue.position_y,
                        opacity=init_op,
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
                    _apply_cue_automation(lp, cue, hot=False)
                    lp.set_loop(cue.loop, cue.loop_count)
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
                    _apply_cue_automation(lp, cue, hot=False)
                    lp.set_loop(cue.loop, cue.loop_count)
                    lp.play()
                    logger.info("[MAIN] Audio cue fired to live L%d: %s", layer, cue)

            elif cue.media_type == MediaType.IMAGE:
                # Replace ONLY content on this target layer; video/audio on other layers stay playing!
                if lp is not None:
                    lp.stop()
                init_op = _eval_image_opacity(cue, 0.0)
                output_win.show_image(
                    layer=layer,
                    file_path=cue.file_path,
                    opacity=init_op,
                    crop=cue.crop,
                    scale=cue.scale,
                    pos_x=cue.position_x,
                    pos_y=cue.position_y,
                    aspect_ratio=cue.aspect_ratio,
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

        except Exception as exc:
            logger.error("[MAIN] Error firing cue on L%d: %s", layer, exc, exc_info=True)
            live_image_envelopes.pop(layer, None)
            output_win.clear_layer(layer)
            active_live_cues.pop(layer, None)

    def _on_scheduler_tick(win: ScheduledWindow) -> None:
        if layer_fire_gen.get(win.layer) != win.generation:
            return
        main_win.update_live_layer_phase(win.layer, win.cue, win.phase, win.elapsed_sec, win.total_sec)
        rem = max(0.0, win.total_sec - win.elapsed_sec)
        main_win.set_cue_phase_badge(win.cue.cue_id, f"{win.phase} -{rem:.1f}s")

    def _on_scheduler_finished(win: ScheduledWindow) -> None:
        if layer_fire_gen.get(win.layer) != win.generation:
            return
        main_win.set_cue_phase_badge(win.cue.cue_id, "")
        if win.phase == "PRE":
            _launch_cue_now(win.cue, win.layer, win.generation)
        elif win.phase == "POST":
            _finalize_cue_exit(win.cue, win.layer, expected_gen=win.generation)

    scheduler.tick_updated.connect(_on_scheduler_tick)
    scheduler.window_finished.connect(_on_scheduler_finished)

    def _on_cue_fired(cue: Cue) -> None:
        """Handle GO: schedule Pre-Delay if set or immediately start cue on its target layer."""
        layer = cue.layer if cue.layer in (1, 2, 3) else 1
        if scheduler.is_paused():
            _set_global_paused(False)
        scheduler.cancel_layer(layer)
        cur_gen = layer_fire_gen.get(layer, 0) + 1
        layer_fire_gen[layer] = cur_gen
        paused_layers_by_global.discard(layer)

        pre_d = max(0.0, float(getattr(cue, "pre_delay", 0.0)))
        if pre_d > 0.02:
            main_win.set_cue_phase_badge(cue.cue_id, f"PRE -{pre_d:.1f}s")
            main_win.update_live_layer_phase(layer, cue, "PRE", 0.0, pre_d)
            scheduler.schedule("PRE", cue, layer, pre_d, generation=cur_gen)
            logger.info("[MAIN] Cue '%s' scheduled with Pre-Delay %.2fs on Layer %d", cue.name, pre_d, layer)
        else:
            _launch_cue_now(cue, layer, cur_gen)

    main_win.cue_fired.connect(_on_cue_fired)

    # ── Handle per-layer EOF & Error cleanly ──────────────────────────
    def _on_live_eof(layer: int) -> None:
        """When media on *layer* reaches EOF, enter Post-Delay or clean up immediately."""
        try:
            c = active_live_cues.get(layer)
            gen = layer_fire_gen.get(layer, 0)
            if c and c.media_type in (MediaType.VIDEO, MediaType.AUDIO):
                _enter_post_delay_or_finalize(c, layer, gen)
            else:
                if layer in live_players:
                    live_players[layer].stop()
                output_win.hide_video_widget(layer=layer)
            logger.info("[MAIN] Live media finished on Layer %d (EOF)", layer)
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

    live_durations: dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0}
    preview_manual_position = False

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

    def _on_live_duration(layer: int, dur_sec: float) -> None:
        live_durations[layer] = max(0.001, dur_sec)
        live_cue = active_live_cues.get(layer)
        if live_cue is not None:
            known_file_durations[live_cue.file_path] = live_durations[layer]
            main_win.set_known_duration(live_cue.file_path, live_durations[layer])
            if live_cue.media_type in (MediaType.VIDEO, MediaType.AUDIO):
                start_sec, eff_end, is_inf = _live_effective_bounds(live_cue, live_durations[layer])
                cur_pos = max(start_sec, live_positions.get(layer, start_sec))
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
            if active_c.cue_id == cue.cue_id:
                if cue.media_type in (MediaType.VIDEO, MediaType.AUDIO) and l_idx in live_players:
                    _apply_cue_automation(live_players[l_idx], cue, hot=True)
                elif cue.media_type == MediaType.IMAGE and l_idx not in live_image_envelopes:
                    output_win.set_layer_opacity(l_idx, cue.opacity)

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
            for ph in ("PRE", "POST"):
                pw = scheduler.pending_for_layer(layer, ph)
                if pw is not None:
                    main_win.set_cue_phase_badge(pw.cue.cue_id, "")
            scheduler.cancel_layer(layer)
            cue = active_live_cues.get(layer)
            layer_fire_gen[layer] = layer_fire_gen.get(layer, 0) + 1
            clear_gen = layer_fire_gen[layer]
            paused_layers_by_global.discard(layer)
            fade_time = max(0.2, cue.fade_out) if cue and cue.fade_out > 0 else 0.2
            lp = live_players.get(layer)

            def _clear_active_if_same(l_idx=layer, expected_gen=clear_gen) -> None:
                if layer_fire_gen.get(l_idx) == expected_gen:
                    active_live_cues.pop(l_idx, None)
                    live_durations[l_idx] = 0.0
                    live_positions[l_idx] = 0.0

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
                live_image_envelopes.pop(layer, None)
                output_win.fade_out_layer(layer, fade_time, callback=_clear_active_if_same)
            else:
                live_image_envelopes.pop(layer, None)
                output_win.clear_layer(layer)
                active_live_cues.pop(layer, None)
            logger.info("[MAIN] Layer %d cleared (fade %.2fs)", layer, fade_time)
        except Exception as exc:
            logger.error("[MAIN] Error clearing layer %d: %s", layer, exc)

    def _on_blackout_requested() -> None:
        """Master Blackout: micro-fade out ALL active layers and reveal Layer 0 (Tappo)."""
        try:
            scheduler.cancel_all()
            scheduler.set_paused(False)
            paused_layers_by_global.clear()
            main_win.set_global_paused(False)
            live_image_envelopes.clear()
            live_img_timer.stop()
            for l_idx in (1, 2, 3):
                layer_fire_gen[l_idx] = layer_fire_gen.get(l_idx, 0) + 1
                live_durations[l_idx] = 0.0
                live_positions[l_idx] = 0.0
            for lp in live_players.values():
                lp.fade_out(0.2, stop_after=True)
            output_win.show_fallback(fade_duration_sec=0.2)
            active_live_cues.clear()
            logger.info("[MAIN] Master Blackout executed across all 3 layers (0.2s micro-fade)")
        except Exception as exc:
            logger.error("[MAIN] Error executing blackout: %s", exc)

    def _on_panic_requested() -> None:
        """Immediate 0ms PANIC hard stop across every player, timer, and output layer."""
        try:
            scheduler.cancel_all()
            scheduler.set_paused(False)
            paused_layers_by_global.clear()
            live_image_envelopes.clear()
            live_img_timer.stop()
            for l_idx in (1, 2, 3):
                layer_fire_gen[l_idx] = layer_fire_gen.get(l_idx, 0) + 1
                live_durations[l_idx] = 0.0
                live_positions[l_idx] = 0.0
            for lp in live_players.values():
                lp.stop()
            active_live_cues.clear()
            logger.warning("[MAIN] 0ms PANIC STOP ALL completed")
        except Exception as exc:
            logger.error("[MAIN] Error executing PANIC: %s", exc)

    main_win.layer_clear_requested.connect(_on_layer_clear_requested)
    main_win.blackout_requested.connect(_on_blackout_requested)
    main_win.panic_requested.connect(_on_panic_requested)
    main_win.pause_all_toggled.connect(lambda: _set_global_paused(not scheduler.is_paused()))

    def _on_layer_play_pause_requested(layer: int) -> None:
        """Toggle rehearsal pause/resume for active Audio/Video live layer."""
        live_cue = active_live_cues.get(layer)
        lp = live_players.get(layer)
        if live_cue is None or lp is None or live_cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return
        if lp.is_playing():
            lp.pause()
            main_win.set_live_layer_paused(layer, True)
            logger.info("[MAIN] Live Layer %d paused (rehearsal toggle)", layer)
        else:
            lp.play()
            main_win.set_live_layer_paused(layer, False)
            logger.info("[MAIN] Live Layer %d resumed (rehearsal toggle)", layer)

    main_win.layer_play_pause_requested.connect(_on_layer_play_pause_requested)

    def _on_layer_seek_requested(layer: int, position_sec: float) -> None:
        """Seek active Audio/Video live player to position_sec (rehearsal scrub & skip)."""
        live_cue = active_live_cues.get(layer)
        lp = live_players.get(layer)
        if live_cue is None or lp is None or live_cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return
        dur = live_durations.get(layer, 0.0)
        if dur <= 0 and lp.duration_seconds() > 0:
            dur = lp.duration_seconds()
            live_durations[layer] = dur
        start_sec, eff_end, is_inf = _live_effective_bounds(live_cue, dur if dur > 0 else 999999.0)
        target = max(start_sec, min(eff_end, position_sec))
        lp.seek(target)
        live_positions[layer] = target
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
                    output_win.set_layer_opacity(sel.layer, op)

        test_player.set_opacity_callback(_on_test_video_opacity)

        test_duration = 0.0

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
                    output_win.set_layer_opacity(cue.layer, cue.opacity)

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
                if cue.media_type == MediaType.VIDEO:
                    # Load video paused at in_point so first frame appears in preview
                    main_win.show_preview_video(
                        scale=cue.scale, crop=cue.crop,
                        pos_x=cue.position_x, pos_y=cue.position_y,
                        opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
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
                    )
                    dur_img = cue.hold_time if cue.hold_time > 0 else cue.image_timeline_sec
                    main_win.set_preview_time(0.0, dur_img)
            except Exception as exc:
                logger.error("[MAIN] Cue preview request failed: %s", exc)

        main_win.cue_preview_requested.connect(_on_cue_preview_requested)

        def _test_play_selected(mw: MainWindow, tp: TestPlayer) -> None:
            nonlocal preview_manual_position
            cue = mw._selected_cue()
            if cue is None:
                return
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

    # ── Graceful shutdown on SIGINT / SIGTERM ──────────────────────────
    def _shutdown(*_args) -> None:
        logger.info("[MAIN] Shutdown signal received")
        scheduler.cancel_all()
        live_img_timer.stop()
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
