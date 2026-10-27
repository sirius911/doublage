"""Catalogue des voix proposées pour les projets."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Voice:
    id: str
    label: str
    ref: str  # ce que reçoit le moteur : nom prédéfini de Pocket TTS ou chemin d'un fichier


class VoiceCatalog:
    """Voix prédéfinies de Pocket TTS retenues dans la configuration (DOUBLAGE_TTS_VOICES)."""

    def __init__(self, predefined: list[str], default: str):
        self.predefined = [v for v in dict.fromkeys(predefined) if v]
        self.default = default

    def list(self) -> list[Voice]:
        return [Voice(name, name.replace("_", " ").title(), name) for name in self.predefined]

    def get(self, voice_id: str | None) -> Voice | None:
        return next((v for v in self.list() if v.id == voice_id), None)

    def for_project(self, voice_id: str | None) -> Voice:
        """Voix d'un projet ; celle par défaut s'il n'en a pas choisi ou si elle a disparu du catalogue."""
        voice = self.get(voice_id) or self.get(self.default)
        if voice is None:  # voix par défaut absente de la liste : elle reste utilisable
            voice = Voice(self.default, self.default.replace("_", " ").title(), self.default)
        return voice
