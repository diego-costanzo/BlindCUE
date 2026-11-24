"""The "Add audio" file window with listening before choosing (stage 5, item 5.12).

The program's own file window (not the Windows one: that cannot take a
button) with "▶ Listen" / "■ Stop" under the list: the highlighted sound
plays on the headphone output of the director when one is set (the
monitor device, as in the "Edit cue" window), never on a cue's player. The
sound stops when another file is highlighted and when the window closes.
"""

from __future__ import annotations

from pathlib import Path

from i18n import tr
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QWidget

AUDIO_EXT = {".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".wma", ".opus"}


class AudioPickDialog(QFileDialog):
    def __init__(self, parent: QWidget | None, title: str, folder: str, name_filter: str,
                 audio_device=None) -> None:
        super().__init__(parent, tr(title), folder, tr(name_filter))
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self.setFileMode(QFileDialog.FileMode.ExistingFile)
        self.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        self._current = ""
        self._player = QMediaPlayer(self)
        self._output = QAudioOutput(self)
        if audio_device is not None:
            self._output.setDevice(audio_device)
        self._player.setAudioOutput(self._output)
        self._player.mediaStatusChanged.connect(self._on_status)
        row = QWidget(self)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 4, 0, 0)
        self.btn_listen = QPushButton(tr("▶ Ascolta"))
        self.btn_listen.setToolTip(tr("Ascolta il suono selezionato prima di sceglierlo (in cuffia, se impostata)"))
        self.btn_listen.clicked.connect(self._listen)
        self.btn_stop = QPushButton(tr("■ Ferma"))
        self.btn_stop.clicked.connect(self.stop)
        self.lbl_status = QLabel("")
        lay.addWidget(self.btn_listen)
        lay.addWidget(self.btn_stop)
        lay.addWidget(self.lbl_status, 1)
        grid = self.layout()
        if grid is not None and hasattr(grid, "rowCount"):
            grid.addWidget(row, grid.rowCount(), 0, 1, -1)
        self.currentChanged.connect(self._on_current)
        self._on_current("")

    @staticmethod
    def is_audio(path: str) -> bool:
        return bool(path) and Path(path).suffix.lower() in AUDIO_EXT and Path(path).is_file()

    def _on_current(self, path: str) -> None:
        if path != self._current:
            self.stop()
        self._current = path
        self.btn_listen.setEnabled(self.is_audio(path))

    def _listen(self) -> None:
        if not self.is_audio(self._current):
            return
        self._player.setSource(QUrl.fromLocalFile(self._current))
        self._player.play()
        self.lbl_status.setText(f"▶ {Path(self._current).name}")

    def stop(self) -> None:
        if self._player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self._player.stop()
        self.lbl_status.setText("")

    def _on_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.lbl_status.setText("")
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.lbl_status.setText(tr("Non si riesce a leggere questo file"))

    def done(self, result: int) -> None:  # noqa: D102 - Qt override: never leave a sound playing
        self.stop()
        self._player.setSource(QUrl())
        super().done(result)


def pick_audio_file(parent: QWidget | None, title: str, folder: str, name_filter: str, audio_device=None) -> str:
    """The chosen sound file, or "" (cancelled)."""
    dlg = AudioPickDialog(parent, title, folder, name_filter, audio_device)
    try:
        if dlg.exec() == QFileDialog.DialogCode.Accepted and dlg.selectedFiles():
            return dlg.selectedFiles()[0]
        return ""
    finally:
        dlg.deleteLater()
