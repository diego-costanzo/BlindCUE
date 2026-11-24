"""Qt-free logic of ACTION cues: what they act on and how they read in the UI.

An action cue has no media file. When it fires it stops, fades, releases the
loop of, re-levels or dims *other* cues, or shows a note to the operator. The
live wiring (players, output windows, scheduler) lives in ``main.py``; this
module only answers the questions that can be tested without Qt:

  * which runtime layers (1-6) an action reaches,
  * which level a level change ends at,
  * how the action is summarised in the cue list and inspector.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from models.cue import (
    ACTION_CALL,
    ACTION_CHECKLIST,
    ACTION_COUNTDOWN,
    ACTION_FADE,
    ACTION_GOTO,
    ACTION_LEVEL,
    ACTION_NOTE,
    ACTION_OPACITY,
    ACTION_PAUSE,
    ACTION_RELEASE,
    ACTION_RESUME,
    ACTION_SEEK,
    ACTION_STOP,
    ACTION_STOPWATCH,
    ACTION_TARGET_ALL,
    ACTION_TARGET_CUES,
    ACTION_TARGET_LAYER,
    ACTION_WAIT,
    Cue,
    MediaType,
    resolve_output_target,
    runtime_layer,
    sanitize_action_spec,
)

# A level change may raise a cue above its own volume, up to +12 dB.
MAX_LEVEL_TRIM = 4.0

# Media kinds each action can act on.
_KIND_MEDIA: dict[str, tuple[MediaType, ...]] = {
    ACTION_STOP: (MediaType.VIDEO, MediaType.AUDIO, MediaType.IMAGE),
    ACTION_FADE: (MediaType.VIDEO, MediaType.AUDIO, MediaType.IMAGE),
    ACTION_RELEASE: (MediaType.VIDEO, MediaType.AUDIO),
    ACTION_LEVEL: (MediaType.VIDEO, MediaType.AUDIO),
    ACTION_OPACITY: (MediaType.VIDEO, MediaType.IMAGE),
    ACTION_SEEK: (MediaType.VIDEO, MediaType.AUDIO),  # 2.2: what plays can be moved
    ACTION_PAUSE: (MediaType.VIDEO, MediaType.AUDIO),  # 2.11
    ACTION_RESUME: (MediaType.VIDEO, MediaType.AUDIO),  # 2.11
}


def expand_cue_ids(cues: Iterable[Cue], cue_ids: Iterable[int]) -> set[int]:
    """The chosen cue ids plus every cue inside a chosen group (nested too)."""
    cue_list = list(cues)
    wanted = {int(i) for i in cue_ids}
    changed = True
    while changed:
        changed = False
        for cue in cue_list:
            if cue.parent_id in wanted and cue.cue_id not in wanted:
                wanted.add(cue.cue_id)
                changed = True
    return wanted


def target_layers(
    spec: Mapping[str, object],
    cues: Iterable[Cue],
    live: Mapping[int, Cue],
    waiting: Mapping[int, Cue] | None = None,
    *,
    dual_active: bool = False,
) -> list[int]:
    """Runtime layers (1-6) the action applies to, in ascending order.

    *live* maps a runtime layer to the cue playing on it, *waiting* to the cue
    counting down its Pre-Delay there (a stop must also cancel that start).
    A layer is only returned when something plays or waits on it and that
    cue is a media kind the action can act on.
    """
    spec = sanitize_action_spec(dict(spec))
    kind = str(spec["kind"])
    media = _KIND_MEDIA.get(kind)
    if media is None:
        return []
    waiting = waiting or {}
    can_wait = kind in (ACTION_STOP, ACTION_FADE)
    target = spec["target"]

    def acts_on(layer: int, accept) -> bool:
        cue = live.get(layer)
        if cue is not None and cue.media_type in media and accept(cue):
            return True
        pending = waiting.get(layer) if can_wait else None
        return pending is not None and pending.media_type in media and accept(pending)

    layers = set(live) | (set(waiting) if can_wait else set())
    if target == ACTION_TARGET_LAYER:
        wanted = runtime_layer(
            int(spec["layer"]), resolve_output_target(spec["output"], dual_active)
        )
        return [wanted] if wanted in layers and acts_on(wanted, lambda _c: True) else []
    if target == ACTION_TARGET_CUES:
        ids = expand_cue_ids(cues, spec["cue_ids"])
        return sorted(l for l in layers if acts_on(l, lambda c: c.cue_id in ids))
    return sorted(l for l in layers if acts_on(l, lambda _c: True))


# What a stop/fade does on one layer.
STOP_CLEAR = "clear"                # stop what plays there and cancel what waits there
STOP_SILENCE = "silence"            # silence the playing target, keep the start waiting there
STOP_CANCEL_START = "cancel_start"  # only cancel the waiting target; the cue playing is no target


def stop_plan(
    spec: Mapping[str, object],
    cues: Iterable[Cue],
    live: Mapping[int, Cue],
    waiting: Mapping[int, Cue] | None = None,
    *,
    dual_active: bool = False,
) -> dict[int, str]:
    """Per runtime layer, how a stop/fade action treats it.

    "Everything" and "one layer" clear the layer. With chosen cues a layer can
    hold a target and a non-target at once (one playing, one counting down
    its Pre-Delay): only the target is touched.
    """
    cue_list = list(cues)
    waiting = waiting or {}
    layers = target_layers(spec, cue_list, live, waiting, dual_active=dual_active)
    spec = sanitize_action_spec(dict(spec))
    if spec["target"] != ACTION_TARGET_CUES:
        return {layer: STOP_CLEAR for layer in layers}
    chosen = expand_cue_ids(cue_list, spec["cue_ids"])
    plan: dict[int, str] = {}
    for layer in layers:
        playing, pending = live.get(layer), waiting.get(layer)
        playing_hit = playing is not None and playing.cue_id in chosen
        pending_hit = pending is not None and pending.cue_id in chosen
        if playing_hit and pending is not None and not pending_hit:
            plan[layer] = STOP_SILENCE
        elif pending_hit and playing is not None and not playing_hit:
            plan[layer] = STOP_CANCEL_START
        else:
            plan[layer] = STOP_CLEAR
    return plan


def level_trim_after(spec: Mapping[str, object], current_trim: float, cue_volume: float) -> float:
    """Level multiplier a playing cue ends at after a level change.

    The player multiplies its own envelope by this trim. *Absolute* sets the
    level the cue's Volume slider would give (60 % means "as if Volume were
    60 %"), so a cue normalised with an auto-gain keeps it. *Relative* adds
    the dB change to the current trim, so two "-6 dB" cues make -12 dB.
    """
    spec = sanitize_action_spec(dict(spec))
    if spec["mode"] == "relative":
        trim = float(current_trim) * 10.0 ** (float(spec["db"]) / 20.0)
    elif cue_volume > 0.0:
        trim = float(spec["level"]) / float(cue_volume)
    else:
        trim = float(current_trim)
    return max(0.0, min(MAX_LEVEL_TRIM, trim))


def action_duration(spec: Mapping[str, object]) -> float:
    """Seconds the action keeps working after it fired (0 for instant actions)."""
    spec = sanitize_action_spec(dict(spec))
    if spec["kind"] in (ACTION_FADE, ACTION_LEVEL, ACTION_OPACITY, ACTION_WAIT):
        return float(spec["duration"])
    if spec["kind"] in (ACTION_PAUSE, ACTION_RESUME):
        return float(spec["sleep_sec"])
    return 0.0


def _format_seconds(sec: float) -> str:
    return f"{sec:.1f}"


def describe_target(spec: Mapping[str, object], cues: Iterable[Cue] = ()) -> str:
    """Short text naming what the action acts on (Italian source string)."""
    spec = sanitize_action_spec(dict(spec))
    if spec["target"] == ACTION_TARGET_LAYER:
        if spec["output"] == "B":
            return f"Layer {spec['layer']} · Uscita B"
        return f"Layer {spec['layer']}"
    if spec["target"] == ACTION_TARGET_CUES:
        cue_list = list(cues)
        rows = {c.cue_id: i for i, c in enumerate(cue_list)}
        refs = []
        for cid in spec["cue_ids"]:
            if cid in rows:
                cue = cue_list[rows[cid]]
                q = (cue.q_label or "").strip()
                refs.append(f"#{rows[cid] + 1} {q}".strip())
            else:
                refs.append("?")
        if not refs:
            return "nessuna cue scelta"
        return "cue " + ", ".join(refs)
    return "tutto in onda"


def describe_action(spec: Mapping[str, object], cues: Iterable[Cue] = ()) -> str:
    """One-line summary of an action cue for the list, tooltips and inspector."""
    spec = sanitize_action_spec(dict(spec))
    kind = spec["kind"]
    if kind == ACTION_NOTE:
        first = str(spec["text"]).strip().splitlines()
        return f"Nota: {first[0]}" if first else "Nota (vuota)"
    if kind == ACTION_CHECKLIST:
        return f"Checklist: {len(spec['items'])} voci"
    if kind == ACTION_WAIT:
        return f"Attendi {_format_seconds(float(spec['duration']))} s, poi la successiva"
    if kind == ACTION_STOPWATCH:
        return {"start": "Cronometro: avvia", "stop": "Cronometro: ferma"}.get(spec["sw_mode"], "Cronometro: azzera")
    target = describe_target(spec, cues)
    secs = _format_seconds(float(spec["duration"]))
    if kind == ACTION_STOP:
        return f"Stop: {target}"
    # The target goes last: it may contain " in " itself ("tutto in onda"),
    # which would confuse the translation templates.
    if kind == ACTION_FADE:
        return f"Dissolvi in {secs} s: {target}"
    if kind == ACTION_RELEASE:
        return f"Rilascia loop: {target}"
    sleep = float(spec["sleep_sec"])
    if kind == ACTION_PAUSE:
        return f"Addormenta in {_format_seconds(sleep)} s: {target}" if sleep > 0 else f"Pausa: {target}"
    if kind == ACTION_RESUME and spec.get("wake_next"):  # 3.3: the next track of the playlist
        return (f"Risveglia dal brano successivo in {_format_seconds(sleep)} s: {target}" if sleep > 0
                else f"Riprendi dal brano successivo: {target}")
    if kind == ACTION_RESUME:
        return f"Risveglia in {_format_seconds(sleep)} s: {target}" if sleep > 0 else f"Riprendi: {target}"
    if kind == ACTION_LEVEL:
        if spec["mode"] == "relative":
            return f"Livello {float(spec['db']):+.1f} dB in {secs} s: {target}"
        return f"Livello {round(float(spec['level']) * 100)}% in {secs} s: {target}"
    if kind == ACTION_OPACITY:
        return f"Opacità {round(float(spec['level']) * 100)}% in {secs} s: {target}"
    if kind in (ACTION_GOTO, ACTION_CALL):
        one = describe_target({**spec, "target": ACTION_TARGET_CUES, "cue_ids": spec["cue_ids"][:1]}, cues)
        if kind == ACTION_CALL:
            return f"Chiama: {one}"
        limit = f" (al massimo {spec['goto_max']}×)" if spec["goto_max"] else ""
        return (f"Salta e avvia{limit}: {one}" if spec["goto_play"] else f"Prossimo GO{limit}: {one}")
    if kind == ACTION_COUNTDOWN:
        total = int(float(spec["countdown_sec"]))
        if total <= 0:
            return "Ferma il conto alla rovescia"
        title = str(spec["text"]).strip() or "Intervallo"
        return f"Conto alla rovescia {total // 60:02d}:{total % 60:02d}: {title}"
    if kind == ACTION_SEEK:
        sec = float(spec["seek_sec"])
        if spec["seek_mode"] == "absolute":
            return f"Vai a {_format_seconds(sec)} s: {target}"
        if spec["seek_mode"] == "before_end":
            return f"Vai a {_format_seconds(abs(sec))} s dalla fine: {target}"
        return f"Sposta di {sec:+.1f} s: {target}"
    return kind


def default_action_name(kind: str) -> str:
    """Name given to a new action cue of *kind* (Italian source string)."""
    return {
        ACTION_STOP: "Ferma subito",
        ACTION_FADE: "Dissolvi e ferma",
        ACTION_RELEASE: "Rilascia loop",
        ACTION_LEVEL: "Cambio livello",
        ACTION_OPACITY: "Opacità layer",
        ACTION_NOTE: "Nota per la regia",
        ACTION_CHECKLIST: "Checklist prima dello spettacolo",
        ACTION_GOTO: "Salta a una cue",
        ACTION_CALL: "Chiama una cue",
        ACTION_SEEK: "Sposta la riproduzione",
        ACTION_COUNTDOWN: "Conto alla rovescia",
        ACTION_WAIT: "Attendi",
        ACTION_PAUSE: "Pausa",
        ACTION_RESUME: "Riprendi",
        ACTION_STOPWATCH: "Cronometro",
    }.get(kind, "Azione")


def default_action_spec(kind: str) -> dict[str, object]:
    """A sensible starting point for a new action cue of *kind*."""
    spec: dict[str, object] = {"kind": kind, "target": ACTION_TARGET_ALL}
    if kind == ACTION_LEVEL:
        spec.update(mode="relative", db=-10.0, duration=2.0, curve="linear")
    elif kind == ACTION_OPACITY:
        spec.update(target=ACTION_TARGET_LAYER, layer=1, level=0.3, duration=2.0, curve="linear")
    elif kind == ACTION_FADE:
        spec.update(duration=3.0, curve="linear")
    elif kind == ACTION_WAIT:
        spec.update(duration=5.0)
    elif kind == ACTION_NOTE:
        spec.update(text="")
    elif kind == ACTION_CHECKLIST:
        spec.update(items=["Microfoni accesi", "Proiettore acceso", "Telefono in silenzioso"])
    return sanitize_action_spec(spec)
