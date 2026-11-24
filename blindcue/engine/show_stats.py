"""Numbers about a show for its info window (stage 5, item 5.6). No Qt."""

from __future__ import annotations

import os
from collections.abc import Iterable

from engine.show_engine import go_stops
from models.cue import Cue, MediaType, is_placeholder


def show_stats(cues: Iterable[Cue]) -> dict[str, int]:
    """How many cues of each kind, how many GOs, effects, cues switched off, missing files."""
    cue_list = list(cues)
    texts = sum(1 for c in cue_list if c.media_type == MediaType.IMAGE and getattr(c, "text_spec", None))
    return {
        "cues": len(cue_list),
        "go": len(go_stops(cue_list)),
        "video": sum(1 for c in cue_list if c.media_type == MediaType.VIDEO),
        "audio": sum(1 for c in cue_list if c.media_type == MediaType.AUDIO),
        "pictures": sum(1 for c in cue_list if c.media_type == MediaType.IMAGE) - texts,
        "texts": texts,
        "scenes": sum(1 for c in cue_list if c.media_type == MediaType.GROUP),
        "actions": sum(1 for c in cue_list if c.media_type == MediaType.ACTION),
        "effects": sum(1 for c in cue_list if getattr(c, "adlib", False)),
        "off": sum(1 for c in cue_list if not getattr(c, "enabled", True)),
        "missing": sum(1 for c in cue_list if c.media_type.has_file and not getattr(c, "text_spec", None)
                       and not os.path.isfile(c.file_path or "") and not is_placeholder(c)),
    }
