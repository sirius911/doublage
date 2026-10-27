"""Transcription de l'audio en phrases horodatées."""

from pathlib import Path
from typing import Protocol

import httpx

from .segments import Segment, Transcript


class TranscriptionError(RuntimeError):
    pass


class Transcriber(Protocol):
    def transcribe(self, audio: Path) -> Transcript: ...


def parse_verbose_json(data: dict) -> Transcript:
    """Convertit une réponse `verbose_json` (format OpenAI) en Transcript."""
    raw_segments = [r for r in data.get("segments") or [] if (r.get("text") or "").strip()]
    if not raw_segments and (data.get("text") or "").strip():
        raise TranscriptionError("La réponse du serveur ne contient pas de segments horodatés.")
    duration = float(data.get("duration") or (raw_segments[-1]["end"] if raw_segments else 0.0))
    segments = []
    for raw in raw_segments:
        # Whisper renvoie parfois une fin au-delà de la durée réelle (fenêtre de 30 s) : on la borne.
        start = round(min(float(raw["start"]), duration), 3)
        end = round(min(float(raw["end"]), duration), 3)
        text = raw["text"].strip()
        segments.append(Segment(id=len(segments), start=start, end=end, original_text=text, text=text))
    return Transcript(duration=duration, segments=segments)


class WhisperApiTranscriber:
    """Serveur Whisper interne, API compatible OpenAI (`/v1/audio/transcriptions`)."""

    def __init__(self, url: str, language: str = "fr", model: str | None = None,
                 timeout: float = 900.0, client: httpx.Client | None = None):
        self.url = url
        self.language = language
        self.model = model
        # Serveur interne : on ignore les variables http_proxy de la VM, sinon la requête
        # partirait vers le proxy de l'établissement.
        self.client = client or httpx.Client(timeout=timeout, trust_env=False)

    def transcribe(self, audio: Path) -> Transcript:
        fields = {"language": self.language, "response_format": "verbose_json"}
        if self.model:
            fields["model"] = self.model
        try:
            with audio.open("rb") as f:
                response = self.client.post(
                    self.url, data=fields, files={"file": (audio.name, f, "audio/wav")}
                )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise TranscriptionError(f"Le serveur Whisper n'a pas répondu correctement : {e}") from e
        return parse_verbose_json(response.json())


class FakeTranscriber:
    """Transcription simulée, pour les tests et les essais sans serveur Whisper."""

    def __init__(self, phrases: list[tuple[float, float, str]] | None = None):
        self.phrases = phrases

    def transcribe(self, audio: Path) -> Transcript:
        from .media import probe_duration

        duration = probe_duration(audio)
        phrases = self.phrases
        if phrases is None:
            # Une phrase toutes les 4 secondes, sur toute la durée.
            phrases = [(t, min(t + 3.0, duration), f"Phrase numéro {i + 1}.")
                       for i, t in enumerate(range(0, int(duration), 4))]
        return parse_verbose_json({
            "duration": duration,
            "segments": [{"start": s, "end": e, "text": t} for s, e, t in phrases],
        })
