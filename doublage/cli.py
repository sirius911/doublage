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


def cmd_utilisateur(args: argparse.Namespace) -> None:
    import getpass

    from .auth import UserStore

    store = UserStore(get_settings().data_dir / "doublage.db")
    if args.action == "liste":
        for name in store.list_users():
            print(name)
    elif args.action == "supprimer":
        if not store.delete_user(args.nom):
            raise SystemExit(f"Compte inconnu : {args.nom}")
        print(f"Compte supprimé : {args.nom}")
    else:
        password = getpass.getpass("Mot de passe : ")
        if password != getpass.getpass("Confirmation : "):
            raise SystemExit("Les deux mots de passe ne correspondent pas.")
        store.set_user(args.nom, password)
        print(f"Compte enregistré : {args.nom}")


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

    p = sub.add_parser("utilisateur", help="gérer les comptes de l'application web")
    actions = p.add_subparsers(dest="action", required=True)
    actions.add_parser("ajouter", help="créer un compte ou changer son mot de passe").add_argument("nom")
    actions.add_parser("supprimer", help="supprimer un compte").add_argument("nom")
    actions.add_parser("liste", help="lister les comptes")
    p.set_defaults(func=cmd_utilisateur)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
