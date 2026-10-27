"""Assemblage de la nouvelle bande son : chaque phrase placée à son timecode."""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from .segments import Segment

# Écart toléré (secondes) : en dessous, la différence ne s'entend pas.
FIT_TOLERANCE = 0.05


class Fit(StrEnum):
    OK = "vert"  # la voix tient dans la durée de la phrase d'origine
    OVERFLOW = "orange"  # elle déborde sur le silence qui suit, sans toucher la phrase suivante
    OVERLAP = "rouge"  # elle chevauche la phrase suivante, qui sera décalée


def _s(seconds: float) -> str:
    return f"{seconds:.1f}".replace(".", ",") + " s"


def fit(segment: Segment, slot_end: float, voice_duration: float) -> tuple[Fit, str]:
    """La voix synthétique tient-elle dans son créneau ? Renvoie le niveau et une explication.

    `slot_end` : début de la phrase suivante (ou fin de la vidéo pour la dernière).
    """
    voice, original = _s(voice_duration), _s(segment.duration)
    if voice_duration <= segment.duration + FIT_TOLERANCE:
        return Fit.OK, f"La voix ({voice}) tient dans la phrase d'origine ({original})."
    overlap = segment.start + voice_duration - slot_end
    if overlap <= FIT_TOLERANCE:
        return Fit.OVERFLOW, (f"La voix ({voice}) dépasse la phrase d'origine ({original}) "
                              f"mais finit avant la phrase suivante.")
    return Fit.OVERLAP, (f"La voix ({voice}) déborde de {_s(overlap)} sur la phrase suivante, "
                         f"qui sera décalée.")


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
