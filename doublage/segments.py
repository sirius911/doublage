"""Phrases d'une transcription, avec leurs timecodes, et leur enregistrement en JSON."""

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path


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

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class Transcript:
    duration: float
    segments: list[Segment] = field(default_factory=list)

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
