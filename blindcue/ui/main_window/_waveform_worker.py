"""Waveform Background Worker mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _WaveformWorkerMixin:
    _WAVEFORM_CACHE_MAX = 32

    def _request_waveform(self, cue: Cue) -> None:
        # Group containers and broken/offline cues have no media of their own:
        # running ffprobe on an empty path only spams the log with decode
        # errors and wastes a worker slot on every selection.
        if cue.media_type in (MediaType.IMAGE, MediaType.GROUP) or not cue.file_path:
            self._waveform.set_peaks(np.array([]))
            return
        path = os.path.abspath(cue.file_path)
        cached = self._waveform_cache.get(path)
        if isinstance(cached, np.ndarray):
            self._waveform.set_peaks(cached)
            return
        if any(os.path.abspath(a.file_path) == path for a in self._active_analyzers):
            # Already decoding this exact file in the background.  One job per
            # selection change floods the worker pool (a GO storm queues
            # hundreds of full-file decodes) and the cue that is finally
            # selected would see its waveform only seconds later.
            return
        try:
            if not hasattr(self, "_peaks_cache_dir"):
                from engine import peaks_cache

                self._peaks_cache_dir = peaks_cache.default_dir()  # 3.4: waveforms kept on disk
            analyzer = WaveformAnalyzer(cue.file_path, max(3200, self._waveform.width() * 6),
                                        cache_dir=self._peaks_cache_dir)
            self._active_analyzers.add(analyzer)
            analyzer.signals.duration_ready.connect(
                lambda path, dur: self._on_analyzer_duration(path, dur)
            )
            analyzer.signals.finished.connect(
                lambda path, peaks, a=analyzer: self._on_analyzer_ready(a, path, peaks)
            )
            analyzer.signals.error.connect(
                lambda path, msg, a=analyzer: self._on_analyzer_failed(a, path, msg)
            )
            self._thread_pool.start(analyzer)
        except Exception as exc:
            logger.error("Waveform request failed: %s", exc)

    def _on_analyzer_duration(self, path: str, dur_sec: float) -> None:
        """Apply the ffprobe duration when Qt never reports it for this cue."""
        cue = self._selected_cue()
        if cue is None or os.path.abspath(cue.file_path) != os.path.abspath(path):
            return
        if cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO) or dur_sec <= 0:
            return
        self.set_known_duration(cue.file_path, dur_sec)
        if self._active_test_duration <= 0:
            self.update_waveform_duration(dur_sec)

    def _on_analyzer_ready(self, analyzer, path: str, peaks: object) -> None:
        self._active_analyzers.discard(analyzer)
        if isinstance(peaks, np.ndarray):
            self._cache_waveform(path, peaks)
            cue = self._selected_cue()
            if cue and os.path.abspath(cue.file_path) == os.path.abspath(path):
                self._waveform.set_peaks(peaks)

    def _cache_waveform(self, path: str, peaks: np.ndarray) -> None:
        """Keep the decoded peaks so re-selecting a cue does not re-decode it."""
        self._waveform_cache[os.path.abspath(path)] = peaks
        while len(self._waveform_cache) > self._WAVEFORM_CACHE_MAX:
            self._waveform_cache.pop(next(iter(self._waveform_cache)))

    def _on_analyzer_failed(self, analyzer, path: str, msg: str) -> None:
        self._active_analyzers.discard(analyzer)
        logger.warning("Waveform error for %s: %s", path, msg)
        cue = self._selected_cue()
        if cue is not None and cue.file_path and os.path.abspath(cue.file_path) == os.path.abspath(path):
            self._waveform.set_peaks(np.array([]))
