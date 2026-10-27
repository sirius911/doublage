"""Sous-titres (SRT, WebVTT) à partir du texte corrigé des phrases."""

from .segments import Transcript


def _timestamp(seconds: float, separator: str) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{separator}{ms:03d}"


def to_srt(transcript: Transcript) -> str:
    blocks = [
        f"{i}\n{_timestamp(s.start, ',')} --> {_timestamp(s.end, ',')}\n{s.text}\n"
        for i, s in enumerate((s for s in transcript.segments if s.text), 1)
    ]
    return "\n".join(blocks)


def to_vtt(transcript: Transcript) -> str:
    blocks = [
        f"{_timestamp(s.start, '.')} --> {_timestamp(s.end, '.')}\n{s.text}\n"
        for s in transcript.segments if s.text
    ]
    return "WEBVTT\n\n" + "\n".join(blocks)
