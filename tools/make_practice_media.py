"""Make the media of the practice show (stage 5, item 5.17) into blindcue/assets/practice/.

All of it is generated here (tones, noise, drawn pictures, a curtain made of
two coloured panels), so the files carry no one else's rights. Needs FFmpeg on
PATH (or build/ffmpeg) and PySide6.

usage: python tools/make_practice_media.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "blindcue" / "assets" / "practice"


def ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    local = ROOT / "build" / "ffmpeg" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if local.is_file():
        return str(local)
    raise SystemExit("ffmpeg not found")


def run(*args: str) -> None:
    subprocess.run([ffmpeg(), "-v", "error", "-y", *args], check=True)


def sounds() -> None:
    # Music: a soft C major chord that swells and fades (20 s).
    run("-f", "lavfi", "-i", "sine=f=261.63:d=20", "-f", "lavfi", "-i", "sine=f=329.63:d=20",
        "-f", "lavfi", "-i", "sine=f=392.00:d=20", "-f", "lavfi", "-i", "sine=f=523.25:d=20",
        "-filter_complex", "amix=inputs=4:normalize=1,volume=0.6,tremolo=f=0.25:d=0.3,"
                           "afade=t=in:d=3,afade=t=out:st=16:d=4",
        "-ac", "1", "-b:a", "64k", str(OUT / "music.mp3"))
    # Bell: two short tones (1.5 s).
    run("-f", "lavfi", "-i", "sine=f=880:d=1.5", "-f", "lavfi", "-i", "sine=f=1320:d=1.5",
        "-filter_complex", "amix=inputs=2,afade=t=out:st=0.1:d=1.4", "-ac", "1", "-b:a", "64k",
        str(OUT / "bell.mp3"))
    # Storm: brown noise that rises and falls (6 s).
    run("-f", "lavfi", "-i", "anoisesrc=color=brown:d=6:a=0.5",
        "-af", "lowpass=f=600,afade=t=in:d=1.5,afade=t=out:st=3.5:d=2.5", "-ac", "1", "-b:a", "64k",
        str(OUT / "storm.mp3"))


def curtain() -> None:
    # Two dark red panels open over a dark blue stage (6 s, 640x360).
    graph = ("[0][1]overlay=x='-min(t,5)*64':y=0[a];[a][2]overlay=x='320+min(t,5)*64':y=0,format=yuv420p")
    run("-f", "lavfi", "-i", "color=c=0x101830:s=640x360:d=6:r=25",
        "-f", "lavfi", "-i", "color=c=0x8b1010:s=320x360:d=6:r=25",
        "-f", "lavfi", "-i", "color=c=0x8b1010:s=320x360:d=6:r=25",
        "-filter_complex", graph, "-c:v", "libx264", "-preset", "slow", "-crf", "30", "-an",
        str(OUT / "curtain.mp4"))


def pictures() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPolygonF

    QGuiApplication.instance() or QGuiApplication([])
    w, h = 1280, 720

    def canvas(top: str, bottom: str) -> tuple[QImage, QPainter]:
        img = QImage(w, h, QImage.Format.Format_RGB32)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor(top))
        grad.setColorAt(1, QColor(bottom))
        p.fillRect(img.rect(), grad)
        return img, p

    # Forest: dark trees on a green dusk.
    img, p = canvas("#4b7a5a", "#14301e")
    p.setPen(Qt.PenStyle.NoPen)
    for i, (x, size, shade) in enumerate([(90, 260, "#0d2416"), (260, 330, "#103019"), (470, 280, "#0d2416"),
                                          (690, 360, "#0f2c18"), (930, 300, "#0d2416"), (1150, 340, "#103019")]):
        p.setBrush(QColor(shade))
        base = h - 40 - (i % 2) * 20
        p.drawPolygon(QPolygonF([QPointF(x, base - size), QPointF(x - size * 0.38, base), QPointF(x + size * 0.38, base)]))
        p.setBrush(QColor("#2a1a10"))
        p.drawRect(QRectF(x - 12, base, 24, 40))
    p.end()
    img.save(str(OUT / "forest.png"))

    # Castle: a grey silhouette on an evening sky.
    img, p = canvas("#2c3e70", "#c98d5a")
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#3b3f4a"))
    p.drawRect(QRectF(380, 330, 520, 330))
    for tx in (330, 830):
        p.drawRect(QRectF(tx, 220, 120, 440))
        for k in range(3):
            p.drawRect(QRectF(tx + k * 44, 196, 32, 30))
    for k in range(9):
        p.drawRect(QRectF(390 + k * 58, 306, 36, 30))
    p.setBrush(QColor("#1d2027"))
    p.drawRect(QRectF(590, 520, 100, 140))
    p.setBrush(QColor("#f2c14e"))
    for wx, wy in ((360, 300), (860, 300), (480, 420), (770, 420)):
        p.drawRect(QRectF(wx, wy, 26, 40))
    p.end()
    img.save(str(OUT / "castle.png"))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    sounds()
    curtain()
    pictures()
    for f in sorted(OUT.iterdir()):
        print(f"{f.name}: {f.stat().st_size // 1024} KB")
