"""Hold the last frame of a video (stage 4.4).

A video cue with "hold the last frame" is paused ``HOLD_MARGIN_MS`` before its
end (the FFmpeg backend clears the picture at EndOfMedia). Its frame is then
put on the layer as a still picture and the player is stopped. From then on
the layer behaves like one that shows a picture: a GO on that layer replaces
it (with the new cue's crossfade), Fade / Fade All / Blackout fade it, PANIC
cuts it, Undo GO brings it back.

The cue stays LIVE in the list (its picture is on air) but it has ENDED:

- its end already started what follows (Post-Delay, Auto-GO, "after the end");
- it never blocks a GO (exclusive) and a stop never points the GO back at it;
- it is never paused, resumed or sought (that would play the video again);
- its card says "last frame" and has no clock.

``HeldFrames`` is that explicit state: runtime slot -> cue id, plus the frame
of the last few held cues, so Undo GO can bring one back straight into it.
``HeldFrameController`` does the work for ``main.py`` on the players and the
output windows it is handed (so it can be tested without starting the app).
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from models.cue import Cue, MediaType

logger = logging.getLogger(__name__)

# Frames kept for Undo GO (a 1080p frame is about 8 MB).
KEEP_FRAMES = 6


def wants_hold(cue: Cue | None) -> bool:
    """*cue* is a video that keeps its last frame (never an endless loop: it has no end)."""
    if cue is None or cue.media_type != MediaType.VIDEO or not getattr(cue, "hold_last_frame", False):
        return False
    if cue.loop and cue.loop_count <= 0:
        return False
    return not any(s.loops == 0 and not s.skip for s in cue.sections)


class HeldFrames:
    """Which runtime slots show the held last frame of which cue."""

    def __init__(self, keep: int = KEEP_FRAMES) -> None:
        self._slots: dict[int, int] = {}
        self._frames: OrderedDict[int, tuple[Any, float]] = OrderedDict()
        self._keep = max(1, int(keep))

    def hold(self, slot: int, cue_id: int, frame: Any, opacity: float = 1.0) -> None:
        self._slots[int(slot)] = int(cue_id)
        self._frames[int(cue_id)] = (frame, float(opacity))
        self._frames.move_to_end(int(cue_id))
        while len(self._frames) > self._keep:
            self._frames.popitem(last=False)

    def cue_on(self, slot: int) -> int | None:
        return self._slots.get(int(slot))

    def holds(self, slot: int, cue_id: int | None = None) -> bool:
        held = self._slots.get(int(slot))
        return held is not None and (cue_id is None or held == int(cue_id))

    def release(self, slot: int) -> int | None:
        """The slot no longer shows a held frame; the frame stays for Undo GO."""
        return self._slots.pop(int(slot), None)

    def clear(self) -> dict[int, int]:
        """Every held frame is gone (PANIC, Blackout, Fade All); returns slot -> cue id."""
        gone = dict(self._slots)
        self._slots.clear()
        return gone

    def slots(self) -> dict[int, int]:
        return dict(self._slots)

    def frame_of(self, cue_id: int) -> tuple[Any, float] | None:
        return self._frames.get(int(cue_id))


class HeldFrameController:
    """main.py's side of 4.4: players and output windows.

    *out_window(slot)* gives the output window of a runtime slot, *local_layer(slot)*
    its layer 1-3 there, *players* the live players by slot. *window* is the main
    window (``set_last_frame_held``).
    """

    def __init__(self, *, window: Any, players: dict[int, Any],
                 out_window: Callable[[int], Any], local_layer: Callable[[int], int]) -> None:
        self.state = HeldFrames()
        self._window = window
        self._players = players
        self._out_window = out_window
        self._local = local_layer

    # ── Playback ──────────────────────────────────────────────────────
    def arm(self, cue: Cue, player: Any) -> None:
        """After ``load()``: the player stops short of the end when the cue keeps its frame."""
        if player is not None and hasattr(player, "set_hold_last_frame"):
            player.set_hold_last_frame(wants_hold(cue))

    def freeze(self, cue: Cue, slot: int) -> bool:
        """End of a video: its last frame stays on the layer. False: nothing to keep (layer cleared as before)."""
        if not wants_hold(cue):
            return False
        player = self._players.get(slot)
        frame = player.current_frame_image() if player is not None else None
        if frame is None:
            logger.warning("[HOLD] '%s' (L%d): no frame to keep, the layer is cleared", cue.name, slot)
            return False
        out = self._out_window(slot)
        local = self._local(slot)
        if not out.hold_video_frame(local, frame):
            return False
        opacity = out.layer_picture_opacity(local)  # what the video showed at its end
        player.stop()
        self.state.hold(slot, cue.cue_id, frame, opacity)
        self._tell(cue.cue_id, slot, True)
        logger.info("[HOLD] '%s' keeps its last frame on L%d", cue.name, slot)
        return True

    def ended(self, cue: Cue, slot: int) -> bool:
        """The held cue's end is over (after its Post-Delay): True when the frame stays."""
        if not self.state.holds(slot, cue.cue_id):
            return False
        self._tell(cue.cue_id, slot, True)  # the card loses the Post-Delay clock
        return True

    def _tell(self, cue_id: int, slot: int, on: bool) -> None:
        self._window.set_last_frame_held(cue_id, slot, on, self.state.frame_of(cue_id) if on else None)

    def holds(self, slot: int, cue_id: int | None = None) -> bool:
        return self.state.holds(slot, cue_id)

    def release(self, slot: int) -> int | None:
        """The layer gets something else, or is cleared: no held frame there any more."""
        cue_id = self.state.release(slot)
        if cue_id is not None:
            self._tell(cue_id, slot, False)
        return cue_id

    def clear_all(self) -> None:
        for slot, cue_id in self.state.clear().items():
            self._tell(cue_id, slot, False)

    def fade_out(self, slot: int, seconds: float, callback: Callable[[], None] | None = None) -> None:
        """Fade the held frame like a picture, then forget it."""
        self.release(slot)
        player = self._players.get(slot)
        if player is not None:
            player.stop()
        self._out_window(slot).fade_out_layer(self._local(slot), max(0.0, seconds), callback=callback)

    def restore(self, cue: Cue, slot: int, seconds: float = 0.0) -> bool:
        """Undo GO: *cue* comes back on *slot* straight as its held frame (never played again)."""
        kept = self.state.frame_of(cue.cue_id)
        if kept is None:
            return False
        frame, opacity = kept
        out = self._out_window(slot)
        local = self._local(slot)
        if seconds > 0:
            out.begin_crossfade(local, seconds)  # first: the snapshot needs the picture taken back
        player = self._players.get(slot)
        if player is not None:
            if seconds > 0 and hasattr(player, "hand_over_tail"):
                player.hand_over_tail(seconds)  # the sound of what is taken back fades out
            player.stop()
        out.show_mirrored_frame(
            local, frame, opacity=opacity, crop=cue.crop, scale=cue.scale,
            pos_x=cue.position_x, pos_y=cue.position_y, aspect_ratio=cue.aspect_ratio,
            surface_id=getattr(cue, "surface_id", None), rotation=cue.rotation,
        )
        out.hide_video_widget(layer=local)
        self.state.hold(slot, cue.cue_id, frame, opacity)
        logger.info("[HOLD] '%s' back on L%d as its last frame (Undo GO)", cue.name, slot)
        return True
