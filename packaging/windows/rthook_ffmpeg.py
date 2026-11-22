"""PyInstaller runtime hook: make the bundled FFmpeg visible to shutil.which()."""

import os
import sys

_base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
_ffmpeg_dir = os.path.join(_base, "ffmpeg")
if os.path.isdir(_ffmpeg_dir):
    os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
