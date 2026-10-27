"""Chaîne complète : vidéo → transcription → voix de synthèse → vidéo doublée."""

from collections.abc import Callable
from pathlib import Path

from . import media
from .assembly import Placement, assemble
from .segments import Segment, Status, Transcript
from .transcription import Transcriber
from .tts import Synthesizer

Progress = Callable[[str], None]


def transcribe_video(video: Path, workdir: Path, transcriber: Transcriber,
                     progress: Progress = print) -> Transcript:
    workdir.mkdir(parents=True, exist_ok=True)
    progress("Extraction de l'audio…")
    audio = media.extract_audio(video, workdir / "original.wav")
    progress("Transcription…")
    transcript = transcriber.transcribe(audio)
    transcript.save(workdir / "segments.json")
    progress(f"{len(transcript.segments)} phrases transcrites.")
    return transcript


def clip_path(workdir: Path, segment_id: int) -> Path:
    """Fichier de la voix synthétique d'une phrase."""
    return workdir / "phrases" / f"{segment_id:04d}.wav"


def synthesize_segment(segment: Segment, workdir: Path, synthesizer: Synthesizer):
    """Génère la voix d'une phrase et l'enregistre ; renvoie le signal."""
    audio = synthesizer.synthesize(segment.text)
    path = clip_path(workdir, segment.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    media.write_wav(path, audio, synthesizer.sample_rate)
    return audio


def dub_video(video: Path, transcript: Transcript, workdir: Path, output: Path,
              synthesizer: Synthesizer, progress: Progress = print) -> list[Placement]:
    clips = []
    for i, seg in enumerate(transcript.segments, 1):
        progress(f"Synthèse de la phrase {i}/{len(transcript.segments)}…")
        audio = synthesize_segment(seg, workdir, synthesizer)
        seg.status = Status.SYNTHESIZED
        clips.append((seg.id, seg.start, audio))
    transcript.save(workdir / "segments.json")

    progress("Assemblage de la bande son…")
    total = max(transcript.duration, media.probe_duration(video))
    track, placements = assemble(clips, total, synthesizer.sample_rate)
    voice = media.write_wav(workdir / "doublage.wav", track, synthesizer.sample_rate)

    progress("Création de la vidéo doublée…")
    media.replace_audio(video, voice, output)
    late = [p for p in placements if p.delay > 0.5]
    if late:
        progress(f"Attention : {len(late)} phrase(s) décalée(s) de plus de 0,5 s "
                 f"(retard max {max(p.delay for p in late):.1f} s).")
    progress(f"Vidéo doublée : {output}")
    return placements
