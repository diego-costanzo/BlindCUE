"""The settings of this computer to a file and back (stage 5, item 5.13). No Qt.

A teacher moving to another laptop takes the speakers and outputs, the
screens, the extra keys, the look and the running options with them instead
of setting everything again. Only these groups travel; the exit PIN stays
on its computer (it is a lock), and recent shows, folders and window sizes
belong to the computer they were made on.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

FORMAT = "blindcue-computer-settings"
VERSION = 1
GROUPS = ("audio", "output", "keys", "ui", "live")
KEEP_HERE = frozenset({"live/exit_pin"})
# Italian source strings (the UI translates them).
GROUP_LABELS = {
    "audio": "Audio: altoparlanti e uscite",
    "output": "Schermi e proiettore",
    "keys": "Tasti e telecomando",
    "ui": "Aspetto, lingua, suoni per la regia",
    "live": "Conduzione dello spettacolo",
}


def transferable(key: str) -> bool:
    """True for a settings key that goes to the file."""
    group, sep, rest = key.partition("/")
    return bool(sep and rest) and group in GROUPS and key not in KEEP_HERE


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return str(value)


def to_json(values: Mapping[str, Any], computer: str = "", created: str = "") -> str:
    """The file: format, version, where and when it was made, the values of the groups that travel."""
    data = {
        "format": FORMAT,
        "version": VERSION,
        "computer": computer,
        "created": created,
        "values": {k: _plain(values[k]) for k in sorted(values) if transferable(k)},
    }
    return json.dumps(data, ensure_ascii=False, indent=1)


def from_json(text: str) -> dict[str, Any]:
    """The values of a settings file (only the groups that travel); ValueError when it is not one."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("non è un file di impostazioni di BlindCue") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("non è un file di impostazioni di BlindCue")
    if int(data.get("version", 0) or 0) > VERSION:
        raise ValueError("il file viene da una versione più nuova del programma")
    values = data.get("values")
    if not isinstance(values, dict):
        raise ValueError("il file non contiene impostazioni")
    return {str(k): _plain(v) for k, v in values.items() if transferable(str(k))}


def changes(current: Mapping[str, Any], incoming: Mapping[str, Any]) -> dict[str, list[str]]:
    """Group -> the keys an import would change (compared as text: settings come back as strings)."""
    out: dict[str, list[str]] = {}
    for key in sorted(incoming):
        if not transferable(key):
            continue
        if key in current and str(_plain(current[key])) == str(incoming[key]):
            continue
        out.setdefault(key.split("/", 1)[0], []).append(key)
    return out
