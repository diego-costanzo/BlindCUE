"""Logical audio outputs (stage 3, item 3.1): the rules, without Qt devices.

A cue plays on a logical output - "stage" (the main speakers, the old
"master" choice), "hall" or "foldback" (monitors for the performers) - or is
muted. Each computer maps the outputs to its own devices (QSettings, never
the show file), so a show moves to another computer unchanged. When an
output is not set there, or its device is unplugged, a fallback rule
decides: stage -> the system default, hall -> like the stage, foldback ->
muted (a private track never reaches the audience). Every output has a trim
(-30..+12 dB; Qt volume cannot go above 1.0, so the part above 0 dB is
played only by the own mixer of 3.2).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

OUTPUTS = ("stage", "hall", "foldback")
CUE_OUTPUTS = (*OUTPUTS, "mute")
ROLE = {"stage": "master", "hall": "hall", "foldback": "foldback"}  # QSettings role of each output
FALLBACKS = ("default", "stage", "mute")
# The stage never goes silent by a rule: a show without its main speakers must still be heard.
ALLOWED_FALLBACKS = {"stage": ("default",), "hall": FALLBACKS, "foldback": FALLBACKS}
DEFAULT_FALLBACK = {"stage": "default", "hall": "stage", "foldback": "mute"}
TRIM_MIN_DB = -30.0
# 3.2: a trim above 0 dB is played by the own mixer (engine.audio_mixer_*): sound cues on such an
# output go through it; Qt Multimedia (video sound, mixer off) stays at 0 dB.
TRIM_MAX_DB = 12.0
# Italian source strings (translated by the i18n layer like every other label).
LABELS = {"stage": "Palco", "hall": "Sala", "foldback": "Spie (ascolto palco)", "mute": "Muto",
          "default": "uscita predefinita"}
MAP_VERSION = 1


def normalize_output(value: object) -> str:
    """A cue's output: one of CUE_OUTPUTS, "stage" for anything else."""
    text = str(value or "").strip().lower()
    return text if text in CUE_OUTPUTS else "stage"


def normalize_fallback(key: str, value: object) -> str:
    """The fallback rule of *key*; the stage cannot fall back on itself."""
    text = str(value or "").strip().lower()
    if text not in ALLOWED_FALLBACKS.get(key, FALLBACKS):
        return DEFAULT_FALLBACK.get(key, "default")
    return text


def clamp_trim(db: object) -> float:
    try:
        value = float(db)
    except (TypeError, ValueError):
        return 0.0
    return max(TRIM_MIN_DB, min(TRIM_MAX_DB, value)) if value == value else 0.0


def trim_gain(db: object) -> float:
    """Linear gain of a trim in dB for Qt Multimedia (never above 1.0)."""
    return 10 ** (min(0.0, clamp_trim(db)) / 20.0)


def mixer_trim_gain(db: object) -> float:
    """Linear gain of a trim in dB for the own mixer (up to TRIM_MAX_DB)."""
    return 10 ** (clamp_trim(db) / 20.0)


@dataclass(frozen=True)
class Route:
    """Where a logical output plays right now."""

    device: Any | None   # None = the system default device
    muted: bool
    via: str             # "stage" / "hall" / "foldback": where it plays ("stage" with device None = the
                         # stage follows the system default), "default" (the current default) or "mute"
    missing: str = ""    # name of this output's chosen device while it is not connected


def resolve(key: str, choices: Mapping[str, tuple[str, str] | None], fallbacks: Mapping[str, object],
            find: Callable[[tuple[str, str]], Any | None], _depth: int = 0) -> Route:
    """The route of output *key*.

    *choices*: output -> remembered ``(id hex, name)`` or None (not set here);
    *find*: a remembered choice -> the connected device, or None.
    """
    key = normalize_output(key)
    if key == "mute":
        return Route(None, True, "mute")
    choice = choices.get(key)
    missing = ""
    if choice is not None:
        device = find(choice)
        if device is not None:
            return Route(device, False, key)
        missing = choice[1] or choice[0]
    elif key == "stage":
        return Route(None, False, "stage")  # follows the system default, as before 3.1 (the master device)
    rule = normalize_fallback(key, fallbacks.get(key))
    if rule == "mute":
        return Route(None, True, "mute", missing)
    if rule == "stage" and _depth == 0:
        via = resolve("stage", choices, fallbacks, find, _depth + 1)
        return Route(via.device, via.muted, via.via, missing)
    return Route(None, False, "default", missing)


def export_map(outputs: Mapping[str, Mapping[str, object]]) -> dict:
    """The per-computer map as a JSON-ready dict (to move it to another computer)."""
    out = {}
    for key in OUTPUTS:
        item = outputs.get(key, {})
        out[key] = {"id": str(item.get("id", "") or ""), "name": str(item.get("name", "") or ""),
                    "fallback": normalize_fallback(key, item.get("fallback")),
                    "trim_db": clamp_trim(item.get("trim_db", 0.0))}
    return {"blindcue_audio_outputs": MAP_VERSION, "outputs": out}


def import_map(data: object) -> dict[str, dict]:
    """Validated outputs present in an exported map (others stay as they are); ValueError when it is not one."""
    version = data.get("blindcue_audio_outputs") if isinstance(data, dict) else None
    if (not isinstance(version, int) or isinstance(version, bool) or not 1 <= version <= MAP_VERSION
            or not isinstance(data.get("outputs"), dict)):
        raise ValueError("not a BlindCue audio output map")
    present = {k: v for k, v in data["outputs"].items() if k in OUTPUTS and isinstance(v, dict)}
    if not present:
        raise ValueError("the map has no outputs")
    full = export_map(present)["outputs"]
    return {k: full[k] for k in present}
