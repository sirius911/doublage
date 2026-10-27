# Plan d'action

Légende : `[ ]` à faire · `[~]` en cours · `[x]` fait · `[?]` bloqué (voir QUESTIONS.md)

## Choix techniques (validés)
- Serveur : **Python + FastAPI** (Pocket TTS est une bibliothèque Python).
- Interface : **HTML + JavaScript simple** servi par FastAPI (pas d'étape de compilation, facile à maintenir).
- Stockage : un dossier par projet (vidéo, audio, `segments.json`, fichiers générés) + SQLite pour la liste des projets.
- Traitements longs (transcription, synthèse, export) en tâche de fond, avec suivi de progression dans l'interface.
- Déploiement : **Podman + podman-compose 1.0.6** sur la VM (pas de Docker) ; fichier compose simple, compatible avec cette version.
- Tests : pytest, avec une petite vidéo d'exemple et des faux services (Whisper simulé) pour tester sans le vrai serveur.

## Phase 0 — Socle
- [x] Structure du projet Python (`pyproject.toml`, dossier `doublage/`, `tests/`)
- [x] Application FastAPI minimale + page d'accueil
- [x] Configuration par fichier `.env` (adresse du serveur Whisper, dossier de données, modèle TTS, voix)
- [x] Intégration continue GitHub Actions (tests à chaque envoi)
- [x] `Containerfile` + `compose.yml` compatibles Podman (ffmpeg, Pocket TTS version processeur, limite de CPU/mémoire) — image construite sur la VM (1,79 Go)

## Phase 1 — Chaîne de traitement complète en ligne de commande
- [x] Extraction de l'audio de la vidéo (ffmpeg)
- [x] Adaptateur de transcription : interface commune + version « serveur Whisper interne » + version simulée pour les tests
- [x] Format des phrases (`segments.json` : id, début, fin, texte original, texte corrigé, état)
- [~] Synthèse d'une phrase avec Pocket TTS (voix estelle, modèle chargé une seule fois) — code écrit, essai réel à faire (`pytest -m tts`), voir Q5
- [x] Assemblage de la bande son : chaque phrase placée à son timecode, silence ailleurs
- [x] Remplacement de la bande son dans la vidéo (sans ré-encoder l'image)
- [~] Commande `doublage traiter video.mp4` qui enchaîne tout → fonctionne en mode `--simuler` ; essai réel (Whisper + Pocket TTS) à faire depuis la VM

## Phase 2 — Interface web
- [x] Connexion par identifiant / mot de passe (comptes créés en ligne de commande, mots de passe chiffrés)
- [ ] Liste des projets + dépôt d'une vidéo
- [ ] Lancement de la transcription avec barre de progression
- [ ] Éditeur : vidéo en fond, texte de la phrase en cours affiché sur l'image au bon timecode
- [ ] Modification du texte sur l'image et dans la liste des phrases, enregistrement automatique
- [ ] Clic sur une phrase → la vidéo se place au timecode
- [ ] Écoute de l'original / de la voix synthétique d'une phrase ; régénération d'une seule phrase
- [ ] Génération de toutes les phrases + export de la vidéo finale à télécharger

## Phase 3 — Calage et confort d'édition
- [ ] Indicateur par phrase : la voix synthétique tient-elle dans son créneau ? (vert / orange / rouge)
- [ ] Solutions automatiques : accélération légère (limite raisonnable), débord sur le silence suivant
- [ ] Fusionner / couper des phrases, ajuster début et fin
- [ ] Aperçu de la vidéo avec la nouvelle voix avant l'export
- [ ] Export complémentaire : sous-titres (SRT/VTT) et audio seul

## Phase 4 — Mise en service
- [x] Relevé des ressources consommées sur la VM par les applications existantes ; choix du volume de données (ex. `/srv/apps`)
- [~] Stockage Podman rootless dédié (`/var/lib/containers/doublage/storage`), code dans `/srv/apps/doublage` — en place et vérifié (stockage, état d'exécution et verrous séparés de scribe)
- [~] Choix d'un port libre (8091), réseau et volumes dédiés, aucune interférence avec ce-transcripteur-v2 et `scribe` — à vérifier au déploiement
- [ ] Essai réel du serveur Whisper avec l'audio d'une vidéo complète (taille et durée maximales acceptées)
- [~] Documentation d'installation sur la VM (Podman sans droits root ; une préparation initiale par l'administrateur) — écrite, à éprouver
- [ ] Démarrage automatique avec la VM (service systemd utilisateur, `deploiement/doublage.service`)
- [ ] Environnement de test (staging) sur la VM, validé par l'utilisateur
- [ ] Mise en production (uniquement après validation de l'utilisateur)

## Phase 5 — Voix
- [ ] Choix de la voix par projet parmi un catalogue
- [ ] Ajout d'une voix à partir d'un échantillon audio (export en `.safetensors` pour un chargement rapide)
- [ ] Choix du modèle `french` / `french_24l` (rapidité / qualité)

## Idées pour plus tard
- Glossaire de prononciation (noms de logiciels, sigles)
- Conserver les bruits de fond d'origine (clics) sous la nouvelle voix
