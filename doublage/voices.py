"""Catalogue des voix proposées pour les projets : voix prédéfinies et voix créées à partir d'un échantillon."""

import json
import re
import shutil
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from . import media

SAMPLE_MAX_SECONDS = 30
SAMPLE_MIN_SECONDS = 3


class VoiceError(ValueError):
    pass


@dataclass(frozen=True)
class Voice:
    id: str
    label: str
    ref: str  # ce que reçoit le moteur : nom prédéfini de Pocket TTS ou chemin du WAV de l'échantillon
    added_by: str | None = None  # None : voix prédéfinie
    added: float = 0.0


def _slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:40] or "voix"


class VoiceCatalog:
    """Voix prédéfinies de Pocket TTS retenues dans la configuration (DOUBLAGE_TTS_VOICES), et voix
    ajoutées par les utilisateurs, rangées dans `folder` (un WAV et une fiche JSON par voix)."""

    def __init__(self, predefined: list[str], default: str, folder: Path | None = None):
        self.predefined = [v for v in dict.fromkeys(predefined) if v]
        self.default = default
        self.folder = folder

    def custom(self) -> list[Voice]:
        if self.folder is None or not self.folder.exists():
            return []
        voices = []
        for info_path in self.folder.glob("*.json"):
            info = json.loads(info_path.read_text(encoding="utf-8"))
            voices.append(Voice(info_path.stem, info["nom"], str(info_path.with_suffix(".wav")),
                                info["ajoutee_par"], info["date"]))
        return sorted(voices, key=lambda v: v.label.lower())

    def list(self) -> list[Voice]:
        predefined = [Voice(name, name.replace("_", " ").title(), name) for name in self.predefined]
        return predefined + self.custom()

    def get(self, voice_id: str | None) -> Voice | None:
        return next((v for v in self.list() if v.id == voice_id), None)

    def for_project(self, voice_id: str | None) -> Voice:
        """Voix d'un projet ; celle par défaut s'il n'en a pas choisi ou si elle a disparu du catalogue."""
        voice = self.get(voice_id) or self.get(self.default)
        if voice is None:  # voix par défaut absente de la liste : elle reste utilisable
            voice = Voice(self.default, self.default.replace("_", " ").title(), self.default)
        return voice

    def add(self, name: str, sample: BinaryIO, user: str,
            prepare: Callable[[Path, Path], Path] | None = None) -> Voice:
        """Ajoute une voix à partir d'un fichier audio ou vidéo (seul son début est gardé)."""
        name = " ".join(name.split())
        if not name:
            raise VoiceError("Donnez un nom à la voix.")
        if any(v.label.lower() == name.lower() for v in self.list()):
            raise VoiceError(f"Une voix s'appelle déjà « {name} ».")
        # L'horodatage rend l'identifiant unique : une voix supprimée puis recréée sous le même nom
        # ne reprend pas l'état gardé en mémoire par le moteur.
        voice_id = f"{_slug(name)}-{int(time.time() * 1000)}"
        self.folder.mkdir(parents=True, exist_ok=True)
        source, wav = self.folder / f"{voice_id}.source", self.folder / f"{voice_id}.wav"
        try:
            with source.open("wb") as out:
                shutil.copyfileobj(sample, out, length=1024 * 1024)
            try:
                (prepare or media.prepare_voice_sample)(source, wav)
            except media.MediaError:
                raise VoiceError("Fichier illisible : déposez un enregistrement audio (ou une vidéo).")
            if media.wav_duration(wav) < SAMPLE_MIN_SECONDS:
                raise VoiceError(f"Échantillon trop court : au moins {SAMPLE_MIN_SECONDS} s de parole.")
        except BaseException:
            wav.unlink(missing_ok=True)
            raise
        finally:
            source.unlink(missing_ok=True)
        info = {"nom": name, "ajoutee_par": user, "date": time.time(), "accord": True}
        (self.folder / f"{voice_id}.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        return self.get(voice_id)

    def delete(self, voice_id: str) -> None:
        """Supprime une voix ajoutée (échantillon, fiche et états préparés par le moteur)."""
        if self.folder is None or not (self.folder / f"{voice_id}.json").exists():
            raise KeyError(voice_id)
        for path in self.folder.glob(f"{voice_id}.*"):
            path.unlink()
