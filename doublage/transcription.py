"""Transcription de l'audio en phrases horodatées."""

import zlib
from pathlib import Path
from typing import Protocol

import httpx
import numpy as np

from .segments import Segment, Transcript


class TranscriptionError(RuntimeError):
    pass


class Transcriber(Protocol):
    def transcribe(self, audio: Path) -> Transcript: ...


def parse_verbose_json(data: dict) -> Transcript:
    """Convertit une réponse `verbose_json` (format OpenAI) en Transcript."""
    raw_segments = [r for r in data.get("segments") or []
                    if (r.get("text") or "").strip() and not is_hallucination(r["text"])]
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
    transcript = regroup(Transcript(duration=duration, segments=segments))
    # Une boucle répartie sur plusieurs tronçons n'apparaît qu'une fois ceux-ci réunis.
    kept = [s for s in transcript.segments if not is_hallucination(s.text)]
    for i, s in enumerate(kept):
        s.id = i
    return Transcript(duration=duration, segments=kept)


# Seuil de Whisper lui-même : au-delà, le texte est trop répétitif pour être de la parole réelle.
MAX_COMPRESSION_RATIO = 2.4


def is_hallucination(text: str) -> bool:
    """Phrase répétée en boucle (Whisper sur un silence) : le texte se compresse énormément."""
    data = text.strip().encode("utf-8")
    return len(data) > 0 and len(data) / len(zlib.compress(data)) > MAX_COMPRESSION_RATIO


SENTENCE_END = (".", "?", "!", "…")


def regroup(transcript: Transcript, max_duration: float = 15.0, max_gap: float = 1.0) -> Transcript:
    """Réunit les tronçons consécutifs d'une même phrase (Whisper coupe parfois en pleine phrase).

    On ajoute le tronçon suivant tant que le texte ne finit pas par une ponctuation de fin, sans dépasser
    `max_duration` ni enjamber un silence de plus de `max_gap` (la voix resterait calée sur l'image).
    """
    merged: list[Segment] = []
    for s in transcript.segments:
        last = merged[-1] if merged else None
        if (last and not last.text.endswith(SENTENCE_END) and s.start - last.end <= max_gap
                and s.end - last.start <= max_duration):
            last.end = s.end
            last.text = last.original_text = f"{last.text} {s.text}"
        else:
            merged.append(Segment(id=len(merged), start=s.start, end=s.end,
                                  original_text=s.original_text, text=s.text))
    return Transcript(duration=transcript.duration, segments=merged)


def trim_leading_silence(transcript: Transcript, audio: np.ndarray, sample_rate: int,
                         threshold: float = 0.01, min_silence: float = 0.3, margin: float = 0.1) -> Transcript:
    """Recale le début de chaque phrase sur le premier son réel de son créneau.

    Whisper fait souvent commencer une phrase avant la parole, surtout la première (à 0 s alors qu'on ne
    parle qu'à 6 s) : la voix de synthèse partirait trop tôt. Un silence de moins de `min_silence` est
    laissé tel quel ; on garde `margin` avant le premier son. `threshold` : niveau RMS (0..1, ≈ -40 dB)
    par fenêtres de 20 ms.
    """
    window = max(1, int(sample_rate * 0.02))
    for s in transcript.segments:
        part = audio[int(s.start * sample_rate):int(s.end * sample_rate)]
        n = len(part) // window
        if n == 0:
            continue
        rms = np.sqrt(np.mean(part[:n * window].reshape(n, window) ** 2, axis=1))
        loud = np.flatnonzero(rms > threshold)
        if len(loud) == 0:
            continue  # aucun son mesurable : on ne devine pas
        silence = loud[0] * window / sample_rate
        if silence >= min_silence:
            s.start = round(s.start + silence - margin, 3)
    return transcript


class WhisperApiTranscriber:
    """Serveur Whisper interne, API compatible OpenAI (`/v1/audio/transcriptions`)."""

    def __init__(self, url: str, language: str = "fr", model: str | None = None,
                 timeout: float = 900.0, prompt: str | None = None, client: httpx.Client | None = None):
        self.url = url
        self.language = language
        self.model = model
        self.prompt = prompt
        # Serveur interne : on ignore les variables http_proxy de la VM, sinon la requête
        # partirait vers le proxy de l'établissement.
        self.client = client or httpx.Client(timeout=timeout, trust_env=False)

    def transcribe(self, audio: Path) -> Transcript:
        fields = {"language": self.language, "response_format": "verbose_json"}
        if self.model:
            fields["model"] = self.model
        if self.prompt:
            fields["prompt"] = self.prompt
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
