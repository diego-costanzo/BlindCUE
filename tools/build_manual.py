"""Build the user manuals (IT / EN / PL) from docs/manual/manual_<lang>.src.html.

    python tools/build_manual.py          # writes blindcue/help/manual_<lang>.html

Blocks marked <!--IF:feature--> / <!--IFNOT:feature--> are kept or dropped
depending on what the code contains (see tools/manual_features.py).
{{APP}} and {{VERSION}} come from blindcue/version.py (empty version if the
file is missing), {{STYLE}} is the shared style sheet and {{CREDITS}} the
optional docs/manual/credits_<lang>.html. <img src="img/<lang>/x.png"
width="W"> gets its height from the real image, so take the screenshots
first (tools/manual_screenshots.py).
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manual_features import FEATURES, ROOT, present  # noqa: E402

SRC_DIR = ROOT / "docs" / "manual"
HELP_DIR = ROOT / "blindcue" / "help"
LANGS = ("it", "en", "pl")

STYLE = """<style>
body { font-family: "Segoe UI", sans-serif; font-size: 14px; }
li { margin-bottom: 4px; }
h1 { font-size: 26px; color: #38bdf8; }
h2 { font-size: 20px; color: #38bdf8; margin-top: 28px; border-bottom: 1px solid #334155; }
h3 { font-size: 16px; color: #fbbf24; margin-top: 18px; }
code, kbd { font-family: Consolas, monospace; background-color: #1e293b; color: #e2e8f0; }
table.k td { padding: 3px 10px; border-bottom: 1px solid #334155; }
.tip { background-color: #0f2a1f; color: #bbf7d0; padding: 6px; }
.warn { background-color: #3a1d0b; color: #fed7aa; padding: 6px; }
img { border: 1px solid #334155; }
a { color: #7dd3fc; }
</style>"""


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", head[16:24])


def app_name_and_version() -> tuple[str, str]:
    sys.path.insert(0, str(ROOT / "blindcue"))
    try:
        from version import APP_NAME, APP_VERSION
    except ImportError:
        return "BlindCUE", ""
    return APP_NAME, APP_VERSION


def build(text: str, lang: str, features: set[str], help_dir: Path, app: str, version: str) -> str:
    for name in FEATURES:
        keep, drop = ("IF", "IFNOT") if name in features else ("IFNOT", "IF")
        text = re.sub(rf"<!--{drop}:{name}-->.*?<!--/{drop}:{name}-->", "", text, flags=re.DOTALL)
        text = text.replace(f"<!--{keep}:{name}-->", "").replace(f"<!--/{keep}:{name}-->", "")
    credits_file = SRC_DIR / f"credits_{lang}.html"
    credits = credits_file.read_text(encoding="utf-8").strip() if credits_file.is_file() else ""
    text = text.replace("{{CREDITS}}", f" {credits}" if credits else "")
    text = text.replace("{{STYLE}}", STYLE).replace("{{APP}}", app).replace("{{VERSION}}", version)

    missing: list[str] = []

    def sized(match: re.Match[str]) -> str:
        src, width = match.group(1), int(match.group(2))
        img = help_dir / src
        if not img.is_file():
            missing.append(src)
            return match.group(0)
        w, h = png_size(img)
        return f'<img src="{src}" width="{width}" height="{round(width * h / w)}">'

    text = re.sub(r'<img src="([^"]+)" width="(\d+)">', sized, text)
    if missing:
        # Usually a feature was just merged: its section is in, its pictures not yet.
        raise SystemExit(
            f"Missing screenshots for '{lang}': {', '.join(missing)}\n"
            f"Take them first: python tools/manual_screenshots.py blindcue "
            f"blindcue/help/img/{lang} {lang} <media dir>  (media: tools/make_manual_media.py)")
    text = re.sub(r"\n{3,}", "\n\n", text)
    if "{{" in text or "<!--IF" in text or "<!--/IF" in text:
        raise ValueError("unresolved marker left in the output")
    return text


def main() -> int:
    features = present()
    app, version = app_name_and_version()
    print("features:", ", ".join(sorted(features)) or "none")
    for lang in LANGS:
        src = (SRC_DIR / f"manual_{lang}.src.html").read_text(encoding="utf-8")
        out = HELP_DIR / f"manual_{lang}.html"
        out.write_text(build(src, lang, features, HELP_DIR, app, version), encoding="utf-8", newline="\n")
        print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
