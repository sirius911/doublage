"""Chaîne complète : vidéo → transcription → voix de synthèse → vidéo doublée."""

import shutil
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

import numpy as np

from . import media
from .assembly import Placement, assemble, fit_clips
from .segments import Segment, Status, Transcript, spoken_text
from .subtitles import to_srt
from .transcription import Transcriber, trim_leading_silence
from .tts import Synthesizer

Progress = Callable[[str], None]


def transcribe_video(video: Path, workdir: Path, transcriber: Transcriber,
                     progress: Progress = print) -> Transcript:
    workdir.mkdir(parents=True, exist_ok=True)
    progress("Extraction de l'audio…")
    audio = media.extract_audio(video, workdir / "original.wav")
    progress("Transcription…")
    transcript = trim_leading_silence(transcriber.transcribe(audio), *media.read_wav(audio))
    transcript.save(workdir / "segments.json")
    progress(f"{len(transcript.segments)} phrases transcrites.")
    return transcript


def clip_path(workdir: Path, segment_id: int) -> Path:
    """Fichier de la voix synthétique d'une phrase."""
    return workdir / "phrases" / f"{segment_id:04d}.wav"


def synthesize_segment(segment: Segment, workdir: Path, synthesizer: Synthesizer):
    """Génère la voix d'une phrase et l'enregistre ; renvoie le signal."""
    audio = synthesizer.synthesize(spoken_text(segment.text))
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


def reset_voices(workdir: Path) -> None:
    """Efface les voix de toutes les phrases (changement de voix du projet) ; le texte est conservé."""
    shutil.rmtree(workdir / "phrases", ignore_errors=True)
    transcript_path = workdir / "segments.json"
    if transcript_path.exists():
        transcript = Transcript.load(transcript_path)
        for segment in transcript.segments:
            segment.status = Status.TRANSCRIBED
        transcript.save(transcript_path)


def burned_subtitles_marker(output: Path) -> Path:
    """Témoin : la vidéo doublée `output` a ses sous-titres gravés dans l'image."""
    return output.with_name(output.stem + ".sous-titres")


def dubbed_voice_path(output: Path) -> Path:
    """Nom de la voix avec laquelle la vidéo doublée `output` a été générée."""
    return output.with_name(output.stem + ".voix")


# Fondus aux bords d'un extrait du son d'origine, pour éviter les claquements.
FADE_SECONDS = 0.01


def original_clip(original: np.ndarray, sample_rate: int, transcript: Transcript,
                  segment: Segment) -> np.ndarray:
    """Son d'origine d'une phrase, borné au début de la phrase suivante, avec de courts fondus."""
    end = min(segment.end, transcript.slot_end(segment))
    clip = original[int(round(segment.start * sample_rate)):int(round(end * sample_rate))].copy()
    n = min(int(FADE_SECONDS * sample_rate), len(clip) // 2)
    if n:
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
        clip[:n] *= ramp
        clip[-n:] *= ramp[::-1]
    return clip


def _original_audio(video: Path, workdir: Path, sample_rate: int) -> np.ndarray:
    """Son d'origine de la vidéo à la fréquence de la synthèse (extrait une fois par projet)."""
    path = workdir / f"original-{sample_rate}.wav"
    if not path.exists():
        media.extract_audio(video, path, sample_rate)
    return media.read_wav(path)[0]


def _render(video: Path, transcript: Transcript, clips: list[tuple[int, float, np.ndarray]],
            sample_rate: int, workdir: Path, output: Path, progress: Progress,
            max_speed: float, burn_subtitles: bool = False, threads: int = 2,
            min_speed: float = 1.0, subtitle_style: str | None = None) -> list[Placement]:
    clips, accelerated, slowed = fit_clips(transcript, clips, sample_rate, max_speed, media.change_tempo,
                                           min_speed)
    if accelerated:
        progress(f"{accelerated} phrase(s) légèrement accélérée(s) pour tenir dans leur créneau.")
    if slowed:
        progress(f"{slowed} phrase(s) légèrement ralentie(s) pour mieux suivre l'original.")
    progress("Assemblage de la bande son…")
    total = max(transcript.duration, media.probe_duration(video))
    track, placements = assemble(clips, total, sample_rate)
    voice = media.write_wav(workdir / "doublage.wav", track, sample_rate)

    if burn_subtitles:
        # Timecodes des phrases d'origine, comme les sous-titres téléchargeables.
        subtitles = workdir / "sous-titres.srt"
        subtitles.write_text(to_srt(transcript), encoding="utf-8")
        progress("Création de la vidéo doublée, sous-titres incrustés (ré-encodage de l'image)…")
        media.replace_audio(video, voice, output, subtitles, threads, subtitle_style)
    else:
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
              max_speed: float = 1.0, min_speed: float = 1.0) -> list[Placement]:
    """Doublage d'un seul tenant (ligne de commande) : toutes les phrases sont synthétisées."""
    clips = []
    for i, seg in enumerate(transcript.segments, 1):
        if not seg.text:
            continue
        progress(f"Synthèse de la phrase {i}/{len(transcript.segments)}…")
        audio = synthesize_segment(seg, workdir, synthesizer)
        seg.status = Status.SYNTHESIZED
        clips.append((seg.id, seg.start, audio))
    transcript.save(workdir / "segments.json")
    return _render(video, transcript, clips, synthesizer.sample_rate, workdir, output, progress, max_speed,
                   min_speed=min_speed)


