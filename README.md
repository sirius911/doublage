# Doublage

Remplace la voix d'un tutoriel vidéo par une voix de synthèse (Pocket TTS), à partir de la transcription
du serveur Whisper de l'établissement. Voir [SPEC.md](SPEC.md) pour le descriptif et [PLAN.md](PLAN.md) pour l'avancement.

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

La vidéo doublée est créée à côté de l'original (`ma_video_double.mp4`). Les fichiers de travail
(audio extrait, `segments.json`, une piste par phrase) sont dans `data/ma_video/`.

### Interface web en local

```bash
.venv/bin/doublage utilisateur ajouter moi
DOUBLAGE_SIMULER=1 .venv/bin/doublage serveur    # transcription et voix factices (ffmpeg requis)
```

Puis ouvrir http://127.0.0.1:8000.

## Tests

```bash
.venv/bin/pytest            # tests rapides (Whisper et voix simulés)
.venv/bin/pytest -m tts     # essai réel de Pocket TTS (télécharge le modèle)
```

## Déploiement sur la VM svp-recvoc-a3p

### Principe : un stockage Podman dédié

La VM est partagée : `scribe` (Podman sans droits root, compte `lorcyr`) et `ce-transcripteur-v2`.
Le stockage Podman de `lorcyr` est sur `/home` (10 Go), trop petit pour l'image de doublage (~3 Go avec le
modèle). Doublage utilise donc **son propre stockage Podman**, toujours sans droits root :

| Élément | Emplacement |
|---|---|
| Code (clone du dépôt), `.env` | `/srv/apps/doublage` |
| Données (vidéos, projets, comptes) | `/srv/apps/doublage/data` |
| Images, conteneur, volume du modèle | `/var/lib/containers/doublage/storage` (197 Go libres) |
| Fichiers temporaires de construction | `/var/lib/containers/doublage/tmp` |
| État d'exécution | `/run/user/1002/doublage/` |

