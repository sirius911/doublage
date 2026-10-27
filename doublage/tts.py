"""Synthèse vocale d'une phrase."""

from typing import Protocol

import numpy as np


class Synthesizer(Protocol):
    sample_rate: int

    def synthesize(self, text: str) -> np.ndarray:
        """Renvoie un signal mono flottant (-1..1) à `sample_rate`."""
        ...


class Engine(Protocol):
    def voice(self, voice: str) -> Synthesizer:
        """Synthétiseur pour une voix : nom prédéfini de Pocket TTS ou chemin d'un fichier."""
        ...


class PocketVoice:
    def __init__(self, model, voice_state):
        self.model = model
        self.voice_state = voice_state
        self.sample_rate = model.sample_rate

    def synthesize(self, text: str) -> np.ndarray:
        audio = self.model.generate_audio(self.voice_state, text)
        return audio.numpy().astype(np.float32)


class PocketEngine:
    """Pocket TTS (Kyutai), sur processeur. Le modèle est chargé une seule fois ; chaque voix est
    préparée à sa première utilisation puis gardée en mémoire."""

    def __init__(self, language: str = "french", threads: int | None = None):
        import torch  # import tardif : PyTorch est lourd
        from pocket_tts import TTSModel

        if threads:
            torch.set_num_threads(threads)

        self.model = TTSModel.load_model(language=language)
        self._voices: dict[str, PocketVoice] = {}

    def voice(self, voice: str) -> PocketVoice:
        if voice not in self._voices:
            self._voices[voice] = PocketVoice(self.model, self.model.get_state_for_audio_prompt(voice))
        return self._voices[voice]


class FakeSynthesizer:
    """Voix simulée (un bip dont la durée dépend de la longueur du texte), pour les tests."""

    def __init__(self, sample_rate: int = 24000, seconds_per_char: float = 0.06, voice: str = ""):
        self.sample_rate = sample_rate
        self.seconds_per_char = seconds_per_char
        self.voice = voice

    def synthesize(self, text: str) -> np.ndarray:
        n = int(len(text) * self.seconds_per_char * self.sample_rate)
        t = np.arange(n) / self.sample_rate
        return (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


class FakeEngine:
    """Moteur simulé : note les voix demandées."""

    def __init__(self):
        self.voices: list[str] = []

    def voice(self, voice: str) -> FakeSynthesizer:
        self.voices.append(voice)
        return FakeSynthesizer(voice=voice)
