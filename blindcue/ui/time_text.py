"""One way to type a time in every seconds field (stage 2, item 2.9).

``parse_seconds`` understands what people type: "83.5", "83,5", ".8",
"1:23.5", "1:02:03", "2.1.7" (dots for colons, numeric keypad), "1m23s",
"1m 23,5s", "2m", "45s", "1h2m", and a leading "-" for fields that allow it
(move by -10 s). ``could_become_time`` tells a spin box
that the text is still being typed ("1:", "1m").
"""

from __future__ import annotations

import re

_NUM = r"(\d+(?:\.\d*)?|\.\d+)"
_UNITS = re.compile(rf"^(?:{_NUM}h)?(?:{_NUM}m)?(?:{_NUM}s?)?$")
_PARTIAL = re.compile(r"^-?[\d\s:.,hms]*$")


def parse_seconds(text: str | None) -> float | None:
    """Seconds from *text*, or None when it is not a time."""
    raw = (text or "").strip().lower().replace(",", ".")
    if not raw:
        return None
    sign = -1.0 if raw.startswith("-") else 1.0
    raw = raw.lstrip("+-").strip()
    if ":" not in raw and raw.count(".") >= 2:  # numeric keypad: 2.1.7 = 2:1.7
        head, _, frac = raw.rpartition(".")
        raw = head.replace(".", ":") + "." + frac
    if ":" in raw:
        parts = raw.rstrip("s").split(":")
        if len(parts) > 3 or any(not p.replace(".", "", 1).isdigit() for p in parts):
            return None
        if any("." in p for p in parts[:-1]):
            return None
        total = 0.0
        for part in parts:
            total = total * 60 + float(part)
        if len(parts) >= 2 and float(parts[-1]) >= 60:
            return None
        return sign * total
    match = _UNITS.match(raw.replace(" ", ""))
    if not match or not any(match.groups()):
        return None
    hours, minutes, seconds = (float(g) if g else 0.0 for g in match.groups())
    return sign * (hours * 3600 + minutes * 60 + seconds)


def could_become_time(text: str | None) -> bool:
    """True while *text* may still turn into a time ("1:", "1m", "")."""
    return bool(_PARTIAL.match((text or "").strip().lower()))
