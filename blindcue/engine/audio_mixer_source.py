"""Decoded sound for the own mixer (3.2): FFmpeg -> 16-bit PCM in memory, read by voices.

A *source* is one file at one tempo. It keeps what FFmpeg decoded in
*segments* (a segment = one FFmpeg run from a start point onwards, kept in
1-second chunks), so a seek inside what is decoded is instant and the cue's
loops and sections cost nothing. A seek elsewhere starts a new segment;
FFmpeg decodes several hundred times faster than real time, so the first
frames arrive after the process start (~50 ms on the Dell).

Decoding runs on its own Python thread per segment (blocking pipe reads,
which release the GIL); the audio thread only copies frames that are
already there and never waits. Memory is capped per source: a long file
keeps at most ``KEEP_SECONDS`` behind the reader and decodes at most
``AHEAD_SECONDS`` ahead of it.

Frames are counted in output frames at ``RATE``: with a tempo ``r`` frame
``f`` is file time ``f * r / RATE``.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from engine.audio_mixer_dsp import RATE

logger = logging.getLogger(__name__)

CHUNK = RATE                 # frames per stored chunk (1 s)
NEAR_SECONDS = 3.0           # a read this close after a decoding segment waits for it
AHEAD_SECONDS = 600.0        # decode at most this far ahead of the reader
KEEP_SECONDS = 720.0         # a segment longer than this drops what lies far behind the reader
BEHIND_SECONDS = 60.0        # ... keeping this much behind the reader
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def find_ffmpeg() -> str | None:
    """FFmpeg for live decoding: $BLINDCUE_FFMPEG, PATH (the installed program adds its own), build/ffmpeg."""
    env = os.environ.get("BLINDCUE_FFMPEG", "")
    if env and os.path.isfile(env):
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    roots = [Path(getattr(sys, "_MEIPASS", "")) / "ffmpeg"] if getattr(sys, "_MEIPASS", None) else []
    here = Path(__file__).resolve()
    roots += [here.parents[2] / "build" / "ffmpeg"]
    for root in roots:
        if (root / exe).is_file():
            return str(root / exe)
    return None


class Segment:
    """Frames decoded from ``start`` onwards (written by one decoder thread, read by voices)."""

    def __init__(self, start: int, limit: int | None = None) -> None:
        self.start = int(start)
        self.limit = limit            # a "head" (prefetched start of a cue) stops after this many frames
        self.length = 0               # frames written (published after the data)
        self.dropped = 0              # leading chunks freed (long files)
        self.done = False             # the decoder ended (end of file, error or cancelled)
        self.eof = False              # it reached the end of the file
        self.error = ""
        self.read_hint = int(start)   # where a voice reads now (for the ahead / behind limits)
        self.last_used = time.monotonic()
        self._chunks: list[np.ndarray | None] = []
        self.cancelled = False
        self.handle: object | None = None

    # ── writer side (decoder thread) ──────────────────────────────────
    def write(self, frames: np.ndarray) -> None:
        """Append int16 frames of shape (n, 2) (a head keeps only up to its limit)."""
        pos = self.length
        offset = 0
        n = len(frames) if self.limit is None else max(0, min(len(frames), self.limit - pos))
        while offset < n:
            idx, inner = divmod(pos, CHUNK)
            while len(self._chunks) <= idx:
                self._chunks.append(np.zeros((CHUNK, 2), dtype=np.int16))
            chunk = self._chunks[idx]
            take = min(CHUNK - inner, n - offset)
            if chunk is not None:
                chunk[inner:inner + take] = frames[offset:offset + take]
            pos += take
            offset += take
        self.length = pos  # publish after the data is in place

    def wants_more(self) -> bool:
        """False while the decoder is far enough ahead of the reader (it waits)."""
        return (self.start + self.length) - self.read_hint < int(AHEAD_SECONDS * RATE)

    def full(self) -> bool:
        """A head that has all it may hold."""
        return self.limit is not None and self.length >= self.limit

    def trim_behind(self) -> None:
        """Free the chunks far behind the reader once a segment is long."""
        if self.length - self.dropped * CHUNK <= int(KEEP_SECONDS * RATE):
            return
        keep_from = self.read_hint - self.start - int(BEHIND_SECONDS * RATE)
        upto = max(0, keep_from // CHUNK)
        for idx in range(self.dropped, min(upto, len(self._chunks))):
            self._chunks[idx] = None
        self.dropped = max(self.dropped, min(upto, len(self._chunks)))

    # ── reader side (audio thread) ─────────────────────────────────────
    def first_frame(self) -> int:
        return self.start + self.dropped * CHUNK

    def end_frame(self) -> int:
        return self.start + self.length

    def covers(self, frame: int) -> bool:
        return self.first_frame() <= frame < self.end_frame()

    def read_into(self, frame: int, out: np.ndarray) -> int:
        """Copy frames from absolute *frame* into *out* (int16 (n, 2)); returns how many were there."""
        rel = frame - self.start
        avail = min(len(out), self.length - rel)
        if rel < self.dropped * CHUNK or avail <= 0:
            return 0
        done = 0
        while done < avail:
            idx, inner = divmod(rel + done, CHUNK)
            chunk = self._chunks[idx] if idx < len(self._chunks) else None
            if chunk is None:
                break
            take = min(CHUNK - inner, avail - done)
            out[done:done + take] = chunk[inner:inner + take]
            done += take
        return done

    def nbytes(self) -> int:
        return sum(c.nbytes for c in self._chunks if c is not None)


DecoderFactory = Callable[["PcmSource", Segment, float], object]


class PcmSource:
    """One file at one tempo, decoded on demand into segments."""

    def __init__(self, path: str, tempo: float = 1.0, keep_pitch: bool = True,
                 decoder: DecoderFactory | None = None) -> None:
        self.path = path
        self.tempo = max(0.5, min(2.0, float(tempo)))
        self.keep_pitch = bool(keep_pitch)
        self.duration_sec: float | None = None   # from FFmpeg's header (refined at the end of the file)
        self.total_frames: int | None = None     # exact, once a segment reached the end
        self.error = ""
        self.users = 0
        self.last_used = time.monotonic()
        self._segments: list[Segment] = []
        self._lock = threading.Lock()
        self._decoder = decoder or ffmpeg_decoder

    @property
    def key(self) -> tuple[str, float, bool]:
        return source_key(self.path, self.tempo, self.keep_pitch)

    def frame_of(self, seconds: float) -> int:
        return max(0, round(float(seconds) * RATE / self.tempo))

    def seconds_of(self, frame: int) -> float:
        return frame * self.tempo / RATE

    def duration_frames(self) -> int | None:
        if self.total_frames is not None:
            return self.total_frames
        return self.frame_of(self.duration_sec) if self.duration_sec else None

    def note_duration(self, seconds: float) -> None:
        if seconds > 0 and self.total_frames is None:
            self.duration_sec = float(seconds)

    def note_end(self, segment: Segment) -> None:
        """A segment reached the end of the file: the exact length is known now."""
        self.total_frames = segment.end_frame()
        self.duration_sec = self.seconds_of(self.total_frames)

    # ── segments ──────────────────────────────────────────────────────
    def _covering(self, frame: int) -> Segment | None:
        best = None
        for seg in self._segments:
            if seg.covers(frame) and (best is None or seg.end_frame() > best.end_frame()):
                best = seg
        return best

    def _arriving(self, frame: int, whole_only: bool = False) -> Segment | None:
        """A decoding segment that will reach *frame* soon (a head only within its limit)."""
        for seg in self._segments:
            if (not seg.done and seg.first_frame() <= frame
                    and frame <= seg.end_frame() + int(NEAR_SECONDS * RATE)
                    and (seg.limit is None or (not whole_only and frame < seg.start + seg.limit))):
                return seg
        return None

    def _spawn(self, seg: Segment) -> Segment:
        """Start the decoder of a new segment (on its own thread; never waits for FFmpeg)."""
        try:
            seg.handle = self._decoder(self, seg, self.seconds_of(seg.start))
        except Exception as exc:  # noqa: BLE001 - a missing FFmpeg must not break the show
            seg.error = str(exc) or exc.__class__.__name__
            seg.done = True
            self.error = seg.error
            logger.error("[MIXER] decoder for %s could not start: %s", self.path, exc)
        return seg

    def ensure(self, frame: int, whole: bool = False) -> Segment | None:
        """The segment that has (or will soon have) *frame*; starts a decoder when none does.

        *whole*: the sound is about to play from here - when only a prefetched
        head has it, the whole file is decoded too, from the head's start, so
        the two hold the same frames and the reader moves over without a seam.
        Never blocks on FFmpeg. Returns None at or after the known end of the file.
        """
        frame = max(0, int(frame))
        total = self.total_frames
        if total is not None and frame >= total:
            return None
        new = None
        with self._lock:
            seg = self._covering(frame) or self._arriving(frame)
            if seg is not None:
                if whole and seg.limit is not None and self._arriving(frame, whole_only=True) is None \
                        and not any(s.limit is None and s.covers(frame) for s in self._segments) \
                        and not self.error:
                    new = Segment(seg.start)
                    self._segments.append(new)
                if new is None:
                    return seg
            elif self.error:
                # Never start FFmpeg again and again on a file it could not read.
                return next((s for s in reversed(self._segments) if s.error), None)
            else:
                seg = new = Segment(frame)
                self._segments.append(new)
        self._spawn(new)
        return seg

    def prefetch(self, frame: int, seconds: float) -> Segment | None:
        """Decode *seconds* from *frame* ahead of time (the start of a cue before its GO)."""
        frame = max(0, int(frame))
        with self._lock:
            if self._covering(frame) is not None or self._arriving(frame) is not None:
                return None
            seg = Segment(frame, limit=max(CHUNK // 10, int(seconds * RATE)))
            self._segments.append(seg)
        return self._spawn(seg)

    def read(self, frame: int, out: np.ndarray) -> tuple[int, str]:
        """Fill *out* (int16 (n, 2)) from *frame*: (frames copied, state).

        State: "ok" (all there), "wait" (the decoder is behind: try again),
        "end" (the file ends inside or before this block), "error". A block
        may come from two segments (a head, then the whole file).
        """
        frame = int(frame)
        n = len(out)
        got_total = 0
        while got_total < n:
            at = frame + got_total
            total = self.total_frames
            if total is not None and at >= total:
                return got_total, "end"
            seg = self.ensure(at)
            if seg is None:
                return got_total, "end" if (not self.error or got_total or self._has_audio()) else "error"
            seg.read_hint = at
            seg.last_used = self.last_used = time.monotonic()
            got = seg.read_into(at, out[got_total:])
            got_total += got
            if got:
                continue  # all there, or this segment ends inside the block: another one may go on
            if seg.done and seg.eof and at >= seg.end_frame():
                return got_total, "end"
            if seg.done and seg.error:
                # A later segment failed (a seek past the end of a damaged file): say end, not error,
                # when the file played before; a file that never decoded is an error.
                return got_total, "end" if (self.total_frames or self._has_audio()) else "error"
            return got_total, "wait"
        return got_total, "ok"

    def available(self, frame: int) -> bool:
        """Frames at *frame* are decoded (or the file ends there)."""
        total = self.total_frames
        if total is not None and frame >= total:
            return True
        with self._lock:
            return self._covering(int(frame)) is not None

    def _has_audio(self) -> bool:
        return any(s.length > 0 for s in self._segments)

    def prune(self, keep_frames: tuple[int, ...] | list[int] = ()) -> None:
        """Forget segments nobody read for a while (their decoders are stopped).

        *keep_frames*: where voices of this file stand (a paused one reads
        nothing, but must find its sound again when it resumes).
        """
        now = time.monotonic()
        with self._lock:
            for seg in list(self._segments):
                if seg.limit is not None or any(seg.first_frame() <= f <= seg.end_frame() for f in keep_frames):
                    continue  # heads stay: they make the next GO start at once
                if now - seg.last_used > 20.0 and len(self._segments) > 1:
                    seg.cancelled = True
                    self._segments.remove(seg)

    def nbytes(self) -> int:
        return sum(s.nbytes() for s in list(self._segments))

    def close(self) -> None:
        """Stop every decoder and free the memory."""
        with self._lock:
            for seg in self._segments:
                seg.cancelled = True
                handle = seg.handle
                if handle is not None and hasattr(handle, "cancel"):
                    try:
                        handle.cancel()
                    except Exception:
                        logger.debug("[MIXER] cancel failed", exc_info=True)
            self._segments.clear()


def source_key(path: str, tempo: float, keep_pitch: bool) -> tuple[str, float, bool]:
    tempo = round(max(0.5, min(2.0, float(tempo))), 3)
    return (os.path.normcase(os.path.abspath(path)), tempo, bool(keep_pitch) if tempo != 1.0 else True)


# ── FFmpeg decoder ───────────────────────────────────────────────────────

def ffmpeg_command(ffmpeg: str, path: str, start_sec: float, tempo: float, keep_pitch: bool) -> list[str]:
    cmd = [ffmpeg, "-nostdin", "-hide_banner", "-nostats", "-loglevel", "info"]
    if start_sec > 0.0005:
        cmd += ["-ss", f"{start_sec:.4f}"]
    cmd += ["-i", path, "-vn", "-sn", "-dn", "-map", "0:a:0", "-ac", "2"]
    if abs(tempo - 1.0) > 1e-6:
        if keep_pitch:
            cmd += ["-af", f"aresample={RATE},atempo={tempo:.4f}"]
        else:
            cmd += ["-af", f"aresample={RATE},asetrate={round(RATE * tempo)},aresample={RATE}"]
    cmd += ["-ar", str(RATE), "-f", "s16le", "-acodec", "pcm_s16le", "-"]
    return cmd


class _FfmpegDecoder:
    """One FFmpeg process feeding one segment, on its own daemon thread."""

    def __init__(self, source: PcmSource, segment: Segment, start_sec: float) -> None:
        self._source, self._segment = source, segment
        self._start_sec = start_sec
        self._proc: subprocess.Popen | None = None
        self._lines: list[str] = []
        self._thread = threading.Thread(target=self._run, name="mixer-decoder", daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._segment.cancelled = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                logger.debug("[MIXER] kill failed", exc_info=True)

    def _read_stderr(self, stream) -> None:
        try:
            for raw in iter(stream.readline, b""):
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                self._lines.append(line)
                del self._lines[:-12]
                match = _DURATION_RE.search(line)
                if match and self._source.duration_sec is None:
                    h, m, s = match.groups()
                    self._source.note_duration(int(h) * 3600 + int(m) * 60 + float(s))
        except Exception:
            logger.debug("[MIXER] stderr reader ended", exc_info=True)

    def _run(self) -> None:
        seg, src = self._segment, self._source
        try:
            ffmpeg = find_ffmpeg()
            if ffmpeg is None:
                raise FileNotFoundError("FFmpeg not found")
            if not os.path.isfile(src.path):
                raise FileNotFoundError(src.path)
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            self._proc = subprocess.Popen(
                ffmpeg_command(ffmpeg, src.path, self._start_sec, src.tempo, src.keep_pitch),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                bufsize=0, creationflags=flags)
            err_thread = threading.Thread(target=self._read_stderr, args=(self._proc.stderr,), daemon=True)
            err_thread.start()
            stdout = self._proc.stdout
            rest = b""
            first = True
            while not seg.cancelled:
                while not seg.wants_more() and not seg.cancelled:
                    seg.trim_behind()
                    time.sleep(0.05)
                data = stdout.read(1 << 15 if first else 1 << 16)  # a small first read: the start comes sooner
                first = False
                if not data:
                    break
                if rest:
                    data = rest + data
                usable = len(data) - len(data) % 4
                rest = data[usable:]
                if usable:
                    seg.write(np.frombuffer(data[:usable], dtype=np.int16).reshape(-1, 2))
                    seg.trim_behind()
                if seg.full():
                    return  # a head has what it needs (FFmpeg is stopped in finally)
            if seg.cancelled:
                return
            code = self._proc.wait(timeout=5)
            err_thread.join(timeout=1.0)
            if seg.length == 0 and code != 0:
                seg.error = self._lines[-1] if self._lines else f"ffmpeg exit {code}"
                src.error = src.error or seg.error
                logger.error("[MIXER] FFmpeg could not decode %s: %s", src.path, seg.error)
            else:
                seg.eof = True
                src.note_end(seg)
        except Exception as exc:  # noqa: BLE001 - reported to the player as an error
            seg.error = str(exc) or exc.__class__.__name__
            src.error = src.error or seg.error
            logger.error("[MIXER] decoding %s failed: %s", src.path, exc)
        finally:
            seg.done = True
            proc = self._proc
            if proc is not None and proc.poll() is None:
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:
                    logger.debug("[MIXER] kill failed", exc_info=True)


def ffmpeg_decoder(source: PcmSource, segment: Segment, start_sec: float) -> object:
    return _FfmpegDecoder(source, segment, start_sec)
