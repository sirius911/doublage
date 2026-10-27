# Questions en attente

Questions qui demandent une réponse de votre part. Répondez directement sous chaque question.
Tant qu'une question bloque une tâche, Claude avance sur les autres.

## Ouvertes

### Q8 — Emplacement des données (non bloquant)
Par défaut, les données (vidéos déposées, projets, comptes) vont dans `/srv/apps/doublage/data`, sur `/`
(42 Go libres, partagés avec le système). Une alternative est `/var/lib/containers/doublage/data` (197 Go).
Pour quelques tutoriels de quelques centaines de Mo, `/srv` suffit largement ; je recommande de le garder
et de revoir si le volume grossit. D'accord ?

Réponse :

### Q9 — Limites de ressources du conteneur (non bloquant)
Sur la VM, Podman sans root en **cgroups v1** ignore `--cpus` et `--memory` (message « Resource limits are
not supported and ignored on cgroups V1 rootless systems ») : les limites de `compose.yml` sont sans effet.
En attendant, la synthèse est bridée à 2 cœurs dans l'application (`DOUBLAGE_TTS_THREADS`, `OMP_NUM_THREADS`)
et tourne en priorité basse (`nice`). Il n'y a en revanche **aucune limite de mémoire** (Pocket TTS : ~1 à 2 Go).
La vraie solution serait de passer la VM en **cgroups v2** (paramètre de démarrage
`systemd.unified_cgroup_hierarchy=1` + redémarrage) : cela concerne toutes les applications de la VM (scribe,
ce-transcripteur-v2), donc à décider avec l'administrateur. Je recommande de s'en contenter pour l'instant
et d'y revenir si la VM souffre pendant les synthèses.

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
  Hugging Face joignables). Podman sans droits root. Le port 8090 est déjà occupé : l'application utilise 8091.
  Le serveur Whisper est appelé sans proxy.
- Q7 — Stockage Podman : solution C retenue. Le stockage Podman de `lorcyr` (sur `/home`, utilisé par scribe)
  reste inchangé ; doublage a son propre stockage rootless dans `/var/lib/containers/doublage/storage`
  (XFS, 197 Go, SELinux Enforcing), le code dans `/srv/apps/doublage`. Pas de modification de la configuration
  Podman globale, pas d'intervention sur ce-transcripteur-v2. Préparation (droits, SELinux) et procédure dans
  README.md, « Déploiement sur la VM ». Nettoyage des images inutilisées traité séparément.
- Q6 — Premier essai réel (2026-10-27) : vidéo de 90 s, 20 phrases, 56 s de traitement au total (modèle déjà
  chargé exclu du téléchargement). Doublage jugé très bon, synchronisation correcte, aucune phrase inventée
  sur les silences.
