# Questions en attente

Questions qui demandent une réponse de votre part. Répondez directement sous chaque question.
Tant qu'une question bloque une tâche, Claude avance sur les autres.

## Ouvertes

### Q1 — Interface du serveur Whisper (bloque : adaptateur réel, Phase 1)
Comment interroge-t-on le serveur ? Idéalement :
- l'adresse (URL) et la méthode d'appel (exemple de commande `curl` ou de code existant) ;
- le format de réponse : renvoie-t-il les **timecodes par phrase** (segments), voire par mot ?
- faut-il une authentification (clé, jeton) ?
- limite de taille ou de durée des fichiers envoyés ?

En attendant, Claude développe avec un serveur simulé.

Réponse :

### Q2 — La VM d'hébergement (bloque : Phase 4)
- Système (Linux ? quelle distribution ?), nombre de cœurs, mémoire, espace disque ?
- Docker peut-il y être installé ?
- La VM peut-elle joindre le serveur Whisper ?

Réponse :

### Q3 — Accès à l'application (bloque : Phase 4)
Un accès libre depuis le réseau interne suffit-il, ou faut-il un mot de passe / les comptes de l'établissement ?

Réponse :

### Q4 — Validation des choix techniques (voir PLAN.md, « Choix techniques »)
Python + FastAPI, interface web simple, Docker Compose sur la VM. D'accord ?

Réponse :

## Résolues
- Entrée : la vidéo complète (pas seulement l'audio).
- Voix de départ : « estelle » ; catalogue de voix plus tard.
- Utilisateurs : 2 à 3 auteurs de tutoriels.
- Type d'application : application web sur une VM de l'établissement.