def dub_project(video: Path, workdir: Path, output: Path, synthesizer: Synthesizer,
                progress: Progress = print, max_speed: float = 1.0,
                synthesis_lock: AbstractContextManager = nullcontext(),
                transcript_lock: AbstractContextManager = nullcontext(),
                burn_subtitles: bool = False, threads: int = 2, voice_label: str = "",
                min_speed: float = 1.0, subtitle_style: str | None = None) -> list[Placement]:
    """Doublage d'un projet corrigé dans l'éditeur.

    Seules les phrases sans voix à jour sont (re)générées ; les autres reprennent la voix déjà
    écoutée et validée. Les phrases marquées « voix d'origine » gardent le son de la vidéo ; les phrases
    effacées (texte vide) restent silencieuses. Les verrous permettent de corriger le texte pendant le traitement.
    `burn_subtitles` grave le texte corrigé dans l'image (ré-encodage sur `threads` cœurs), dans le style
    `subtitle_style` (police et taille, voir subtitles.burn_style).
    `voice_label` (nom de la voix) est noté à côté de la vidéo, pour l'afficher.
    """
    transcript_path = workdir / "segments.json"
    with transcript_lock:
        todo = [s for s in Transcript.load(transcript_path).segments if s.text and not s.keep_original
                and (s.status != Status.SYNTHESIZED or not clip_path(workdir, s.id).exists())]
    for i, seg in enumerate(todo, 1):
        progress(f"Synthèse de la phrase {i}/{len(todo)}…")
        with synthesis_lock:
            synthesize_segment(seg, workdir, synthesizer)
        with transcript_lock:
            mark_synthesized(transcript_path, seg)

    with transcript_lock:
        transcript = Transcript.load(transcript_path)
    sample_rate = synthesizer.sample_rate
    clips = []
    kept = [s for s in transcript.segments if s.text and s.keep_original]
    for seg in transcript.segments:
        if seg.text and not seg.keep_original:
            audio, sample_rate = media.read_wav(clip_path(workdir, seg.id))
            clips.append((seg.id, seg.start, audio))
    if kept:
        progress("Reprise du son d'origine des phrases à garder…")
        original = _original_audio(video, workdir, sample_rate)
        clips += [(s.id, s.start, original_clip(original, sample_rate, transcript, s)) for s in kept]
    partial = output.with_name(output.stem + ".partiel" + output.suffix)
    placements = _render(video, transcript, clips, sample_rate, workdir, partial, progress, max_speed,
                         burn_subtitles, threads, min_speed, subtitle_style)
    partial.replace(output)  # l'ancienne vidéo reste téléchargeable jusqu'au bout
    marker = burned_subtitles_marker(output)
    if burn_subtitles:
        marker.touch()
    else:
        marker.unlink(missing_ok=True)
    dubbed_voice_path(output).write_text(voice_label, encoding="utf-8")
    return placements
