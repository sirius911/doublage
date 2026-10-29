"""Synthèse vocale d'une phrase."""

from pathlib import Path
from typing import Protocol

import numpy as np

# Durée de l'échantillon d'une voix donnée au modèle. Au-delà, la phrase générée est coupée en plein mot
# (mesuré sur la VM : 30 s d'échantillon → coupée vers 5 s ; 20 s → dernier mot tronqué ; 10 et 15 s → complète).
# L'échantillon et la phrase semblent se partager une longueur maximale : on garde de la marge.
VOICE_PROMPT_SECONDS = 10


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

        self.language = language
        self.model = TTSModel.load_model(language=language)
        self._voices: dict[str, PocketVoice] = {}

    def voice(self, voice: str) -> PocketVoice:
        if voice not in self._voices:
            self._voices[voice] = PocketVoice(self.model, self._state(voice))
        return self._voices[voice]

    def _state(self, voice: str):
        """État de la voix. Celui d'un échantillon (WAV) est long à calculer : il est exporté une fois
        en .safetensors à côté du WAV, pour chaque modèle (french, french_24l…), puis relu.

        Seules les `VOICE_PROMPT_SECONDS` premières secondes de l'échantillon sont utilisées (les voix
        ajoutées avant cette limite gardent un échantillon plus long)."""
        sample = Path(voice)
        if sample.suffix != ".wav":
            return self.model.get_state_for_audio_prompt(voice)
        cache = sample.with_name(f"{sample.stem}.{self.language}.{VOICE_PROMPT_SECONDS}s.safetensors")
        if not cache.exists():
            import torch
            from pocket_tts import export_model_state

            from .media import read_wav

            audio, sample_rate = read_wav(sample)
            if sample_rate != self.model.sample_rate:
                raise ValueError(f"Échantillon à {sample_rate} Hz, {self.model.sample_rate} Hz attendus : {sample}")
            prompt = torch.from_numpy(audio[:VOICE_PROMPT_SECONDS * sample_rate].copy())[None]
            partial = cache.with_name(f"{cache.stem}.partiel.safetensors")
            export_model_state(self.model.get_state_for_audio_prompt(prompt), str(partial))
            partial.replace(cache)
        return self.model.get_state_for_audio_prompt(str(cache))


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
