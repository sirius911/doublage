# Journal

Historique des sessions, la plus récente en haut.

## 2026-10-27 — Phase 3 : solutions automatiques de calage
- Débord sur le silence : déjà le cas (la voix est posée à son timecode et peut finir dans le silence
  qui suit, sans gêner la phrase suivante).
- Accélération légère : à l'export, une voix qui empiète sur la phrase suivante est accélérée juste
  assez pour finir à temps, sans changer la hauteur (filtre atempo de ffmpeg), dans la limite de 15 %
  (`DOUBLAGE_ACCELERATION_MAX`, choix par défaut à confirmer à l'usage ; 1.0 désactive).
- Pastilles : orange = corrigé automatiquement (débord ou accélération, détail au survol) ; rouge = même
  accélérée, la voix déborde : texte à raccourcir. « ▶ Voix » fait entendre la voix non accélérée.
- Le test de l'accélération réelle (ffmpeg) ne tourne pas sur le poste Windows : à vérifier sur la VM.
## 2026-10-27 — Phase 3 : indicateur de calage par phrase
- Pastille à côté de « ▶ Voix » (dès qu'une voix existe) : verte si la voix tient dans la durée de la
  phrase d'origine, orange si elle déborde sur le silence qui suit, rouge si elle empiète sur la phrase
  suivante (qui sera décalée à l'assemblage). Détail au survol (durées, débordement). Pastille grisée si
  le texte a changé depuis la voix. Tolérance de 0,05 s.
- Chaque phrase est jugée isolément : le décalage en cascade d'une phrase rouge sur les suivantes n'est
  pas reflété. Suite : solutions automatiques (accélération légère, débord sur le silence).
## 2026-10-27 — Phase 2 : retours après essai sur la VM
- Essai de l'utilisateur : tout fonctionne, mais la vidéo disparaissait en faisant défiler les phrases.
- Éditeur en deux colonnes : vidéo (+ section « Vidéo doublée ») à gauche, fixe ; liste des phrases à droite
  dans sa propre zone qui défile, et qui suit la phrase en cours pendant la lecture. Écran étroit : la vidéo
  reste collée en haut.
- Bouton « Générer la voix » supprimé : « ▶ Voix » joue la voix si elle est à jour, sinon la crée d'abord ;
  curseur d'attente pendant la création. Conséquence : plus de moyen de refaire une voix déjà à jour
  (une prise différente) sans modifier le texte.
- Phrase d'explication sous « Générer la vidéo doublée » supprimée (jugée incompréhensible).
- Déploiement : un conteneur `doublage-essai` (arrêté, pas supprimé) et l'ancien volume `doublage-modeles`
  restent à nettoyer dans le stockage dédié ; compose utilise `doublage_doublage-modeles`.

## 2026-10-27 — Phase 2 : génération complète et export (fin de la Phase 2)
- Section « Vidéo doublée » sous la liste des phrases : génération en tâche de fond avec barre de
  progression ; seules les phrases sans voix à jour sont synthétisées, les voix déjà écoutées sont reprises.
  À la fin, seule la section est rafraîchie (la position de la vidéo et les corrections en cours restent).
- Téléchargement « <nom du projet> (doublée).mp4 ». La nouvelle vidéo est écrite à part puis remplace
  l'ancienne : la précédente reste téléchargeable pendant la génération.
- La correction du texte reste possible pendant la génération (verrous partagés avec l'éditeur).
- Limites connues : l'export est toujours en .mp4 (image copiée sans ré-encodage) — une source .webm ou
  .avi exotique pourrait échouer ; l'avertissement « phrases décalées » n'est pas affiché dans l'interface
  (prévu en Phase 3 avec l'indicateur par phrase). Export non testé ici faute de ffmpeg sur le poste :
  à vérifier sur la VM.
- Suite : essai de la Phase 2 sur la VM par l'utilisateur, puis Phase 3.

## 2026-10-27 — Phase 2 : écoute et voix d'une phrase
- Par phrase : « ▶ Original » rejoue l'extrait de la vidéo (arrêt automatique en fin de phrase),
  « Générer la voix » / « Régénérer » synthétise la phrase avec son texte actuel puis la fait écouter,
  « ▶ Voix » réécoute. État affiché : « voix à jour » ou « texte modifié : voix à régénérer ».
- Le modèle Pocket TTS est chargé au premier usage puis gardé en mémoire : la toute première génération
  prend donc plus de temps. Une seule synthèse à la fois (verrou partagé, à réutiliser pour la génération
  complète). Si le texte change pendant la synthèse, la phrase reste « à régénérer ».
- Non vérifié dans un vrai navigateur. Suite : génération de toutes les phrases + export de la vidéo.

## 2026-10-27 — Phase 2 : clic sur une phrase
- Clic sur une phrase de la liste (ou sur son timecode, devenu un bouton) : la vidéo se place à son début,
  lecture ou pause conservée. Un clic dans le texte de la phrase déjà en cours ne déplace pas la vidéo.
- Non vérifié dans un vrai navigateur. Suite : écoute original / voix synthétique, régénération d'une phrase.

## 2026-10-27 — Phase 2 : correction du texte
- Correction sur l'image (vidéo en pause : le texte devient modifiable) ou dans la liste ; les deux restent
  synchronisés. Enregistrement automatique 0,8 s après la dernière frappe et en quittant la phrase, état
  affiché (« Modifié… », « Enregistré. », erreur). Entrée valide la phrase. Avertissement si on quitte la page
  avant l'envoi. Texte original de Whisper conservé (infobulle).
- Une phrase déjà synthétisée dont le texte change passe à l'état « modifiée » (voix à régénérer).
- Non vérifié dans un vrai navigateur. Suite : clic sur une phrase → la vidéo se place au timecode.

## 2026-10-27 — Phase 2 : éditeur (affichage sur l'image)
- Une fois transcrit, le projet s'ouvre sur l'éditeur : vidéo, phrase en cours affichée sur l'image façon
  sous-titre (suivi image par image pendant la lecture), phrase en cours surlignée dans la liste.
- JavaScript et CSS dans `doublage/static/` (servis par FastAPI), page projet plus large.
- Non vérifié dans un vrai navigateur. Suite : modification du texte sur l'image et dans la liste.

## 2026-10-27 — Phase 2 : suivi de l'envoi
- Demande après essai sur la VM : aucun retour pendant l'envoi de la vidéo. Envoi en JavaScript avec barre de
  progression (pourcentage, Mo, temps restant), puis « enregistrement » jusqu'à l'ouverture du projet.
  Sans JavaScript, le formulaire classique fonctionne toujours.

## 2026-10-27 — Phase 2 : transcription depuis l'interface
- Traitements longs en tâche de fond (`jobs.py`) : un seul à la fois (VM partagée), état en mémoire
  (perdu au redémarrage, il suffit de relancer ; les résultats sont enregistrés dans le projet).
- Page projet : bouton « Lancer la transcription », barre indéterminée avec l'étape et le temps écoulé
  (le serveur Whisper ne renvoie pas d'avancement), message en cas d'erreur avec possibilité de relancer,
  puis liste des phrases avec leur timecode. Une transcription existante n'est jamais écrasée.
- `DOUBLAGE_SIMULER=1` pour essayer l'interface sans Whisper ni Pocket TTS.
- Les tests qui demandent ffmpeg sont ignorés s'il est absent (poste Windows) ; ils tournent en CI.
- Suite : éditeur (vidéo en fond, texte de la phrase en cours sur l'image).

## 2026-10-27 — Phase 2 : projets
- Relevé sur la VM après limitation : priorité basse effective (NI 10), mais ~290 % de processeur au lieu de
  200 % (Pocket TTS utilise d'autres fils que ceux de PyTorch) ; laissé tel quel, la priorité basse protège
  les autres applications. 36 s pour la vidéo de 90 s (modèle déjà en cache).
- `HF_HUB_OFFLINE=1` proposé dans `.env.exemple` une fois le modèle téléchargé.
- Projets : table `projects` dans `doublage.db`, un dossier `data/projets/<id>/` par projet avec la vidéo.
  Page d'accueil = dépôt + liste ; page projet avec lecteur vidéo (requêtes partielles pour se déplacer).
  Tous les utilisateurs voient tous les projets (équipe de 2-3 auteurs).
- Suite : lancement de la transcription avec barre de progression.

## 2026-10-27 — Premier doublage réel sur la VM
- Image construite dans le stockage Podman dédié ; scribe intact.
- Q6 : vidéo de 90 s → 20 phrases, 56 s de traitement, doublage jugé très bon, pas de phrase inventée.
- Constaté : `--cpus`/`--memory` ignorés (cgroups v1 sans root). Synthèse limitée à 2 cœurs
  (`DOUBLAGE_TTS_THREADS`, `OMP_NUM_THREADS`) et lancée avec `nice -n 10` ; Q9 ouverte (cgroups v2).
- Timecodes arrondis à la milliseconde (bruit de virgule flottante dans la réponse de Whisper).
- À faire sur la VM : reconstruire l'image (limitation des cœurs). Suite : Phase 2 (liste des projets).

## 2026-10-27 — Préparation de la VM
- Q5 résolue : Internet via le proxy de l'établissement. Whisper appelé sans proxy (sinon la requête partait
  vers le proxy) ; requête réelle de transcription réussie depuis la VM.
- Correctif : la fin des phrases renvoyée par Whisper peut dépasser la durée de l'audio → bornée.
- Port 8091 (8090 occupé). Données hors de `/home`, `--userns keep-id` pour les droits sur les fichiers.
- Première construction d'image : échec, `/home` plein (10 Go, partagé avec scribe).
- Q7 résolue (solution C) : stockage Podman rootless dédié dans `/var/lib/containers/doublage/storage`,
  sélectionné par `CONTAINERS_STORAGE_CONF` / `CONTAINERS_CONF_OVERRIDE` via `deploiement/podman-doublage` ;
  état d'exécution et verrous séparés de scribe ; service systemd utilisateur. Procédure dans README.md.
- Essai sur la VM : `CONTAINERS_STORAGE_CONF` ignoré pour graphroot/runroot en mode sans root (rien n'a été
  construit dans le mauvais stockage). Remplacé par `XDG_CONFIG_HOME` → `deploiement/config/containers/`.
- Vérifié sur la VM : stockage dédié pris en compte (graphroot, runroot, tmp_dir, verrous en fichiers),
  image construite (1,79 Go), scribe intact. Restait à vérifier à l'origine : configuration via `XDG_CONFIG_HOME` et `lock_type = "file"` par Podman 4.9.4
  (contrôlé par l'étape 3 du déploiement), réglage overlay natif / fuse-overlayfs selon le noyau.
- Bloquant : préparation par l'administrateur (étape 2), puis premier essai réel (Q6). Q8 ouverte (données).

## 2026-10-27 — Phase 2 : connexion
- Aucune nouvelle idée ni réponse (Q5 et Q6 toujours ouvertes).
- Comptes et sessions dans SQLite (`data/doublage.db`), mots de passe chiffrés avec scrypt (bibliothèque standard).
- Pages `/connexion` et `/deconnexion` ; l'accueil redirige vers la connexion si besoin ; session de 30 jours.
- Commande `doublage utilisateur ajouter|supprimer|liste`. Tests de connexion et des comptes ajoutés.
- Remarque : les tests utilisant ffmpeg échouent sur un poste Windows sans ffmpeg (ils passent en CI).
- Suite : liste des projets + dépôt d'une vidéo.

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
