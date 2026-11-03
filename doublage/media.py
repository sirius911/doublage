"""Opérations audio/vidéo via ffmpeg."""

import json
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np


class MediaError(RuntimeError):
    pass


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise MediaError(f"Échec de {cmd[0]} : {result.stderr.strip()[-500:]}")
    return result.stdout


def probe_duration(path: Path) -> float:
    """Durée d'un fichier audio ou vidéo, en secondes."""
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    return float(json.loads(out)["format"]["duration"])


def probe_video(path: Path) -> tuple[int, int, float]:
    """Largeur, hauteur et fréquence d'images (images par seconde) de la vidéo."""
    out = _run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", str(path)])
    stream = json.loads(out)["streams"][0]
    num, _, den = stream["r_frame_rate"].partition("/")
    return int(stream["width"]), int(stream["height"]), float(num) / float(den or 1)


def extract_audio(video: Path, output: Path, sample_rate: int = 16000) -> Path:
    """Extrait la piste audio en WAV mono (format adapté à Whisper)."""
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(video),
        "-vn", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(output),
    ])
    return output


def prepare_voice_sample(source: Path, output: Path, max_seconds: float,
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


def _subtitles_filter(subtitles: Path, style: str | None) -> str:
    # Le filtre est lancé depuis le dossier du SRT : son chemin complet devrait être échappé.
    return f"subtitles={subtitles.name}" + (f":force_style='{style}'" if style else "")


def _image_filters(subtitles: Path | None, style: str | None, masks: str | None) -> str | None:
    """Filtres de l'image : boîtes de masquage d'abord, sous-titres par-dessus."""
    filters = [f for f in (masks, subtitles and _subtitles_filter(subtitles, style)) if f]
    return ",".join(filters) or None


def replace_audio(video: Path, audio: Path, output: Path, subtitles: Path | None = None,
                  threads: int = 2, style: str | None = None, masks: str | None = None,
                  cwd: Path | None = None) -> Path:
    """Remplace la bande son de la vidéo, sans ré-encoder l'image.

    Avec `subtitles` (fichier SRT), les sous-titres sont gravés dans l'image ; avec `masks` (filtres de
    masks.masks_filter), les boîtes de masquage aussi. L'image est alors ré-encodée (H.264, `threads`
    cœurs), ce qui prend bien plus de temps. `style` : police et taille (force_style de ffmpeg).
    ffmpeg est lancé depuis `cwd` (par défaut le dossier du SRT), où se trouvent les fichiers désignés par
    les filtres.
    """
    filters = _image_filters(subtitles, style, masks)
    if filters is None:
        image = ["-c:v", "copy"]
    else:
        image = ["-vf", filters, "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "20", "-pix_fmt", "yuv420p", "-threads", str(threads)]
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(video.resolve()), "-i", str(audio.resolve()),
        "-map", "0:v:0", "-map", "1:a:0", *image, "-c:a", "aac", "-b:a", "160k",
        "-shortest", str(output.resolve()),
    ], cwd=cwd or (subtitles.parent if subtitles else None))
    return output


def subtitle_frame(video: Path, at: float, subtitles: Path, output: Path, style: str | None = None,
                   masks: str | None = None) -> Path:
    """Image (JPEG) de la vidéo à `at` secondes, sous-titres (et boîtes `masks`) gravés comme par
    `replace_audio`.

    La vidéo est lue à partir de `at` : le SRT doit couvrir le tout début (00:00:00), et les boîtes ne
    doivent pas dépendre du temps. Les fichiers désignés par les filtres sont dans le dossier du SRT.
    """
    _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.3f}", "-i", str(video.resolve()),
          "-vf", _image_filters(subtitles, style, masks), "-frames:v", "1", "-q:v", "3", str(output.resolve())],
         cwd=subtitles.parent)
    if not output.exists():
        raise MediaError("Aucune image à cet instant de la vidéo")
    return output
