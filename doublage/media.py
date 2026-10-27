"""Opérations audio/vidéo via ffmpeg."""

import json
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np


class MediaError(RuntimeError):
    pass


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise MediaError(f"Échec de {cmd[0]} : {result.stderr.strip()[-500:]}")
    return result.stdout


def probe_duration(path: Path) -> float:
    """Durée d'un fichier audio ou vidéo, en secondes."""
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    return float(json.loads(out)["format"]["duration"])


def extract_audio(video: Path, output: Path, sample_rate: int = 16000) -> Path:
    """Extrait la piste audio en WAV mono (format adapté à Whisper)."""
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(video),
        "-vn", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(output),
    ])
    return output


def prepare_voice_sample(source: Path, output: Path, max_seconds: float = 30,
                         sample_rate: int = 24000) -> Path:
    """Échantillon de voix (fichier audio ou vidéo) en WAV mono, limité à ses `max_seconds` premières secondes."""
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(source), "-t", str(max_seconds),
        "-vn", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(output),
    ])
    return output


def write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> Path:
    """Écrit un signal flottant (-1..1) mono en WAV 16 bits."""
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(pcm.tobytes())
    return path


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Lit un WAV mono 16 bits ; renvoie (signal flottant, fréquence)."""
    with wave.open(str(path), "rb") as f:
        frames = f.readframes(f.getnframes())
        return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32767, f.getframerate()


def wav_duration(path: Path) -> float:
    """Durée d'un WAV (secondes), lue dans l'en-tête sans charger le signal."""
    with wave.open(str(path), "rb") as f:
        return f.getnframes() / f.getframerate()


def change_tempo(audio: np.ndarray, sample_rate: int, speed: float) -> np.ndarray:
    """Accélère un signal sans changer la hauteur de la voix (filtre atempo de ffmpeg)."""
    with tempfile.TemporaryDirectory() as tmp:
        source, result = Path(tmp) / "avant.wav", Path(tmp) / "apres.wav"
        write_wav(source, audio, sample_rate)
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(source),
              "-filter:a", f"atempo={speed:.4f}", "-ar", str(sample_rate), str(result)])
        return read_wav(result)[0]


def replace_audio(video: Path, audio: Path, output: Path) -> Path:
    """Remplace la bande son de la vidéo, sans ré-encoder l'image."""
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        "-shortest", str(output),
    ])
    return output
