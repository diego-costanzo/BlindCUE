"""Stage 3, item 3.3: how a playlist plays (mixin for MainWindow).

The order of each playlist while the show runs (random order with a gap,
"go on after the last track", a loop) lives here, in a ``PlaylistRun`` per
playlist (``engine.playlist_flow``); ``main.py`` asks for the next track
when one ends or when a transition starts it early, and for the transition
of a playlist. The settings card in the inspector writes the playlist
fields of the scene (one undo step).
"""

from __future__ import annotations

import random

from engine import playlist_flow
from engine.playlist_flow import PlaylistRun
from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405


class _PlaylistMixin:
    def _playlist_setup(self) -> None:
        self._playlist_runs: dict[int, PlaylistRun] = {}
        self._playlist_rng = random.Random()  # a music shuffle, not security
        self._playlist_norm: dict | None = None  # a "same loudness" job: group id, tracks still measured
        box = getattr(self._inspector, "playlist_box", None)
        if box is not None:
            box.changed.connect(self._on_playlist_settings_changed)
            box.normalize_requested.connect(self._on_normalize_playlist)

    # ── Which playlist, which tracks ─────────────────────────────────
    def _playlist_group(self, cue: Cue | None) -> Cue | None:
        """The playlist *cue* is a track of (a scene "one after another" made as a playlist), or None."""
        if cue is None:
            return None
        parent = ShowEngine.group_parent(self._cues, cue)
        if parent is None or not getattr(parent, "playlist", False):
            return None
        return parent if getattr(parent, "group_mode", "") == GroupMode.SEQUENCE.value else None

    def _playlist_ids(self, group: Cue) -> list[int]:
        return [c.cue_id for c in ShowEngine.children_of(self._cues, group.cue_id)]

    def _playlist_opts(self, group: Cue) -> dict:
        return {"loop": bool(getattr(group, "playlist_loop", False)),
                "shuffle": bool(getattr(group, "playlist_shuffle", False)),
                "gap": int(getattr(group, "playlist_shuffle_gap", playlist_flow.DEFAULT_SHUFFLE_GAP)),
                "rng": self._playlist_rng}

    def _playlist_run(self, group: Cue) -> PlaylistRun:
        run = self._playlist_runs.get(group.cue_id)
        if run is None:
            run = self._playlist_runs[group.cue_id] = PlaylistRun()
        return run

    def _row_of_id(self, cue_id: int | None) -> int:
        return next((i for i, c in enumerate(self._cues) if c.cue_id == cue_id), -1)

    # ── The run ──────────────────────────────────────────────────────
    def _playlist_first(self, group: Cue, children: list[Cue]) -> Cue:
        """A GO on the playlist: the track it starts (the first, a random one, or the one after the last)."""
        opts = self._playlist_opts(group)
        run, first = playlist_flow.begin(
            self._playlist_runs.get(group.cue_id), [c.cue_id for c in children], shuffle=opts["shuffle"],
            gap=opts["gap"], remember=bool(getattr(group, "playlist_remember", False)), rng=opts["rng"])
        self._playlist_runs[group.cue_id] = run
        return next((c for c in children if c.cue_id == first), children[0])

    def _playlist_note_started(self, cue: Cue) -> None:
        """A track started (by its playlist, or by hand on its row): the position follows it."""
        group = self._playlist_group(cue)
        if group is not None:
            playlist_flow.note_started(self._playlist_run(group), cue.cue_id, self._playlist_ids(group))

    def playlist_next_row(self, finished: Cue) -> int | None:
        """The row of the track that follows *finished* (-1: the playlist ends; None: not a playlist track)."""
        group = self._playlist_group(finished)
        if group is None:
            return None
        run = self._playlist_run(group)
        ids = self._playlist_ids(group)
        if run.current() is None and finished.cue_id in ids:
            playlist_flow.note_started(run, finished.cue_id, ids)  # a run from before (e.g. an undo)
        opts = self._playlist_opts(group)
        nxt = playlist_flow.advance(run, finished.cue_id, ids, loop=opts["loop"], shuffle=opts["shuffle"],
                                    gap=opts["gap"], rng=opts["rng"])
        return self._row_of_id(nxt) if nxt is not None else -1

    def playlist_peek_next(self, cue: Cue | None) -> Cue | None:
        """The track that will follow *cue* in its playlist, or None (not a track, or the playlist ends)."""
        group = self._playlist_group(cue)
        if group is None:
            return None
        run = self._playlist_run(group)
        ids = self._playlist_ids(group)
        if cue.cue_id not in run.order:
            playlist_flow.sync(run, ids)  # list order for tracks the run has not seen (no position change)
        opts = self._playlist_opts(group)
        nxt = playlist_flow.peek_next(run, cue.cue_id, ids, loop=opts["loop"], shuffle=opts["shuffle"],
                                      gap=opts["gap"], rng=opts["rng"])
        row = self._row_of_id(nxt)
        return self._cues[row] if row >= 0 else None

    def playlist_hands_over(self, cue: Cue) -> bool | None:
        """Does the end of *cue* start another track? None: *cue* is not a playlist track."""
        if self._playlist_group(cue) is None:
            return None
        return self.playlist_peek_next(cue) is not None

    def playlist_transition(self, cue: Cue | None) -> tuple[str, float]:
        """(transition, its seconds) between the tracks of *cue*'s playlist; ("none", 0) otherwise."""
        group = self._playlist_group(cue)
        if group is None:
            return playlist_flow.NONE, 0.0
        return (playlist_flow.normalize_transition(getattr(group, "playlist_transition", playlist_flow.NONE)),
                float(getattr(group, "playlist_transition_sec", 0.0) or 0.0))

    def playlist_gap_after(self, cue: Cue) -> float:
        """Seconds of silence after *cue* before the next track ("pause" transition), else 0."""
        mode, seconds = self.playlist_transition(cue)
        if mode != playlist_flow.GAP or cue.cue_id in self._held_auto_go:
            return 0.0
        return playlist_flow.gap_seconds(mode, seconds) if self.playlist_peek_next(cue) is not None else 0.0

    def playlist_lead(self, cue: Cue) -> tuple[str, float, Cue] | None:
        """(transition, seconds, next track) of a playing track whose next track follows by itself."""
        group = self._playlist_group(cue)
        if group is None or cue.cue_id in self._held_auto_go:
            return None
        nxt = self.playlist_peek_next(cue)
        if nxt is None:
            return None
        mode, seconds = self.playlist_transition(cue)
        return mode, seconds, nxt

    def playlist_skip_to_next(self, cue: Cue) -> bool:
        """3.3 wake "from the next track": start the track after *cue* now. False: there is none."""
        row = self.playlist_next_row(cue)
        if row is None or row < 0:
            return False
        self._undo_auto_source = cue.cue_id
        try:
            self._fire_cue_chain(row, auto=True)
        finally:
            self._undo_auto_source = None
        return True

    # ── Settings (inspector card) ────────────────────────────────────
    @Slot(dict)
    def _on_playlist_settings_changed(self, values: dict) -> None:
        group = self._selected_cue()
        box = self._inspector.playlist_box
        if group is None or not getattr(group, "playlist", False) or len(self._selected_rows()) != 1:
            return
        if not self._change_allowed(EDIT_CUE):
            box.load(group)
            return
        changed = False
        for key, value in values.items():
            if getattr(group, key, None) != value:
                setattr(group, key, value)
                changed = True
        if not changed:
            return
        self._schedule_undo_point()
        self._mark_modified(True)
        self._status_label.setText(tr("Playlist '{}' aggiornata").format(group.name))

    # ── Same loudness for the whole playlist ─────────────────────────
    def _playlist_tracks_with_files(self, group: Cue) -> list[Cue]:
        return [c for c in ShowEngine.children_of(self._cues, group.cue_id)
                if c.media_type in (MediaType.AUDIO, MediaType.VIDEO) and c.file_path and os.path.isfile(c.file_path)]

    @Slot()
    def _on_normalize_playlist(self) -> None:
        """Measure the tracks not measured yet (in the background), then one loudness for all of them."""
        group = self._selected_cue()
        if group is None or not getattr(group, "playlist", False) or not self._change_allowed(EDIT_CUE):
            return
        tracks = self._playlist_tracks_with_files(group)
        if not tracks:
            self._status_label.setText(tr("Nessun brano con il suo file in questa playlist"))
            return
        todo = [t for t in tracks if t.loudness_lufs is None]
        self._playlist_norm = {"group": group.cue_id, "left": {t.cue_id for t in todo}}
        if not todo:
            self._finish_playlist_normalize()
            return
        self._status_label.setText(tr("Misuro il volume percepito di {} brani…").format(len(todo)))
        for track in todo:
            scanner = LoudnessScanner(track.file_path, target_lufs=playlist_flow.TARGET_LUFS)
            scanner.signals.finished.connect(
                lambda path, lufs, peak, _gain, cid=track.cue_id: self._on_playlist_track_measured(cid, path, lufs, peak))
            scanner.signals.error.connect(
                lambda path, _err, cid=track.cue_id: self._on_playlist_track_measured(cid, path, None, None))
            self._thread_pool.start(scanner)

    def _on_playlist_track_measured(self, cue_id: int, path: str, lufs: float | None, peak: float | None) -> None:
        job = self._playlist_norm
        if job is None or cue_id not in job["left"]:
            return
        job["left"].discard(cue_id)
        cue = next((c for c in self._cues if c.cue_id == cue_id), None)
        if cue is not None and lufs is not None and os.path.abspath(cue.file_path or "") == os.path.abspath(path):
            cue.loudness_lufs, cue.true_peak_dbfs = lufs, peak
        if not job["left"]:
            self._finish_playlist_normalize()

    def _finish_playlist_normalize(self) -> None:
        job, self._playlist_norm = self._playlist_norm, None
        group = next((c for c in self._cues if job is not None and c.cue_id == job["group"]), None)
        if group is None:
            return
        tracks = [t for t in self._playlist_tracks_with_files(group) if t.loudness_lufs is not None]
        if not tracks:
            self._status_label.setText(tr("Volume percepito non misurabile: nessun brano analizzato"))
            return
        result = playlist_flow.normalize_gains([(float(t.loudness_lufs), float(t.volume)) for t in tracks])
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        for track, gain in zip(tracks, result.gains_db, strict=True):
            track.auto_gain_db = gain
            track.normalize_audio = True
        self._commit_undo_point()
        self._mark_modified(True)
        for track in tracks:
            self.live_automation_updated.emit(track)
        missing = len(self._playlist_tracks_with_files(group)) - len(tracks)
        text = tr("Playlist '{}': {} brani allo stesso volume percepito ({} LUFS)").format(
            group.name, len(tracks), f"{result.target_lufs:.1f}")
        if result.limited:
            text += " · " + tr("più basso di -16: il brano più debole non può suonare più forte")
        if missing:
            text += " · " + tr("non misurati: {}").format(missing)
        self._status_label.setText(text)
