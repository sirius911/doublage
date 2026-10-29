"""Sous-titres (SRT, WebVTT) à partir du texte corrigé des phrases."""

from .segments import Transcript, display_text


def _timestamp(seconds: float, separator: str) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{separator}{ms:03d}"


# Sous-titres incrustés : polices installées dans le conteneur (Containerfile) et tailles proposées.
# La taille suit le gabarit des sous-titres SRT de ffmpeg (288 lignes de haut, quelle que soit la
# définition de la vidéo) : 16, la taille par défaut de ffmpeg, fait environ 5,5 % de la hauteur de l'image.
FONTS = ("DejaVu Sans", "Liberation Sans", "Liberation Serif")
SIZES = {12: "petite", 16: "normale", 20: "grande", 24: "très grande"}
DEFAULT_FONT, DEFAULT_SIZE = FONTS[0], 16


def burn_style(font: str, size: int) -> str:
    """Style ffmpeg (force_style) des sous-titres incrustés."""
    return f"FontName={font},FontSize={size}"


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
