"""Chaîne complète : vidéo → transcription → voix de synthèse → vidéo doublée."""

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

import numpy as np

from . import media
from .assembly import Placement, assemble, fit_clips
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


def mark_synthesized(transcript_path: Path, segment: Segment) -> Segment | None:
    """Note qu'une voix a été générée pour `segment.text`.

    Le texte a pu être corrigé pendant la synthèse : la voix n'est à jour que s'il est inchangé.
    """
    transcript = Transcript.load(transcript_path)
    current = next((s for s in transcript.segments if s.id == segment.id), None)
    if current is not None:
        current.status = Status.SYNTHESIZED if current.text == segment.text else Status.MODIFIED
        transcript.save(transcript_path)
    return current


def _render(video: Path, transcript: Transcript, clips: list[tuple[int, float, np.ndarray]],
            sample_rate: int, workdir: Path, output: Path, progress: Progress,
            max_speed: float) -> list[Placement]:
    clips, accelerated = fit_clips(transcript, clips, sample_rate, max_speed, media.change_tempo)
    if accelerated:
        progress(f"{accelerated} phrase(s) légèrement accélérée(s) pour tenir dans leur créneau.")
    progress("Assemblage de la bande son…")
    total = max(transcript.duration, media.probe_duration(video))
    track, placements = assemble(clips, total, sample_rate)
    voice = media.write_wav(workdir / "doublage.wav", track, sample_rate)

    progress("Création de la vidéo doublée…")
    media.replace_audio(video, voice, output)
    late = [p for p in placements if p.delay > 0.5]
    if late:
        progress(f"Attention : {len(late)} phrase(s) décalée(s) de plus de 0,5 s "
                 f"(retard max {max(p.delay for p in late):.1f} s).")
    progress(f"Vidéo doublée : {output}")
    return placements


def dub_video(video: Path, transcript: Transcript, workdir: Path, output: Path,
              synthesizer: Synthesizer, progress: Progress = print,
              max_speed: float = 1.0) -> list[Placement]:
    """Doublage d'un seul tenant (ligne de commande) : toutes les phrases sont synthétisées."""
    clips = []
    for i, seg in enumerate(transcript.segments, 1):
        progress(f"Synthèse de la phrase {i}/{len(transcript.segments)}…")
        audio = synthesize_segment(seg, workdir, synthesizer)
        seg.status = Status.SYNTHESIZED
        clips.append((seg.id, seg.start, audio))
    transcript.save(workdir / "segments.json")
    return _render(video, transcript, clips, synthesizer.sample_rate, workdir, output, progress, max_speed)


def dub_project(video: Path, workdir: Path, output: Path, synthesizer: Synthesizer,
                progress: Progress = print, max_speed: float = 1.0,
                synthesis_lock: AbstractContextManager = nullcontext(),
                transcript_lock: AbstractContextManager = nullcontext()) -> list[Placement]:
    """Doublage d'un projet corrigé dans l'éditeur.

    Seules les phrases sans voix à jour sont (re)générées ; les autres reprennent la voix déjà
    écoutée et validée. Les verrous permettent de corriger le texte pendant le traitement.
    """
    transcript_path = workdir / "segments.json"
    with transcript_lock:
        todo = [s for s in Transcript.load(transcript_path).segments
                if s.status != Status.SYNTHESIZED or not clip_path(workdir, s.id).exists()]
    for i, seg in enumerate(todo, 1):
        progress(f"Synthèse de la phrase {i}/{len(todo)}…")
        with synthesis_lock:
            synthesize_segment(seg, workdir, synthesizer)
        with transcript_lock:
            mark_synthesized(transcript_path, seg)

    with transcript_lock:
        transcript = Transcript.load(transcript_path)
    clips, sample_rate = [], synthesizer.sample_rate
    for seg in transcript.segments:
        audio, sample_rate = media.read_wav(clip_path(workdir, seg.id))
        clips.append((seg.id, seg.start, audio))
    partial = output.with_name(output.stem + ".partiel" + output.suffix)
    placements = _render(video, transcript, clips, sample_rate, workdir, partial, progress, max_speed)
    partial.replace(output)  # l'ancienne vidéo reste téléchargeable jusqu'au bout
    return placements
