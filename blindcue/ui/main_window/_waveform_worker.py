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
    def _request_waveform(self, cue: Cue) -> None:
        if cue.media_type == MediaType.IMAGE:
            self._waveform.set_peaks(np.array([]))
            return
        try:
            analyzer = WaveformAnalyzer(cue.file_path, max(3200, self._waveform.width() * 6))
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
        cue = self._selected_cue()
        if cue and os.path.abspath(cue.file_path) == os.path.abspath(path):
            if isinstance(peaks, np.ndarray):
                self._waveform.set_peaks(peaks)

    def _on_analyzer_failed(self, analyzer, path: str, msg: str) -> None:
        self._active_analyzers.discard(analyzer)
        logger.warning("Waveform error for %s: %s", path, msg)
        self._waveform.set_peaks(np.array([]))
