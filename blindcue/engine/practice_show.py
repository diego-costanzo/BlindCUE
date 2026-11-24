"""The practice show (stage 5, item 5.17). No Qt.

A short show with every kind of cue, built on small media made for it
(tools/make_practice_media.py, in assets/practice): a note for the operator,
music that starts with a picture, a caption, a bell on a key, a video with a
crossfade, a step-by-step scene, a storm that crossfades the music, a fade
of everything and the end caption. A teacher learns the program on it
without own files. Names and texts come through *tr* (the operator's
language); captions are rendered by *caption_png*.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from engine.action_cues import default_action_spec
from models.cue import Cue, CueStatus, FollowMode, GroupMode, MediaType

MEDIA_FILES = ("music.mp3", "bell.mp3", "storm.mp3", "curtain.mp4", "forest.png", "castle.png")


def practice_cues(media: Path, caption_png: Callable[[dict[str, Any]], str],
                  tr: Callable[[str], str] = lambda s: s) -> list[Cue]:
    """The cues of the practice show, their files in *media*."""

    def file_cue(name: str, kind: MediaType, file_name: str, **fields: Any) -> Cue:
        cue = Cue(name=tr(name), media_type=kind, file_path=str(media / file_name))
        for key, value in fields.items():
            setattr(cue, key, value)
        cue.status = CueStatus.LOADED
        return cue

    def caption(text: str, **fields: Any) -> Cue:
        spec = {"text": tr(text), "position": fields.pop("position", "bottom"), "size": fields.pop("size", 90)}
        cue = Cue(name="📝 " + tr(text).replace("\n", " "), media_type=MediaType.IMAGE, file_path=caption_png(spec))
        cue.text_spec = spec
        cue.layer = 3
        cue.fade_in = cue.fade_out = 0.5
        for key, value in fields.items():
            setattr(cue, key, value)
        cue.status = CueStatus.LOADED
        return cue

    def action(name: str, kind: str, **spec: Any) -> Cue:
        full = default_action_spec(kind)
        full.update(spec)
        cue = Cue(name=tr(name), media_type=MediaType.ACTION, file_path="", action_spec=full)
        cue.status = CueStatus.LOADED
        return cue

    welcome = action("Benvenuto", "note", text=tr(
        "Questo è lo spettacolo di prova. Premi la barra spaziatrice (GO) per passare alla cue successiva. "
        "Le note come questa le vedi solo tu, mai il pubblico."))
    music = file_cue("Musica d'apertura", MediaType.AUDIO, "music.mp3", layer=2, fade_in=2.0, fade_out=3.0,
                     follow_mode=FollowMode.SIMULTANEOUS.value)
    forest = file_cue("Sfondo: il bosco", MediaType.IMAGE, "forest.png", layer=1, fade_in=1.0)
    act1 = caption("Atto I – Nel bosco", hold_time=6.0)
    bell = file_cue("Campanello (tasto D)", MediaType.AUDIO, "bell.mp3", layer=2, adlib=True, hotkey="D")
    curtain = file_cue("Il sipario si apre", MediaType.VIDEO, "curtain.mp4", layer=1, crossfade=1.0, volume=0.0)
    scene = Cue(name=tr("Scena: il castello"), media_type=MediaType.GROUP, file_path="",
                group_mode=GroupMode.STEP.value, layer=1, collapsed=False, color="#6366f1")
    scene.status = CueStatus.LOADED
    castle = file_cue("Sfondo: il castello", MediaType.IMAGE, "castle.png", layer=1, crossfade=2.0)
    act2 = caption("Atto II – Il castello", hold_time=6.0)
    for child in (castle, act2):
        child.parent_id = scene.cue_id
    storm = file_cue("Temporale", MediaType.AUDIO, "storm.mp3", layer=2, crossfade=2.0)
    fade = action("Sfuma tutto", "fade", duration=3.0)
    end = caption("Fine", position="center", size=140)
    return [welcome, music, forest, act1, bell, curtain, scene, castle, act2, storm, fade, end]
