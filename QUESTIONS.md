# Questions en attente

Questions qui demandent une réponse de votre part. Répondez directement sous chaque question.
Tant qu'une question bloque une tâche, Claude avance sur les autres.

## Ouvertes

## Résolues
- Q14 : page d'aide illustrée par des dessins dans la page (vrais boutons, pastilles et zones reproduits
  en petit, flèches, légendes), pas de captures d'écran ; une ou deux captures plus tard si besoin.
- Q13 : sous-titres gravés dans l'image, case décochée par défaut, avec un avertissement sur la durée du
  ré-encodage.
- Q12 : HTTP en connaissance de cause (mots de passe et vidéos en clair sur le réseau interne). Un reverse
  proxy viendra plus tard pour donner un nom à l'application, sans HTTPS. Il devra la publier à la racine
  d'un nom (`http://doublage…/`), pas sous un sous-chemin : les liens de l'application sont absolus.
- Q11 : une seule instance, la production (`/srv/apps/doublage`, port 8091, branche `main`) ; pas d'instance
  de test séparée, les essais se font directement sur la production (utilisateurs = collègues). Le travail
  continue sur la branche `dev`, fusionnée dans `main` par l'utilisateur à chaque version validée.
- Q8 : données dans `/srv/apps/doublage/data` ; à revoir si le volume grossit.
- Q9 : on s'en tient au bridage applicatif (2 cœurs, `nice`) en cgroups v1 ; à revoir si la VM souffre
  pendant les synthèses (passage en cgroups v2 à décider avec l'administrateur).
- Q10 (fusionner / couper / recaler les phrases) : repoussé, besoin pas encore rencontré sur les vidéos réelles.
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
  Hugging Face joignables). Podman sans droits root. Le port 8090 est déjà occupé : l'application utilise 8091.
  Le serveur Whisper est appelé sans proxy.
- Q7 — Stockage Podman : solution C retenue. Le stockage Podman de `lorcyr` (sur `/home`, utilisé par scribe)
  reste inchangé ; doublage a son propre stockage rootless dans `/var/lib/containers/doublage/storage`
  (XFS, 197 Go, SELinux Enforcing), le code dans `/srv/apps/doublage`. Pas de modification de la configuration
  Podman globale, pas d'intervention sur ce-transcripteur-v2. Préparation (droits, SELinux) et procédure dans
  README.md, « Déploiement sur la VM ». Nettoyage des images inutilisées traité séparément.
- Q6 — Premier essai réel (2026-10-27) : vidéo de 90 s, 20 phrases, 56 s de traitement au total (téléchargement du modèle
  compris). Doublage jugé très bon, synchronisation correcte, aucune phrase inventée
  sur les silences.
