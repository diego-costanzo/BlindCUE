"""Pure math and runtime sequencing for audio/opacity envelopes and virtual sections.

Zero Qt GUI dependencies so timing, fade curves, keyframes, and virtual
section transitions stay lightweight, deterministic, and easily testable.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from models.cue import CueSection

FADE_CURVE_LABELS: dict[str, str] = {
    "log": "Logaritmica (Naturale)",
    "scurve": "S-Curve Morbida",
    "linear": "Lineare",
}

MIN_SECTION_SEC = 0.15


def clamp01(val: float) -> float:
    return 0.0 if val <= 0.0 else (1.0 if val >= 1.0 else float(val))


def section_label_for_index(idx: int) -> str:
    """Return 'A'..'Z' for 0..25, then 'S27'.. beyond."""
    if 0 <= idx < 26:
        return chr(ord("A") + idx)
    return f"S{idx + 1}"


# ── Fade Curves & Envelope Keyframes ──────────────────────────────────────

def apply_fade_curve(progress: float, curve: str = "log", *, fade_out: bool = False) -> float:
    """Map normalized fade progress (0..1) into gain multiplier (0..1)."""
    p = clamp01(progress)
    u = (1.0 - p) if fade_out else p
    if curve == "linear":
        return u
    if curve == "scurve":
        return 0.5 * (1.0 - math.cos(math.pi * u))
    # Default "log": perceptual exponent approximating logarithmic dB hearing
    return u ** 2.2


def normalize_points(points: Sequence[Sequence[float]]) -> list[list[float]]:
    """Return sorted, clamped [[t_sec, level], ...] envelope keyframes."""
    cleaned: list[list[float]] = []
    for p in points:
        if len(p) >= 2:
            cleaned.append([round(max(0.0, float(p[0])), 3), round(clamp01(float(p[1])), 3)])
    cleaned.sort(key=lambda item: item[0])
    return cleaned


def evaluate_points_envelope(
    t_sec: float,
    points: Sequence[Sequence[float]],
    base_level: float,
) -> float:
    """Evaluate piecewise-linear keyframe envelope at *t_sec*, falling back to *base_level*."""
    if not points:
        return clamp01(base_level)

    pts = sorted(points, key=lambda item: float(item[0]))
    if t_sec <= pts[0][0]:
        return clamp01(float(pts[0][1]))
    if t_sec >= pts[-1][0]:
        return clamp01(float(pts[-1][1]))

    for idx in range(len(pts) - 1):
        t0, v0 = float(pts[idx][0]), float(pts[idx][1])
        t1, v1 = float(pts[idx + 1][0]), float(pts[idx + 1][1])
        if t0 <= t_sec <= t1:
            if t1 - t0 <= 1e-6:
                return clamp01(v1)
            frac = (t_sec - t0) / (t1 - t0)
            return clamp01(v0 + frac * (v1 - v0))
    return clamp01(float(pts[-1][1]))


def evaluate_cue_level(
    t_sec: float,
    *,
    start_sec: float,
    end_sec: Optional[float],
    duration_sec: float,
    fade_in: float,
    fade_out: float,
    fade_curve: str,
    points: Sequence[Sequence[float]],
    base_level: float,
    apply_fade_out_at_end: bool = True,
) -> float:
    """Evaluate effective gain/opacity (0..1) combining keyframes and IN/OUT fade ramps."""
    eff_start = max(0.0, float(start_sec))
    eff_end = (
        float(end_sec)
        if (end_sec is not None and end_sec > eff_start)
        else max(eff_start, float(duration_sec))
    )

    level = evaluate_points_envelope(t_sec, points, base_level)

    if fade_in > 0.0:
        fi_end = eff_start + fade_in
        if t_sec < eff_start:
            level *= 0.0
        elif t_sec < fi_end:
            level *= apply_fade_curve((t_sec - eff_start) / fade_in, fade_curve, fade_out=False)

    if apply_fade_out_at_end and fade_out > 0.0 and eff_end > eff_start:
        fo_start = max(eff_start, eff_end - fade_out)
        actual_fo = eff_end - fo_start
        if actual_fo > 1e-4:
            if t_sec >= eff_end:
                level *= 0.0
            elif t_sec > fo_start:
                level *= apply_fade_curve((t_sec - fo_start) / actual_fo, fade_curve, fade_out=True)

    return clamp01(level)


def add_or_update_point(
    points: Sequence[Sequence[float]],
    t_sec: float,
    val: float,
    merge_tol_sec: float = 0.04,
) -> tuple[list[list[float]], int]:
    """Insert or snap-update a keyframe point; returns (sorted_points, active_index)."""
    pts = normalize_points(points)
    t_clean = round(max(0.0, float(t_sec)), 3)
    v_clean = round(clamp01(float(val)), 3)

    for idx, pt in enumerate(pts):
        if abs(pt[0] - t_clean) <= merge_tol_sec:
            pts[idx] = [t_clean, v_clean]
            return pts, idx

    pts.append([t_clean, v_clean])
    pts.sort(key=lambda item: item[0])
    new_idx = next(i for i, pt in enumerate(pts) if pt[0] == t_clean and pt[1] == v_clean)
    return pts, new_idx


def move_point(
    points: Sequence[Sequence[float]],
    index: int,
    t_sec: float,
    val: float,
    t_min: float = 0.0,
    t_max: float = 1e9,
) -> list[list[float]]:
    """Move keyframe *index* strictly within adjacent keyframes to keep ordering invariant."""
    pts = [list(p) for p in points]
    if not (0 <= index < len(pts)):
        return pts
    left_bound = (pts[index - 1][0] + 0.02) if index > 0 else t_min
    right_bound = (pts[index + 1][0] - 0.02) if index < len(pts) - 1 else t_max
    if right_bound < left_bound:
        right_bound = left_bound
    pts[index][0] = round(max(left_bound, min(right_bound, float(t_sec))), 3)
    pts[index][1] = round(clamp01(float(val)), 3)
    return pts


def remove_point(points: Sequence[Sequence[float]], index: int) -> list[list[float]]:
    """Remove keyframe *index* cleanly if in bounds."""
    pts = [list(p) for p in points]
    if 0 <= index < len(pts):
        pts.pop(index)
    return pts


# ── Virtual Contiguous Sections & Runtime Sequencer ───────────────────────

def normalize_sections(
    sections: Sequence[CueSection],
    cue_in: float,
    eff_end: float,
) -> list[CueSection]:
    """Ensure sections stay strictly contiguous inside [cue_in, eff_end] with clean A/B/C labels."""
    if not sections or eff_end <= cue_in + MIN_SECTION_SEC * 2:
        return []

    raw = sorted(sections, key=lambda s: float(s.start))
    # Collapse degenerate intervals safely
    bounds: list[tuple[float, int, bool]] = []  # (start, loops, skip)
    cursor = float(cue_in)
    for sec in raw:
        s_start = max(cursor, min(eff_end - MIN_SECTION_SEC, float(sec.start)))
        if not bounds:
            bounds.append((cue_in, int(sec.loops), bool(sec.skip)))
            cursor = cue_in + MIN_SECTION_SEC
        elif s_start >= cursor:
            bounds.append((round(s_start, 3), int(sec.loops), bool(sec.skip)))
            cursor = s_start + MIN_SECTION_SEC

    if len(bounds) < 2:
        return []

    result: list[CueSection] = []
    for i, (start_val, loops_val, skip_val) in enumerate(bounds):
        end_val = bounds[i + 1][0] if i + 1 < len(bounds) else None
        result.append(
            CueSection(
                label=section_label_for_index(i),
                start=round(start_val, 3),
                end=round(end_val, 3) if end_val is not None else None,
                loops=max(0, loops_val),
                skip=skip_val,
            )
        )
    return result


def split_sections_at(
    sections: Sequence[CueSection],
    split_sec: float,
    cue_in: float,
    eff_end: float,
) -> list[CueSection]:
    """Split timeline or existing section contiguously at *split_sec*."""
    t = round(float(split_sec), 3)
    if t < cue_in + MIN_SECTION_SEC or t > eff_end - MIN_SECTION_SEC:
        return list(sections)

    if not sections:
        return [
            CueSection(label="A", start=round(cue_in, 3), end=t, loops=1, skip=False),
            CueSection(label="B", start=t, end=None, loops=1, skip=False),
        ]

    cur = normalize_sections(sections, cue_in, eff_end)
    if not cur:
        return [
            CueSection(label="A", start=round(cue_in, 3), end=t, loops=1, skip=False),
            CueSection(label="B", start=t, end=None, loops=1, skip=False),
        ]

    new_list: list[CueSection] = []
    inserted = False
    for sec in cur:
        s_end = sec.end if sec.end is not None else eff_end
        if not inserted and sec.start + MIN_SECTION_SEC <= t <= s_end - MIN_SECTION_SEC:
            new_list.append(
                CueSection(label="", start=sec.start, end=t, loops=sec.loops, skip=sec.skip)
            )
            new_list.append(
                CueSection(label="", start=t, end=sec.end, loops=1, skip=False)
            )
            inserted = True
        else:
            new_list.append(sec)
    return normalize_sections(new_list, cue_in, eff_end)


def resize_section_divider(
    sections: Sequence[CueSection],
    divider_idx: int,
    new_t: float,
    cue_in: float,
    eff_end: float,
) -> list[CueSection]:
    """Move shared boundary between section[divider_idx] and section[divider_idx + 1]."""
    cur = normalize_sections(sections, cue_in, eff_end)
    if not (0 <= divider_idx < len(cur) - 1):
        return cur
    left = cur[divider_idx]
    right = cur[divider_idx + 1]
    right_end = right.end if right.end is not None else eff_end
    clamped = round(max(left.start + MIN_SECTION_SEC, min(right_end - MIN_SECTION_SEC, float(new_t))), 3)
    left.end = clamped
    right.start = clamped
    return normalize_sections(cur, cue_in, eff_end)


def merge_section_at(
    sections: Sequence[CueSection],
    idx: int,
    cue_in: float,
    eff_end: float,
) -> list[CueSection]:
    """Remove section *idx*, merging its span cleanly into adjacent neighbor."""
    cur = normalize_sections(sections, cue_in, eff_end)
    if len(cur) <= 2 or not (0 <= idx < len(cur)):
        return []
    if idx == 0:
        cur[1].start = cur[0].start
        cur.pop(0)
    else:
        cur[idx - 1].end = cur[idx].end
        cur.pop(idx)
    return normalize_sections(cur, cue_in, eff_end)


class SectionSequencer:
    """Tracks section iterations, infinite vamps, skip cuts, and lookahead jump targets."""

    def __init__(self) -> None:
        self.sections: list[CueSection] = []
        self.cue_in: float = 0.0
        self.eff_end: float = 0.0
        self.current_index: int = 0
        self.iteration: int = 0

    def configure(
        self,
        sections: Sequence[CueSection],
        cue_in: float,
        eff_end: float,
    ) -> None:
        self.cue_in = max(0.0, float(cue_in))
        self.eff_end = max(self.cue_in, float(eff_end))
        self.sections = normalize_sections(sections, self.cue_in, self.eff_end)
        self.current_index = 0
        self.iteration = 0
        first = self._next_playable_index(0)
        if first is not None:
            self.current_index = first

    @property
    def active(self) -> bool:
        return len(self.sections) >= 2

    def update_live_sections(self, sections: Sequence[CueSection], eff_end: Optional[float] = None) -> None:
        """Hot-reload loop/skip flags mid-playback without losing current index."""
        if eff_end is not None and eff_end > self.cue_in:
            self.eff_end = float(eff_end)
        norm = normalize_sections(sections, self.cue_in, self.eff_end)
        self.sections = norm
        if self.sections:
            self.current_index = min(self.current_index, len(self.sections) - 1)
        else:
            self.current_index = 0
            self.iteration = 0

    def _next_playable_index(self, from_idx: int) -> Optional[int]:
        for i in range(max(0, from_idx), len(self.sections)):
            if not self.sections[i].skip:
                return i
        return None

    def current_section(self) -> Optional[CueSection]:
        if 0 <= self.current_index < len(self.sections):
            return self.sections[self.current_index]
        return None

    def active_start_sec(self) -> float:
        sec = self.current_section()
        return sec.start if sec is not None else self.cue_in

    def active_end_sec(self) -> float:
        sec = self.current_section()
        if sec is None:
            return self.eff_end
        return sec.end if sec.end is not None else self.eff_end

    def _compute_transition(self) -> tuple[str, Optional[int], Optional[float], int]:
        """Compute (action, next_idx, jump_start_sec, next_iter) without mutating self."""
        sec = self.current_section()
        if sec is None:
            return ("EOF", None, None, 0)

        next_iter = self.iteration + 1
        # Stay in current section if infinite (loops == 0) or iterations remain (loops >= 2)
        if sec.loops == 0 or next_iter < sec.loops:
            return ("JUMP", self.current_index, sec.start, next_iter)

        # Otherwise advance to next non-skipped section
        nxt = self._next_playable_index(self.current_index + 1)
        if nxt is None:
            return ("EOF", None, None, 0)

        nxt_sec = self.sections[nxt]
        cur_end = sec.end if sec.end is not None else self.eff_end
        if nxt == self.current_index + 1 and abs(nxt_sec.start - cur_end) <= 0.03:
            # Contiguous forward transition: ZERO seek required!
            return ("CONTINUE", nxt, None, 0)
        return ("JUMP", nxt, nxt_sec.start, 0)

    def peek_next_jump_target(self) -> Optional[float]:
        """Return future jump start time in seconds ONLY if next transition needs a seek."""
        if not self.active:
            return None
        action, _idx, target_sec, _next_iter = self._compute_transition()
        if action == "JUMP" and target_sec is not None:
            return target_sec
        return None

    def advance_at_boundary(self) -> tuple[str, Optional[int], Optional[float]]:
        """Commit boundary transition and return (action, target_idx, target_start_sec)."""
        action, target_idx, target_sec, next_iter = self._compute_transition()
        if action == "EOF":
            return ("EOF", None, None)
        assert target_idx is not None
        self.current_index = target_idx
        self.iteration = next_iter
        return (action, target_idx, target_sec)

    def jump_to(self, target_idx: int) -> Optional[float]:
        """Manually jump directly to section *target_idx*."""
        if not (0 <= target_idx < len(self.sections)):
            return None
        self.current_index = target_idx
        self.iteration = 0
        return self.sections[target_idx].start

    def break_loop_to_next(self) -> tuple[str, Optional[int], Optional[float]]:
        """Exit current repeating section cleanly onto the next playable section."""
        if not self.active:
            return ("EOF", None, None)
        nxt = self._next_playable_index(self.current_index + 1)
        if nxt is None:
            return ("EOF", None, None)
        self.current_index = nxt
        self.iteration = 0
        return ("JUMP", nxt, self.sections[nxt].start)

