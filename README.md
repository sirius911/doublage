# Doublage

Remplace la voix d'un tutoriel vidéo par une voix de synthèse (Pocket TTS), à partir de la transcription
du serveur Whisper de l'établissement. Voir [SPEC.md](SPEC.md) pour le descriptif et [PLAN.md](PLAN.md) pour l'avancement.

## Essai en ligne de commande (sans conteneur)

Prérequis : Python 3.11+ et ffmpeg.

```bash
python3 -m venv .venv
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -e ".[tts]" pytest
cp .env.exemple .env          # adapter si besoin

# Essai sans Whisper ni Pocket TTS (voix factice) :
.venv/bin/doublage traiter ma_video.mp4 --simuler

# Essai réel : transcription par le serveur Whisper, voix estelle
.venv/bin/doublage traiter ma_video.mp4
```

La vidéo doublée est créée à côté de l'original (`ma_video_double.mp4`). Les fichiers de travail
(audio extrait, `segments.json`, une piste par phrase) sont dans `data/ma_video/`.

## Tests

```bash
.venv/bin/pytest            # tests rapides (Whisper et voix simulés)
.venv/bin/pytest -m tts     # essai réel de Pocket TTS (télécharge le modèle)
```

## Déploiement avec Podman

```bash
cp .env.exemple .env        # choisir un port libre (ss -ltn) et le dossier de données
mkdir -p /srv/apps/doublage/data
podman-compose up -d --build
```

L'application répond alors sur `http://<VM>:8090/`. Le conteneur, son réseau et ses volumes sont tous
nommés `doublage…`, et limités à 2 processeurs et 4 Go de mémoire, pour ne pas gêner les autres applications.
