"""Assemblage de la nouvelle bande son : chaque phrase placée à son timecode."""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from .segments import Segment, Transcript

# Écart toléré (secondes) : en dessous, la différence ne s'entend pas.
FIT_TOLERANCE = 0.05


class Fit(StrEnum):
    OK = "vert"  # la voix tient dans la durée de la phrase d'origine
    # Corrigé automatiquement : débord sur le silence qui suit, ou légère accélération.
    OVERFLOW = "orange"
    OVERLAP = "rouge"  # même accélérée, elle chevauche la phrase suivante : à reformuler


def _s(seconds: float) -> str:
    return f"{seconds:.1f}".replace(".", ",") + " s"


def speed_factor(segment: Segment, slot_end: float, voice_duration: float, max_speed: float) -> float:
    """Accélération nécessaire pour que la voix finisse avant la phrase suivante, plafonnée à `max_speed`.

    1.0 si la voix tient déjà (au besoin en débordant sur le silence qui suit).
    """
    available = slot_end - segment.start
    if available <= 0 or voice_duration <= available + FIT_TOLERANCE:
        return 1.0
    return min(voice_duration / available, max_speed)


def fit(segment: Segment, slot_end: float, voice_duration: float,
        max_speed: float = 1.0) -> tuple[Fit, str]:
    """La voix synthétique tient-elle dans son créneau ? Renvoie le niveau et une explication.

    `slot_end` : début de la phrase suivante (ou fin de la vidéo pour la dernière).
    """
    voice, original = _s(voice_duration), _s(segment.duration)
    if voice_duration <= segment.duration + FIT_TOLERANCE:
        return Fit.OK, f"La voix ({voice}) tient dans la phrase d'origine ({original})."
    if segment.start + voice_duration - slot_end <= FIT_TOLERANCE:
        return Fit.OVERFLOW, (f"La voix ({voice}) dépasse la phrase d'origine ({original}) "
                              f"mais finit avant la phrase suivante.")
    speed = speed_factor(segment, slot_end, voice_duration, max_speed)
    overlap = segment.start + voice_duration / speed - slot_end
    percent = round((speed - 1) * 100)
    if overlap <= FIT_TOLERANCE:
        return Fit.OVERFLOW, (f"La voix ({voice}) sera accélérée de {percent} % "
                              f"pour finir avant la phrase suivante.")
    accelerated = f"Même accélérée de {percent} %, la voix" if percent > 0 else "La voix"
    return Fit.OVERLAP, (f"{accelerated} ({voice}) déborde de {_s(overlap)} sur la phrase suivante, "
                         f"qui sera décalée : raccourcissez le texte.")


def fit_clips(transcript: Transcript, clips: list[tuple[int, float, np.ndarray]], sample_rate: int,
              max_speed: float, change_tempo) -> tuple[list[tuple[int, float, np.ndarray]], int]:
    """Accélère légèrement les voix qui empiètent sur la phrase suivante. Renvoie (clips, nombre accélérés)."""
    segments = {s.id: s for s in transcript.segments}
    fitted, accelerated = [], 0
    for segment_id, start, audio in clips:
        segment = segments.get(segment_id)
        speed = 1.0
        if segment is not None:
            speed = speed_factor(segment, transcript.slot_end(segment), len(audio) / sample_rate, max_speed)
        if speed > 1.005:
            audio = change_tempo(audio, sample_rate, speed)
            accelerated += 1
        fitted.append((segment_id, start, audio))
    return fitted, accelerated


@dataclass
class Placement:
    segment_id: int
    start: float  # moment où la phrase commence réellement (secondes)
    duration: float  # durée de la voix synthétique (secondes)
    delay: float  # retard par rapport au timecode d'origine (secondes)


def assemble(clips: list[tuple[int, float, np.ndarray]], total_duration: float,
             sample_rate: int) -> tuple[np.ndarray, list[Placement]]:
    """Place chaque clip (id, début souhaité, audio) sur une piste silencieuse.

    Si une phrase déborde sur la suivante, la suivante est décalée juste après pour rester
    intelligible ; le retard est signalé dans les placements.
    """
    track = np.zeros(int(round(total_duration * sample_rate)), dtype=np.float32)
    placements = []
    cursor = 0  # premier échantillon libre
    for segment_id, wanted_start, audio in sorted(clips, key=lambda c: c[1]):
        start = max(int(round(wanted_start * sample_rate)), cursor)
        end = start + len(audio)
        if end > len(track):
            track = np.concatenate([track, np.zeros(end - len(track), dtype=np.float32)])
        track[start:end] += audio
        cursor = end
        placements.append(Placement(
            segment_id=segment_id, start=start / sample_rate,
            duration=len(audio) / sample_rate, delay=start / sample_rate - wanted_start,
        ))
    return track, placements
