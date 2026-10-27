# Doublage

Remplace la voix d'un tutoriel vidéo par une voix de synthèse (Pocket TTS), à partir de la transcription
du serveur Whisper de l'établissement. Voir [SPEC.md](SPEC.md) pour le descriptif et [PLAN.md](PLAN.md) pour l'avancement.

## Premier essai réel sur la VM (dans le conteneur)

C'est l'essai à faire en priorité : il vérifie en une fois la construction de l'image, l'accès au serveur
Whisper et la voix Pocket TTS, dans les conditions de la production. Pas besoin d'installer Python ni
ffmpeg sur la VM : tout est dans l'image.

Pour l'essai, les données vont dans `~/doublage-data` (aucun droit administrateur nécessaire) ;
l'emplacement définitif (par exemple `/srv/apps/doublage`) sera choisi à la mise en service.

```bash
bash <<'EOF'
set -e
cd ~
[ -d doublage ] || git clone https://github.com/sirius911/doublage.git
cd doublage && git checkout dev && git pull
cp -n .env.exemple .env
sed -i "s|^DOUBLAGE_DONNEES=.*|DOUBLAGE_DONNEES=$HOME/doublage-data|" .env
mkdir -p ~/doublage-data
podman build -t localhost/doublage:latest -f Containerfile .
EOF
```

Puis, avec une vidéo courte (1 à 2 minutes) copiée dans `~/doublage-data/` :

```bash
bash <<'EOF'
cd ~/doublage
time podman run --rm --env-file .env --cpus 2 --memory 4g --userns keep-id:uid=1000,gid=1000 -v ~/doublage-data:/data:Z   -v doublage-modeles:/home/doublage/.cache/huggingface   localhost/doublage:latest doublage traiter /data/ma_video.mp4
ls -lh ~/doublage-data/
EOF
```

`--userns keep-id:uid=1000,gid=1000` fait correspondre l'utilisateur du conteneur à votre compte :
les fichiers produits vous appartiennent et vous pouvez déposer des vidéos dans le dossier.

La vidéo doublée est créée à côté de l'original (`ma_video_double.mp4`). Le premier lancement télécharge
le modèle Pocket TTS (quelques centaines de Mo), conservé ensuite dans le volume `doublage-modeles`.

## Essai sur un poste de développement Linux (sans conteneur)

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

`--userns keep-id:uid=1000,gid=1000` fait correspondre l'utilisateur du conteneur à votre compte :
les fichiers produits vous appartiennent et vous pouvez déposer des vidéos dans le dossier.

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

L'application répond alors sur `http://<VM>:8091/`. Le conteneur, son réseau et ses volumes sont tous
nommés `doublage…`, et limités à 2 processeurs et 4 Go de mémoire, pour ne pas gêner les autres applications.

## Comptes utilisateurs

Les comptes de l'application web se gèrent en ligne de commande (mots de passe chiffrés avec scrypt,
dans `data/doublage.db`) :

```bash
.venv/bin/doublage utilisateur ajouter alice     # crée le compte ou change son mot de passe
.venv/bin/doublage utilisateur liste
.venv/bin/doublage utilisateur supprimer alice

# Dans le conteneur :
podman exec -it doublage doublage utilisateur ajouter alice
```