Ce stockage est sélectionné par `deploiement/podman-doublage`, qui positionne `XDG_CONFIG_HOME` sur
`deploiement/config` : Podman y lit `containers/storage.conf` (emplacement du stockage) et
`containers/containers.conf` (état d'exécution et verrous séparés) comme configuration utilisateur, et y range
ses réseaux CNI. (`CONTAINERS_STORAGE_CONF` ne convient pas : en mode sans root, Podman ignore alors
`graphroot` et `runroot`, constaté sur la VM.) Sans ce lanceur, `podman` continue d'utiliser le stockage
habituel : **scribe n'est pas touché**, la configuration globale de Podman non plus, et
`/var/lib/containers/storage` (stockage de root) n'est jamais utilisé.

Toutes les commandes Podman de doublage passent donc par le lanceur :

```bash
cd /srv/apps/doublage
deploiement/podman-doublage podman ps
deploiement/podman-doublage podman-compose up -d --build
```

### 1. Vérifications préalables (compte lorcyr, aucune modification)

```bash
bash <<'EOF'
echo "== Noyau (overlay natif sans root à partir de 5.13, sinon fuse-overlayfs)"; uname -r
echo "== Réglage overlay du stockage actuel"; podman info --format '{{.Store.GraphDriverName}} {{json .Store.GraphOptions}}'
echo "== Réseau Podman"; podman info --format '{{.Host.NetworkBackend}}'
echo "== Droits et étiquettes"; ls -ldZ /var/lib/containers /srv /srv/apps 2>&1
echo "== XFS ftype (doit valoir 1)"; xfs_info /var/lib/containers 2>/dev/null | grep -o 'ftype=[01]'
echo "== Linger (démarrage des services utilisateur sans session)"; loginctl show-user lorcyr -p Linger
echo "== Plages subuid/subgid"; grep '^lorcyr:' /etc/subuid /etc/subgid
EOF
```

À reporter avant la suite : si le noyau est en 4.18 (RHCK) ou si le stockage actuel utilise
`fuse-overlayfs`, décommenter `mount_program` dans `deploiement/storage.conf`.

### 2. Préparation par un administrateur (root)

```bash
sudo bash <<'EOF'
set -e
install -d -m 0755 /srv/apps
restorecon -v /srv/apps          # /srv/apps était en unlabeled_t (constaté le 2026-10-27)
install -d -o lorcyr -g lorcyr -m 0755 /srv/apps/doublage
install -d -o lorcyr -g lorcyr -m 0700 /var/lib/containers/doublage \
  /var/lib/containers/doublage/storage /var/lib/containers/doublage/tmp
# SELinux : le stockage dédié reçoit les mêmes étiquettes que /var/lib/containers/storage
semanage fcontext -a -e /var/lib/containers/storage /var/lib/containers/doublage/storage
restorecon -R -v /var/lib/containers/doublage
matchpathcon /var/lib/containers/doublage/storage/overlay   # attendu : container_ro_file_t
loginctl enable-linger lorcyr
ls -ldZ /var/lib/containers /var/lib/containers/doublage /var/lib/containers/doublage/storage /srv/apps/doublage
EOF
```

Constaté sur la VM : noyau UEK 5.4, réseau CNI, `/var/lib/containers` en 0755 (traversable par `lorcyr`),
XFS `ftype=1`, linger déjà actif, plages subuid/subgid présentes.

### 3. Installation et construction (compte lorcyr)

```bash
bash <<'EOF'
set -e
cd /srv/apps
[ -d doublage/.git ] || git clone https://github.com/sirius911/doublage.git doublage
cd doublage && git checkout dev && git pull
cp -n .env.exemple .env
mkdir -p data
chmod +x deploiement/podman-doublage
echo "== Stockage doublage (attendu : /var/lib/containers/doublage/storage)"
deploiement/podman-doublage podman info --format '{{.Store.GraphRoot}}  {{.Store.RunRoot}}'
echo "== Mode overlay retenu (natif ou fuse-overlayfs)"
deploiement/podman-doublage podman info --format '{{json .Store.GraphStatus}}'
echo "== Stockage habituel (attendu : inchangé, ~/.local/share/containers/storage)"
podman info --format '{{.Store.GraphRoot}}'
deploiement/podman-doublage podman build -t localhost/doublage:latest -f Containerfile .
deploiement/podman-doublage podman images
echo "== scribe tourne toujours"; podman ps --format '{{.Names}}  {{.Status}}'
EOF
```

### 4. Premier essai en ligne de commande

Avec une vidéo courte (1 à 2 minutes) copiée dans `/srv/apps/doublage/data/` :

```bash
bash <<'EOF'
cd /srv/apps/doublage
time deploiement/podman-doublage podman run --rm --env-file .env --cpus 2 --memory 4g \
  --userns keep-id:uid=1000,gid=1000 \
  -v /srv/apps/doublage/data:/data:Z \
  -v doublage-modeles:/home/doublage/.cache/huggingface \
  localhost/doublage:latest doublage traiter /data/ma_video.mp4
ls -lh data/
EOF
```

`--userns keep-id:uid=1000,gid=1000` fait correspondre l'utilisateur du conteneur au compte `lorcyr` :
les fichiers produits lui appartiennent. La vidéo doublée est créée à côté de l'original
(`ma_video_double.mp4`). Le premier lancement télécharge le modèle Pocket TTS (quelques centaines de Mo),
conservé ensuite dans le volume `doublage-modeles` du stockage dédié.

### 5. Application web et démarrage avec la VM

```bash
bash <<'EOF'
set -e
cd /srv/apps/doublage
deploiement/podman-doublage podman-compose up -d
mkdir -p ~/.config/systemd/user
cp deploiement/doublage@.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now doublage@doublage
systemctl --user status doublage@doublage --no-pager | head -5
curl --noproxy '*' -s http://127.0.0.1:8091/sante
EOF
```

L'application répond sur `http://10.1.147.219:8091/`. Conteneur, réseau et volume sont nommés `doublage…`.
Le service systemd est nécessaire parce que `podman-restart.service` ne connaît que le stockage par défaut.
C'est un modèle (`doublage@<nom>`, `<nom>` = `DOUBLAGE_NOM` de `.env`), pour pouvoir faire tourner une
instance de test à côté de la production.

### Mises à jour

```bash
/srv/apps/doublage/deploiement/mettre-a-jour
```

Le script récupère le code (`git pull`), construit la nouvelle image pendant que l'ancienne version tourne,
remplace le conteneur, relance le service et vérifie que l'application répond (sinon, il affiche le journal).
Les données et le cache du modèle sont conservés.

### Voix créées à partir d'un échantillon

Le modèle de clonage de voix de Pocket TTS est en accès restreint sur Hugging Face (les voix prédéfinies,
comme estelle, ne le sont pas) : sans lui, l'ajout d'une voix fonctionne mais sa synthèse échoue
(« We could not download the weights for the model with voice cloning »).

1. Avec un compte Hugging Face, accepter les conditions d'utilisation sur
   https://huggingface.co/kyutai/pocket-tts (notamment : pas de clonage sans le consentement de la personne).
2. Créer un jeton en **lecture** (Settings > Access Tokens) et l'ajouter dans `.env` : `HF_TOKEN=hf_...`
   (et commenter `HF_HUB_OFFLINE=1` le temps du téléchargement, s'il est actif).
3. `deploiement/mettre-a-jour`, puis générer une phrase avec la voix : les poids sont téléchargés
   (via le proxy) dans le volume du modèle. Seuls des poids descendent : aucun audio ne sort de l'établissement.

## Comptes utilisateurs

Les comptes de l'application web se gèrent en ligne de commande (mots de passe chiffrés avec scrypt,
dans `data/doublage.db`) :

```bash
.venv/bin/doublage utilisateur ajouter alice     # crée le compte ou change son mot de passe
.venv/bin/doublage utilisateur liste
.venv/bin/doublage utilisateur supprimer alice

# Sur la VM, dans le conteneur :
cd /srv/apps/doublage && deploiement/podman-doublage podman exec -it doublage doublage utilisateur ajouter alice
```
