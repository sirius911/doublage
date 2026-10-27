"""Configuration lue depuis les variables d'environnement (préfixe DOUBLAGE_) ou un fichier .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOUBLAGE_", env_file=".env", extra="ignore")

    # Dossier où sont rangés les projets (une vidéo = un sous-dossier).
    data_dir: Path = Path("data")

    # Essai sans serveur Whisper ni Pocket TTS (transcription et voix factices), par ex. sur un poste
    # de développement.
    simuler: bool = False

    # Serveur Whisper interne (API compatible OpenAI).
    whisper_url: str = "http://10.1.147.251:30000/v1/audio/transcriptions"
    whisper_language: str = "fr"
    # Nom du modèle à transmettre au serveur, si celui-ci l'exige (champ `model`).
    whisper_model: str | None = None
    whisper_timeout: float = 900.0

    # Synthèse vocale Pocket TTS.
    tts_language: str = "french"
    tts_voice: str = "estelle"
    # Cœurs utilisés par la synthèse. Sur la VM (cgroups v1, Podman sans root), les limites --cpus
    # du conteneur sont ignorées : c'est ce réglage qui protège les autres applications.
    tts_threads: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
