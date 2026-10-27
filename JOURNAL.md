# Journal

Historique des sessions, la plus récente en haut.

## 2026-10-27 — Phases 0 et 1
- Réponses Q1 à Q4 intégrées (API Whisper OpenAI, VM Podman partagée, connexion par mot de passe, Python).
- Socle : projet Python, configuration `.env`, FastAPI minimale (`/`, `/sante`), GitHub Actions.
- Chaîne complète : extraction audio → Whisper (adaptateur OpenAI `verbose_json`) → Pocket TTS phrase par
  phrase → placement aux timecodes (décalage signalé si débordement) → remplacement de la bande son.
- Commande `doublage traiter video.mp4` ; mode `--simuler` testé de bout en bout. 14 tests passent.
- `Containerfile` + `compose.yml` (Podman, port 8090, données dans `/srv/apps/doublage/data`, 2 CPU / 4 Go max).
- Non vérifié : vraie voix Pocket TTS et construction de l'image (réseau bloqué ici, pas de moteur de conteneurs).
- Bloquant : Q5 (accès Internet de la VM). Suite : Phase 2 (connexion, liste des projets, éditeur sur l'image).

## 2026-10-27 — Démarrage
- Recueil du besoin : doublage de tutoriels vidéo par voix de synthèse, traitement 100 % interne.
- Choix : application web sur VM, transcription par le serveur Whisper interne, synthèse par Pocket TTS (voix estelle).
- Création de SPEC.md, PLAN.md, IDEES.md, QUESTIONS.md, CLAUDE.md.
- En attente : validation du plan et réponses aux questions Q1 à Q4.
