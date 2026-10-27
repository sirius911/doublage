"""Ligne de commande : `doublage traiter video.mp4`, `doublage serveur`."""

import argparse
from pathlib import Path

from .config import get_settings


def cmd_traiter(args: argparse.Namespace) -> None:
    from .pipeline import dub_video, transcribe_video
    from .transcription import FakeTranscriber, WhisperApiTranscriber
    from .tts import FakeSynthesizer, PocketSynthesizer

    settings = get_settings()
    video: Path = args.video
    output = args.sortie or video.with_name(f"{video.stem}_double{video.suffix}")
    workdir = args.dossier or settings.data_dir / video.stem

    if args.simuler:
        transcriber, synthesizer = FakeTranscriber(), FakeSynthesizer()
    else:
        transcriber = WhisperApiTranscriber(settings.whisper_url, settings.whisper_language,
                                            settings.whisper_model, settings.whisper_timeout)
        print("Chargement de Pocket TTS…")
        synthesizer = PocketSynthesizer(settings.tts_language, settings.tts_voice)

    transcript = transcribe_video(video, workdir, transcriber)
    dub_video(video, transcript, workdir, output, synthesizer)


def cmd_serveur(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("doublage.app:app", host=args.hote, port=args.port)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="doublage", description=__doc__)
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("traiter", help="doubler une vidéo de bout en bout")
    p.add_argument("video", type=Path)
    p.add_argument("-o", "--sortie", type=Path, help="vidéo produite (défaut : <nom>_double.<ext>)")
    p.add_argument("--dossier", type=Path, help="dossier de travail (défaut : data/<nom>)")
    p.add_argument("--simuler", action="store_true",
                   help="sans serveur Whisper ni Pocket TTS (transcription et voix factices)")
    p.set_defaults(func=cmd_traiter)

    p = sub.add_parser("serveur", help="lancer l'application web")
    p.add_argument("--hote", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serveur)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
