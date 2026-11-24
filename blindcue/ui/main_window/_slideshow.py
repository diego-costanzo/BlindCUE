"""Photos to music (stage 4, item 4.3) mixin for MainWindow.

Select several pictures and one sound, right-click → "Photos to this music":
the sound starts together with a folded playlist scene of the pictures; each
picture is shown for the time the music really plays (IN/OUT, tempo)
divided by their number; each picture crossfades into the next one (the
next one starts that much before the end of the previous one, evaluation
#14), the first fades in and the last fades out. All pictures go to one
layer, the music to another one. The scene stops after the last picture
and GO goes on after it.
"""

from __future__ import annotations

from i18n import tr
from PySide6.QtWidgets import QInputDialog

from ui.main_window._common import *  # noqa: F403,F401,F405

FADE_SEC = 0.5
XFADE_SEC = 1.0


def slideshow_holds(count: int, music_sec: float, xfade: float = 0.0) -> float:
    """Seconds each of *count* pictures is shown so that they fill *music_sec* (0.1 s steps,
    as the inspector keeps them; at least a second). With a crossfade the pictures overlap
    by *xfade*, so each one is shown that much longer."""
    count = max(1, count)
    return round(max(1.0, (music_sec + (count - 1) * max(0.0, xfade)) / count), 1)


def slideshow_crossfade(count: int, music_sec: float) -> float:
    """The crossfade between the pictures: XFADE_SEC, never more than half of a picture's time."""
    return round(min(XFADE_SEC, max(1.0, music_sec / max(1, count)) / 2.0), 1)


def music_play_seconds(cue: Cue, file_sec: float) -> float | None:
    """How long *cue* really plays: IN/OUT and tempo; None for loops and sections (no fixed length)."""
    if cue.loop or cue.sections or file_sec <= 0:
        return None
    start = max(0.0, cue.in_point)
    end = min(file_sec, cue.out_point) if cue.out_point and cue.out_point > start else file_sec
    return max(0.0, end - start) / max(0.5, float(getattr(cue, "playback_rate", 1.0)))


class _SlideshowMixin:
    def _slideshow_setup(self) -> None:
        self._cue_list.slideshow_requested.connect(self._make_slideshow)
        self._cue_list.crossfade_selected_requested.connect(self._crossfade_selected)

    def _media_length(self, path: str) -> float | None:
        known = self._known_file_durations.get(path)
        if known:
            return float(known)
        try:
            from engine.audio_analyzer import WaveformAnalyzer

            sec = WaveformAnalyzer(path)._get_duration()
        except Exception:  # noqa: BLE001 - no length: the operator is told below
            sec = None
        if sec:
            self._known_file_durations[path] = sec
        return sec

    def _make_slideshow(self) -> None:
        from engine.show_mode import EDIT_LIST

        rows = sorted(self._selected_rows())
        chosen = [self._cues[r] for r in rows]
        pictures = [c for c in chosen if c.media_type == MediaType.IMAGE]
        sounds = [c for c in chosen if c.media_type == MediaType.AUDIO]
        if len(pictures) < 2 or len(sounds) != 1 or len(pictures) + 1 != len(chosen):
            self._status_label.setText(tr("Foto con musica: seleziona almeno due immagini e un solo audio"))
            return
        if any(c.parent_id is not None for c in chosen):
            self._status_label.setText(tr("Foto con musica: non dentro una scena"))
            return
        if not self._change_allowed(EDIT_LIST):
            return
        music = sounds[0]
        file_sec = self._media_length(music.file_path)
        if not file_sec:
            self._status_label.setText(tr("Foto con musica: durata di '{}' sconosciuta").format(music.name))
            return
        length = music_play_seconds(music, file_sec)
        if not length:
            self._status_label.setText(tr("Foto con musica: '{}' ha un loop o sezioni").format(music.name))
            return
        if len(pictures) > length:
            self._status_label.setText(tr("Foto con musica: troppe immagini (almeno 1 s ciascuna)"))
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        xfade = slideshow_crossfade(len(pictures), length)
        hold = slideshow_holds(len(pictures), length, xfade)
        at = rows[0]
        rest = [c for c in self._cues if c not in chosen]
        group = Cue(name=tr("Foto: {}").format(music.name), file_path="", media_type=MediaType.GROUP,
                    group_mode=GroupMode.SEQUENCE.value, color="#a855f7", layer=1, collapsed=True,
                    status=CueStatus.LOADED)
        group.playlist = True  # stops after the last picture; GO goes on after the scene
        music.follow_mode = FollowMode.SIMULTANEOUS.value  # the music starts together with the pictures
        layer, output = pictures[0].layer, pictures[0].output_target
        group.layer, group.output_target = layer, output
        if music.layer == layer and music.output_target == output:
            music.layer = next(n for n in (2, 3, 1) if n != layer)  # a picture would stop the music
        for pic in pictures:
            pic.parent_id = group.cue_id
            pic.layer, pic.output_target = layer, output
            pic.hold_time = hold
            pic.pre_delay = pic.post_delay = 0.0
            pic.follow_mode = FollowMode.MANUAL.value  # the scene moves on by itself
            first, last = pic is pictures[0], pic is pictures[-1]
            pic.fade_in = FADE_SEC if first else 0.0       # with a crossfade the fade in stays 0
            pic.fade_out = FADE_SEC if last else 0.0
            pic.crossfade = 0.0 if first else xfade
        before = at  # nothing chosen lies above the first chosen row
        self._cues = rest[:before] + [music, group] + pictures + rest[before:]
        self._refresh_cue_list(keep_selection=False)
        self._cue_list.setCurrentRow(before)
        self._commit_undo_point()
        self._mark_modified(True)
        self._auto_save()
        self._status_label.setText(tr("Foto con musica: {} immagini da {} s su '{}' ({} s)").format(
            len(pictures), f"{hold:.1f}", music.name, f"{length:.0f}"))
        logger.info("[SLIDESHOW] %d pictures x %.2fs on '%s' (%.1fs), crossfade %.1fs", len(pictures), hold,
                    music.name, length, xfade)

    def _crossfade_selected(self) -> None:
        """Row menu → "Crossfade for the selected…": one crossfade time for all selected pictures (#14)."""
        from engine.show_mode import EDIT_CUE

        pictures = [self._cues[r] for r in sorted(self._selected_rows())
                    if self._cues[r].media_type == MediaType.IMAGE]
        if not pictures:
            self._status_label.setText(tr("Dissolvenza incrociata: seleziona almeno un'immagine"))
            return
        if not self._change_allowed(EDIT_CUE):
            return
        seconds, ok = QInputDialog.getDouble(
            self, tr("Dissolvenza incrociata"), tr("Secondi di dissolvenza incrociata (0 = taglio):"),
            max(1.0, float(pictures[0].crossfade or 0.0)), 0.0, 10.0, 1)
        if not ok:
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        for pic in pictures:
            pic.crossfade = round(seconds, 1)
            if seconds > 0:
                pic.fade_in = 0.0   # the crossfade brings the picture in
        self._commit_undo_point()
        self._mark_modified(True)
        self._last_selection_sig = None
        self._sync_selection_state()
        self._auto_save()
        self._status_label.setText(tr("Dissolvenza incrociata di {} s su {} immagini").format(
            f"{seconds:.1f}", len(pictures)))
