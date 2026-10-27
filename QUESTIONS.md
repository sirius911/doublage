# Questions en attente

Questions qui demandent une réponse de votre part. Répondez directement sous chaque question.
Tant qu'une question bloque une tâche, Claude avance sur les autres.

## Ouvertes

### Q6 — Premier essai réel
Quand la VM sera prête, pouvez-vous y lancer (procédure dans README.md) :
`doublage traiter une_video_courte.mp4` sur un tutoriel de 1 à 2 minutes, et me dire le résultat
(messages affichés, qualité de la voix, synchronisation) ?

Réponse :

## Résolues
- Entrée : la vidéo complète (pas seulement l'audio).
- Voix de départ : « estelle » ; catalogue de voix plus tard.
- Utilisateurs : 2 à 3 auteurs de tutoriels.
- Type d'application : application web sur une VM de l'établissement.
- Q1 — Serveur Whisper : API compatible OpenAI, `POST http://10.1.147.251:30000/v1/audio/transcriptions`,
  `multipart/form-data`, champ `file`, `language=fr`, `response_format=verbose_json` ; la réponse contient
  `text`, `duration` et `segments` (`start`, `end`, `text`). Testé avec succès sur un petit fichier audio
  (pas encore sur l'audio d'une vidéo complète). Le serveur n'est pas joignable depuis les sessions cloud de Claude :
  les essais réels se feront depuis la VM.
- Q2 — VM : `svp-recvoc-a3p` (10.1.147.219), Oracle Linux 8.10, 4 vCPU, 15 Gio de RAM, **Podman 4.9.4 +
  podman-compose 1.0.6** (pas de Docker). VM partagée avec d'autres applications en production (dont
  ce-transcripteur-v2) : isolation complète obligatoire (conteneurs, réseau, ports, volumes, variables),
  vérification des ressources avant déploiement, choix d'un volume adapté pour les données.
- Q3 — Accès : connexion simple par mot de passe, sans sécurité poussée.
- Q4 — Choix techniques : Python validé.
- Q5 — Accès Internet de la VM : oui, via le proxy `http://proxy.chprod.fr:8080` (Docker Hub, PyPI, PyTorch,
  Hugging Face joignables). Podman sans droits root. Le port 8090 est déjà occupé : en choisir un autre.
  Le serveur Whisper est appelé sans proxy.
