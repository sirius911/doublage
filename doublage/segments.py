"""Phrases d'une transcription, avec leurs timecodes, et leur enregistrement en JSON."""

import json
import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path


# Notation dans le texte d'une phrase : [Zimbra|Zimm-bra] s'affiche « Zimbra » (sous-titres) et se
# prononce « Zimm-bra » (voix de synthèse).
NOTATION = re.compile(r"\[([^\[\]|]*)\|([^\[\]|]*)\]")


def display_text(text: str) -> str:
    """Texte des sous-titres : la partie « écrit » des notations."""
    return " ".join(NOTATION.sub(r"\1", text).split())


def spoken_text(text: str) -> str:
    """Texte envoyé à la synthèse : la partie « prononcé » des notations."""
    return " ".join(NOTATION.sub(r"\2", text).split())


def notation_error(text: str) -> bool:
    """Crochet ou barre en dehors d'une notation complète : ils apparaîtraient dans les sous-titres."""
    return any(c in NOTATION.sub("", text) for c in "[]|")


class Status(StrEnum):
    TRANSCRIBED = "transcrite"  # texte issu de Whisper, pas encore de voix
    SYNTHESIZED = "synthetisee"  # voix générée pour le texte actuel
    MODIFIED = "modifiee"  # texte changé depuis la dernière synthèse


@dataclass
class Segment:
    id: int
    start: float  # secondes
    end: float  # secondes
    original_text: str
    text: str
    status: Status = Status.TRANSCRIBED
    keep_original: bool = False  # la vidéo doublée garde le son d'origine de cette phrase
    speed: float | None = None  # vitesse de la voix réglée à la main (None : automatique)

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class Transcript:
    duration: float
    segments: list[Segment] = field(default_factory=list)

    def set_text(self, segment_id: int, text: str) -> Segment:
        """Corrige le texte d'une phrase ; une voix déjà générée devient périmée."""
        segment = next((s for s in self.segments if s.id == segment_id), None)
        if segment is None:
            raise KeyError(segment_id)
        text = " ".join(text.split())
        if text != segment.text:
            segment.text = text
            if segment.status == Status.SYNTHESIZED:
                segment.status = Status.MODIFIED
        return segment

    def slot_end(self, segment: Segment) -> float:
        """Fin du créneau d'une phrase : début de la suivante, ou fin de la vidéo."""
        later = [s.start for s in self.segments if s.start > segment.start]
        return min(later) if later else max(self.duration, segment.end)

    def save(self, path: Path) -> None:
        data = {"duration": self.duration, "segments": [asdict(s) for s in self.segments]}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Transcript":
        data = json.loads(path.read_text(encoding="utf-8"))
        segments = [
            Segment(**{**s, "status": Status(s.get("status", Status.TRANSCRIBED))})
            for s in data["segments"]
        ]
        return cls(duration=data["duration"], segments=segments)
