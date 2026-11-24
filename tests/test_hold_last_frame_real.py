"""Stage 4.4 with a real video: the paused deck still has its last frame.

The whole "hold the last frame" design rests on one fact of the Qt FFmpeg
backend: at EndOfMedia it clears the picture, but a deck paused shortly
before the end keeps the frame in its video sink. A silent 1.6 s video (blue,
then red for the last 0.6 s) plays to its end in a subprocess (offscreen, no
sound track); the frame taken at the end must be red, and the output must
show it as a still.

Needs ffmpeg (PATH or build/ffmpeg) to make the video, else skipped.

Run:
    QT_QPA_PLATFORM=offscreen pytest -q tests/test_hold_last_frame_real.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"


def _ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    local = ROOT / "build" / "ffmpeg" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    return str(local) if local.is_file() else None


_PLAY = '''
import faulthandler, os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, sys.argv[1])
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
from engine.player_live import LivePlayer
from ui.output_window import OutputWindow

out = OutputWindow()
out.resize(640, 360)
out.show()
lp = LivePlayer(video_widget=out.get_video_widget(1))
result = {}


def on_eof():
    img = lp.current_frame_image()
    result["frame"] = img is not None
    result["pos_ms"] = lp._deck_pair()[0].position()
    result["dur_ms"] = int(lp.duration_seconds() * 1000)
    if img is not None:
        c = img.pixelColor(img.width() // 2, img.height() // 2)
        result["rgb"] = (c.red(), c.green(), c.blue())
        result["held"] = out.hold_video_frame(1, img)
        result["still"] = out._image_containers[1].isVisible() and not out._video_containers[1].isVisible()
    lp.stop()
    QTimer.singleShot(200, app.quit)


def start():
    out.show_video_widget(layer=1)
    lp.load(sys.argv[2])
    lp.configure_automation(is_video=True)
    lp.set_hold_last_frame(True)
    lp.play()


lp.signals.eof_reached.connect(on_eof)
faulthandler.dump_traceback_later(40, exit=True)
QTimer.singleShot(50, start)
QTimer.singleShot(20000, app.quit)
app.exec()
print("RESULT", result)
'''


def test_the_last_frame_is_still_there_when_the_deck_pauses(tmp_path) -> None:
    ffmpeg = _ffmpeg()
    if ffmpeg is None:
        pytest.skip("ffmpeg not found (PATH or build/ffmpeg)")
    video = tmp_path / "blue_then_red.mp4"
    subprocess.run(
        [ffmpeg, "-v", "error", "-y",
         "-f", "lavfi", "-i", "color=c=blue:s=320x180:d=1:r=25",
         "-f", "lavfi", "-i", "color=c=red:s=320x180:d=0.6:r=25",
         "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]",
         "-c:v", "mpeg4", "-q:v", "3", "-an", str(video)],
        check=True, capture_output=True, timeout=60,
    )
    script = tmp_path / "play_and_hold.py"
    script.write_text(_PLAY, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(script), str(APP_DIR), str(video)],
                          capture_output=True, text=True, timeout=90)
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT")), "")
    assert line, proc.stdout + proc.stderr
    result = eval(line[len("RESULT "):])  # noqa: S307 - our own subprocess prints a dict literal
    assert result.get("frame"), result
    red, green, blue = result["rgb"]
    assert red > 150 and blue < 100, result          # the LAST picture (red), not a cleared one
    assert result["dur_ms"] - result["pos_ms"] < 600, result
    assert result.get("held") and result.get("still"), result
