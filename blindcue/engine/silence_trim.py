"""Cut the silence at the start and the end of a sound (stage 3, item 3.4).

Files from the internet often start with seconds of silence and end with a
long tail. ``sound_bounds`` finds where the sound really starts and ends in
the waveform peaks the program already has (normalised 0..1, one value per
bin): the first and last bin above a threshold relative to the loudest
peak, with a small margin, so nothing audible is cut.
"""

from __future__ import annotations

from collections.abc import Sequence

THRESHOLD_DB = -40.0   # relative to the loudest peak of the file
MARGIN_SEC = 0.05


def sound_bounds(peaks: Sequence[float] | None, duration: float, threshold_db: float = THRESHOLD_DB,
                 margin: float = MARGIN_SEC) -> tuple[float, float | None] | None:
    """(IN, OUT) in seconds - OUT None when the sound reaches the end - or None without any sound."""
    values = [float(v) for v in (peaks if peaks is not None else [])]
    if not values or duration <= 0:
        return None
    loudest = max(values)
    if loudest <= 0:
        return None
    limit = loudest * 10 ** (threshold_db / 20.0)
    loud = [i for i, v in enumerate(values) if v >= limit]
    step = duration / len(values)
    start = max(0.0, loud[0] * step - margin)
    end = min(duration, (loud[-1] + 1) * step + margin)
    if start < step:
        start = 0.0  # nothing worth cutting at the start
    return round(start, 2), (None if end >= duration - step else round(end, 2))
