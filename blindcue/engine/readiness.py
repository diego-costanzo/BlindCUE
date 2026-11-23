"""Readiness check before the show (stage 1 C2a step 7; plan items 5.6 + 4.5).

Pure logic, no Qt: the main window collects the facts (screens, speakers,
files, power, the show's checklist) and :func:`checks` turns them into rows
for the "Before the show" page. Order: what needs cables and walking first
(picture, then the master volume before the test tone, then the speakers),
then files, power and the checklist for people.

A row is ``OK``, a ``PROBLEM`` (the operator may still start), ``SKIPPED``
(not checked, e.g. no test tone yet) or ``INFO`` (no verdict).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

OK = "ok"
PROBLEM = "problem"
SKIPPED = "skipped"
INFO = "info"

SCREEN = "screen"
VOLUME = "volume"
SPEAKERS = "speakers"
MEDIA = "media"
POWER = "power"
CHECKLIST = "checklist"
SHOW = "show"

# Items of the checklist a new show starts with (Italian source; stored in
# the show in the operator's language, then edited freely).
DEFAULT_CHECKLIST = [
    "Alimentatore collegato al portatile",
    "Notifiche disattivate (Windows: Non disturbare)",
    "Altri programmi chiusi (Teams, browser, OneDrive)",
    "Schermo del portatile abbassato",
    "Amplificatore e casse accesi, manopola come alla prova",
    "Copia dello spettacolo su chiavetta (File → Salva con nome, portatile)",
    "Telefono del telecomando carico, nella stessa rete",
]
DEFAULT_CHECKLIST_NAME = "Checklist prima dello spettacolo"


@dataclass(frozen=True)
class Facts:
    """What the main window knows when the page is built."""

    screen_name: str | None = None      # where the output goes
    screen_external: bool = False       # not the laptop's own screen
    screen_count: int = 1
    master_level: float = 1.0
    master_muted: bool = False
    speakers: str = ""                  # device the show plays on
    speakers_pinned: bool = False       # chosen on this computer (not the Windows default)
    speakers_missing: str | None = None  # pinned speakers that are not connected
    heard: bool | None = None           # test tone: heard in the hall? None = not tried
    playing: bool = False               # something is on air (no test tone then)
    missing: tuple[str, ...] = ()       # "#6 'name'" of cues whose file is gone
    media_total: int = 0
    power: tuple[bool, int] | None = None  # (on battery, percent); None = no battery
    checklist: tuple[int, int] | None = None  # (ticked, items); None = the show has none
    show_name: str = ""


@dataclass(frozen=True)
class Check:
    """One row of the page: what, its verdict and the values for its text."""

    key: str
    state: str
    values: dict = field(default_factory=dict)


def checks(f: Facts) -> list[Check]:
    """Rows of the readiness page, in the order the operator should go through them."""
    rows: list[Check] = []
    if f.screen_external and f.screen_name:
        rows.append(Check(SCREEN, OK, {"name": f.screen_name}))
    else:
        rows.append(Check(SCREEN, PROBLEM, {"single": f.screen_count <= 1}))

    if f.master_muted or f.master_level < 0.999:
        rows.append(Check(VOLUME, PROBLEM, {"percent": round(f.master_level * 100), "muted": f.master_muted}))
    else:
        rows.append(Check(VOLUME, OK, {"percent": 100}))

    if f.speakers_missing:
        rows.append(Check(SPEAKERS, PROBLEM, {"missing": f.speakers_missing, "name": f.speakers}))
    elif f.heard is True:
        rows.append(Check(SPEAKERS, OK, {"name": f.speakers, "pinned": f.speakers_pinned}))
    elif f.heard is False:
        rows.append(Check(SPEAKERS, PROBLEM, {"name": f.speakers, "not_heard": True}))
    else:
        rows.append(Check(SPEAKERS, SKIPPED, {"name": f.speakers, "pinned": f.speakers_pinned,
                                              "playing": f.playing}))

    if f.missing:
        rows.append(Check(MEDIA, PROBLEM, {"count": len(f.missing), "cues": list(f.missing)}))
    else:
        rows.append(Check(MEDIA, OK, {"count": f.media_total}))

    if f.power is not None:
        on_battery, percent = f.power
        rows.append(Check(POWER, PROBLEM if on_battery else OK, {"percent": percent}))

    if f.checklist is None:
        rows.append(Check(CHECKLIST, INFO, {"none": True}))
    else:
        done, total = f.checklist
        rows.append(Check(CHECKLIST, OK if done >= total else PROBLEM, {"done": done, "total": total}))

    rows.append(Check(SHOW, INFO, {"name": f.show_name}))
    return rows


def problems(rows: list[Check]) -> list[Check]:
    return [r for r in rows if r.state == PROBLEM]


def page_rows(rows: list[Check], full: bool) -> list[Check]:
    """Everything on a full check; later entries show only what is not right."""
    return rows if full else problems(rows)


def power_status() -> tuple[bool, int] | None:
    """(on battery, charge %) of this laptop; None without a battery or off Windows."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class _SystemPowerStatus(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", wintypes.BYTE),
                ("BatteryFlag", wintypes.BYTE),
                ("BatteryLifePercent", wintypes.BYTE),
                ("SystemStatusFlag", wintypes.BYTE),
                ("BatteryLifeTime", wintypes.DWORD),
                ("BatteryFullLifeTime", wintypes.DWORD),
            ]

        status = _SystemPowerStatus()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return None
        flag = status.BatteryFlag & 0xFF
        if flag == 128 or flag == 255:  # no battery / unknown
            return None
        percent = status.BatteryLifePercent & 0xFF
        return (status.ACLineStatus & 0xFF) == 0, (percent if percent <= 100 else -1)
    except Exception:  # noqa: BLE001 - a status we cannot read is not a problem
        return None
