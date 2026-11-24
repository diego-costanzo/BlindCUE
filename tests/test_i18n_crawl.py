"""Every text the program shows is in the UI language (translation sweep 2026-11-24).

``tests/i18n_crawl.py`` builds the real main window offscreen in Polish (and
English), walks it in Preparation, Rehearsal and Show, opens the dialogs and
the generated pages (cheat sheet, printed list, CSV, run report) and lists the
visible texts that still hold an Italian (or, in Polish, English) word no
translation uses. It runs in a process of its own because ``i18n.install()``
wraps Qt classes for the whole process.

A failure lists the text, the foreign words and where it was seen. Fix it with
a dictionary entry (``blindcue/i18n/pl.py`` / ``en.py``), with ``tr()`` where
the text bypasses the Qt wrappers, or - for a proper name - in ``ALLOWED`` /
``ALLOWED_TEXTS`` of ``tests/i18n_crawl.py``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
MARK = "@@CRAWL@@"


def _crawl(lang: str) -> dict:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", BLINDCUE_CRAWL_TIMEOUT="540")
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(TESTS / "i18n_crawl.py"), lang, "--json"],
        check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=600,
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith(MARK)), None)
    assert line is not None, f"the crawl did not finish (exit {proc.returncode}):\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}"
    return json.loads(line[len(MARK):])


def _report(result: dict) -> str:
    out = []
    for item in result["leftovers"]:
        out.append(f"{item['words']}  {item['text'][:200]!r}\n        " + "\n        ".join(item["where"]))
    out += [f"ERROR {err}" for err in result["errors"]]
    return "\n".join(out)


@pytest.mark.parametrize("lang", ["pl", "en"])
def test_no_italian_left_on_screen(lang):
    result = _crawl(lang)
    assert result["texts"] > 1000, f"the crawl saw too little ({result['texts']} texts)"
    assert not result["leftovers"] and not result["errors"], "\n" + _report(result)
