"""Synthèse vocale d'une phrase."""

from typing import Protocol

import numpy as np


class Synthesizer(Protocol):
    sample_rate: int

    def synthesize(self, text: str) -> np.ndarray:
        """Renvoie un signal mono flottant (-1..1) à `sample_rate`."""
        ...


class PocketSynthesizer:
    """Pocket TTS (Kyutai), sur processeur. Le modèle et la voix sont chargés une seule fois."""

    def __init__(self, language: str = "french", voice: str = "estelle"):
        from pocket_tts import TTSModel  # import tardif : PyTorch est lourd

        self.model = TTSModel.load_model(language=language)
        self.voice_state = self.model.get_state_for_audio_prompt(voice)
        self.sample_rate = self.model.sample_rate

    def synthesize(self, text: str) -> np.ndarray:
        audio = self.model.generate_audio(self.voice_state, text)
        return audio.numpy().astype(np.float32)


class FakeSynthesizer:
    """Voix simulée (un bip dont la durée dépend de la longueur du texte), pour les tests."""

    def __init__(self, sample_rate: int = 24000, seconds_per_char: float = 0.06):
        self.sample_rate = sample_rate
        self.seconds_per_char = seconds_per_char

    def synthesize(self, text: str) -> np.ndarray:
        n = int(len(text) * self.seconds_per_char * self.sample_rate)
        t = np.arange(n) / self.sample_rate
        return (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
