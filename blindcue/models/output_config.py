"""Configurazione del routing delle uscite video.

BlindCue può pilotare i proiettori in tre modi espliciti, mai impliciti:

- ``SINGLE``: una sola uscita, su un singolo schermo (regia + proiettore).
- ``SPAN``: una sola uscita che copre più schermi esterni come un'unica tela
  (due proiettori che formano una superficie uniforme).
- ``DUAL``: due uscite separate e indipendenti, ciascuna con i propri 3 layer
  (due proiettori che mostrano contenuti diversi nello stesso momento).

Il modello è volutamente minimale: descrive *come* la finestra di uscita viene
mappata sui display, non il contenuto. L'assegnazione del contenuto alle aree
proiettate resta compito delle superfici virtuali (``models.surface``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class OutputMode(str, Enum):
    """Modalità di mapping della finestra di uscita sui display fisici."""

    SINGLE = "single"
    SPAN = "span"
    DUAL = "dual"


OUTPUT_MODE_LABELS: dict[str, str] = {
    OutputMode.SINGLE.value: "Singolo schermo",
    OutputMode.SPAN.value: "Superficie unica (span)",
    OutputMode.DUAL.value: "Due uscite indipendenti",
}


def normalize_output_mode(value: Any) -> str:
    """Return a valid :class:`OutputMode` value, falling back to ``single``."""
    if isinstance(value, OutputMode):
        return value.value
    text = str(value or "").strip().lower()
    if text in OUTPUT_MODE_LABELS:
        return text
    return OutputMode.SINGLE.value


@dataclass
class OutputConfig:
    """Persisted output routing settings for a show.

    Stored inside the project file, so reopening a show restores exactly the
    routing it was built for. Use :meth:`to_dict`/:meth:`from_dict` — never
    assign ``mode`` from raw user/JSON data without going through
    ``normalize_output_mode``.
    """

    mode: str = OutputMode.SINGLE.value

    def __post_init__(self) -> None:
        # Any unknown value (older project files, hand-edited JSON) degrades
        # to SINGLE instead of raising: a show must always open.
        """Degrade unknown modes to SINGLE instead of blocking the opening of a show."""
        self.mode = normalize_output_mode(self.mode)

    @property
    def is_span(self) -> bool:
        """True when both projectors form one continuous surface."""
        return self.mode == OutputMode.SPAN.value

    @property
    def is_dual(self) -> bool:
        """True when the two projectors show independent content (layers 4-6 on B)."""
        return self.mode == OutputMode.DUAL.value

    def to_dict(self) -> dict[str, Any]:
        """Serialise to the JSON structure written inside the project file."""
        return {"mode": self.mode}

    @classmethod
    def from_dict(cls, data: Any) -> OutputConfig:
        """Rebuild from saved data, tolerating missing/legacy payloads."""
        if isinstance(data, OutputConfig):
            return cls(mode=data.mode)
        if isinstance(data, dict):
            return cls(mode=data.get("mode", OutputMode.SINGLE.value))
        return cls()
