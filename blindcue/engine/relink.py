"""Missing media found again (stage 5, item 5.10). No Qt.

``find_in_folder`` looks for the files of a show that are not where the show
says (a show copied to another computer, a renamed folder) in one folder and
its subfolders, by file name (case does not matter). The first file of that
name wins; the program reports which names it found more than once.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path


def find_in_folder(missing: Iterable[str], folder: str | Path,
                   limit: int = 200_000) -> tuple[dict[str, str], set[str]]:
    """({old path: new path}, names found more than once) for the *missing* paths.

    At most *limit* files are looked at, so a whole disk never freezes the program.
    """
    wanted: dict[str, list[str]] = {}
    for old in missing:
        name = Path(old).name.casefold()
        if name:
            wanted.setdefault(name, []).append(old)
    found: dict[str, str] = {}
    twice: set[str] = set()
    seen = 0
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        for file in sorted(files):
            seen += 1
            if seen > limit:
                return _paths(wanted, found), twice
            key = file.casefold()
            if key in wanted:
                if key in found:
                    twice.add(file)
                else:
                    found[key] = os.path.join(root, file)
    return _paths(wanted, found), twice


def _paths(wanted: dict[str, list[str]], found: dict[str, str]) -> dict[str, str]:
    return {old: found[name] for name, olds in wanted.items() if name in found for old in olds}
