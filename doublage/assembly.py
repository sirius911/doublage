"""Assemblage de la nouvelle bande son : chaque phrase placée à son timecode."""

from dataclasses import dataclass

import numpy as np


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
