"""Sous-titres (SRT, WebVTT) à partir du texte corrigé des phrases."""

from .segments import Transcript, display_text


def _timestamp(seconds: float, separator: str) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{separator}{ms:03d}"


def _shown(transcript: Transcript) -> list[tuple[float, float, str]]:
    """Phrases à afficher (début, fin, texte écrit) ; les phrases effacées sont omises."""
    return [(s.start, s.end, display_text(s.text)) for s in transcript.segments if display_text(s.text)]


def to_srt(transcript: Transcript) -> str:
    blocks = [
        f"{i}\n{_timestamp(start, ',')} --> {_timestamp(end, ',')}\n{text}\n"
        for i, (start, end, text) in enumerate(_shown(transcript), 1)
    ]
    return "\n".join(blocks)


def to_vtt(transcript: Transcript) -> str:
    blocks = [
        f"{_timestamp(start, '.')} --> {_timestamp(end, '.')}\n{text}\n"
        for start, end, text in _shown(transcript)
    ]
    return "WEBVTT\n\n" + "\n".join(blocks)
