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
- [x] Synthèse d'une phrase avec Pocket TTS (voix estelle, modèle chargé une seule fois) — validée sur la VM
- [x] Assemblage de la bande son : chaque phrase placée à son timecode, silence ailleurs
- [x] Remplacement de la bande son dans la vidéo (sans ré-encoder l'image)
- [x] Commande `doublage traiter video.mp4` qui enchaîne tout — essai réel validé sur la VM (vidéo de 90 s)

## Phase 2 — Interface web
- [x] Connexion par identifiant / mot de passe (comptes créés en ligne de commande, mots de passe chiffrés)
- [x] Liste des projets + dépôt d'une vidéo (projets visibles par tous les utilisateurs)
- [x] Suivi de l'envoi de la vidéo (pourcentage, Mo envoyés, temps restant) — demandé après essai sur la VM
- [x] Lancement de la transcription avec barre de progression (étape + temps écoulé : Whisper ne donne pas d'avancement)
- [x] Éditeur : vidéo en fond, texte de la phrase en cours affiché sur l'image au bon timecode
- [x] Modification du texte sur l'image et dans la liste des phrases, enregistrement automatique
- [x] Clic sur une phrase → la vidéo se place au timecode
- [x] Écoute de l'original / de la voix synthétique d'une phrase ; régénération d'une seule phrase
- [x] Génération de toutes les phrases + export de la vidéo finale à télécharger
- [x] Retours après essai sur la VM : vidéo toujours visible (liste des phrases à côté, qui défile seule),
      bouton « ▶ Voix » unique (crée la voix si besoin, curseur d'attente)

## Phase 3 — Calage et confort d'édition
- [x] Indicateur par phrase : la voix synthétique tient-elle dans son créneau ? (vert / orange / rouge)
- [x] Solutions automatiques : accélération légère (limite raisonnable), débord sur le silence suivant
- [ ] Fusionner / couper des phrases, ajuster début et fin — repoussé (Q10) : à faire si le besoin apparaît
- [x] Aperçu de la vidéo avec la nouvelle voix avant l'export
- [x] Export complémentaire : sous-titres (SRT/VTT) et audio seul

## Phase 4 — Mise en service
- [x] Relevé des ressources consommées sur la VM par les applications existantes ; choix du volume de données (ex. `/srv/apps`)
- [~] Stockage Podman rootless dédié (`/var/lib/containers/doublage/storage`), code dans `/srv/apps/doublage` — en place et vérifié (stockage, état d'exécution et verrous séparés de scribe)
- [~] Choix d'un port libre (8091), réseau et volumes dédiés, aucune interférence avec ce-transcripteur-v2 et `scribe` — à vérifier au déploiement
- [x] Essai réel du serveur Whisper avec l'audio d'une vidéo complète — OK sur 90 s, puis sur un vrai tutoriel d'un peu plus de 5 min (moins de 10 s de transcription) ; tutoriels de 5 min au plus : pas de recherche de la limite (délai d'attente de l'application : 15 min)
- [x] Découpage en vraies phrases : sans consigne, Whisper renvoyait des tronçons de 2 s sans aucune ponctuation
      (doublage haché) ; texte d'exemple ponctué (`prompt`, réglable) → phrases ponctuées, et regroupement des
      tronçons restants d'une même phrase (15 s au plus, pas par-dessus un silence de plus de 1 s)
- [~] Ressources : synthèse limitée à 2 cœurs et en priorité basse (cgroups v1 : `--cpus`/`--memory` ignorés, voir Q9)
- [~] Documentation d'installation sur la VM (Podman sans droits root ; une préparation initiale par l'administrateur) — écrite, à éprouver
- [x] Démarrage automatique avec la VM (service systemd modèle `deploiement/doublage@.service`) + script `deploiement/mettre-a-jour` — installés et vérifiés sur la VM (redémarrage de la VM pas encore éprouvé)
- [x] ~~Environnement de test (staging)~~ : abandonné, une seule instance (Q11)
- [x] Interface : barre de titre compacte sur toutes les pages, éditeur à la hauteur de l'écran (vidéo toujours visible, phrases qui défilent à droite, actions sur une ligne à part)
- [x] Suppression d'un projet depuis la liste (croix à droite, confirmation ; supprime vidéo, transcription, voix et exports ; refusée pendant un traitement en cours)
- [x] Mise en production : fusion `dev` → `main` par l'utilisateur, instance sur `main` (uniquement après validation)
- [x] ~~HTTPS~~ : non, HTTP en connaissance de cause ; nom via un reverse proxy plus tard, à la racine (Q12)

## Phase 5 — Voix
- [x] Choix de la voix par projet parmi un catalogue (voix prédéfinies retenues dans `DOUBLAGE_TTS_VOICES` ; changer de voix efface les voix déjà générées) — estelle est la seule voix française de Pocket TTS : les voix étrangères sont à écouter avant de les proposer
- [x] Ajout d'une voix à partir d'un échantillon audio (export en `.safetensors` pour un chargement rapide) — page « Voix » : échantillon audio ou vidéo (30 premières secondes), accord de la personne enregistrée obligatoire, écoute, suppression (refusée si un projet l'utilise)
- [x] Choix du modèle `french` / `french_24l` : on reste sur `french` (décision de l'utilisateur, 2026-10-28) — `french_24l` 3,3 fois plus lent (x1,21 du temps réel contre x0,37) pour une différence qui ne le justifie pas ; réglage `DOUBLAGE_TTS_LANGUAGE` conservé
- [x] Barre de progression pendant l'envoi d'un échantillon de voix (comme pour le dépôt d'une vidéo ; même script, factorisé)
- [x] Case « sous-titres incrustés dans l'image » à la génération de la vidéo doublée, décochée par défaut, avec avertissement sur la durée du ré-encodage (Q13) — validée sur la VM ; ré-encodage mesuré : 23 s pour une vidéo de 89 s (environ un quart de sa durée), chiffre repris dans l'avertissement

## Phase 6 — Confort d'utilisation
- [x] Section « Vidéo doublée » réorganisée : case « Sous-titres incrustés » à droite du bouton, dont le texte
      devient « … avec sous-titres » quand elle est cochée (avertissement sur la durée affiché seulement alors) ;
      lien de téléchargement, date, autres exports et avertissement « corrections depuis » sous le bouton
- [x] Menu « Aide » dans la barre de titre et page d'aide claire et illustrée, qui remplace le long texte sous
      la vidéo de l'éditeur (Q14 : illustrations dessinées dans la page, pas de captures d'écran)
- [x] Petit bouton ↺ sous le timecode d'une phrase corrigée : revenir au texte de la transcription d'origine
      (confirmation ; la voix devient « à régénérer » comme pour toute correction)
- [x] Durées des progressions lisibles : secondes, puis minutes au-delà de 60 s, puis heures au-delà de 60 min
      (temps restant de l'envoi, temps écoulé de la transcription et du doublage)
- [x] ~~Suppression d'une voix refusée~~ : pas un bug, la voix servait encore à un autre projet (Q15)
- [x] Nom de la voix utilisée après « (générée le … à …) » de la vidéo doublée
- [x] Case par phrase, décochée par défaut, « voix d’origine » : la phrase garde le son d'origine dans la vidéo
      doublée (pas de voix de synthèse pour elle)
- [x] Hallucinations de Whisper (une phrase répétée en boucle sur un silence) écartées à la transcription
- [x] Phrase effacée : texte vidé dans l'éditeur → ni voix ni sous-titre, phrase grisée, ↺ pour la rétablir
- [x] Ralentissement automatique (10 % au plus, réglable) d'une voix qui finit nettement avant la phrase
      d'origine, symétrique de l'accélération
- [x] Vitesse réglable par phrase (clic sur la pastille : curseur 0,8 à 1,25, bouton « auto ») ; « ▶ Voix »
      joue à la vitesse choisie, pastille recalculée ; sans réglage, la vitesse automatique s'applique
- [x] Prononciation sans abîmer les sous-titres : notation `[écrit|prononcé]` dans le texte d'une phrase
      (sous-titres : « écrit », voix : « prononcé ») ; notation mal formée signalée dans la liste ; aide
      (choix de l'utilisateur parmi deux textes par phrase, glossaire commun, notation : la notation)
- [x] Barre de titre (Doublage › …, Voix, Aide) toujours visible quand on fait défiler la page (aide, voix…)
- [x] Police et taille des sous-titres incrustés, réglées par projet à côté de la case « Sous-titres
      incrustés » (polices installées dans le conteneur ; le SRT/VTT téléchargé reste stylé par le lecteur) ;
      aperçu : une image de la vidéo, à l'instant affiché par le lecteur, avec le sous-titre gravé exactement
      comme il le sera (même moteur ffmpeg), sans générer la vidéo
- [x] Éditeur : « Son de la vidéo : original / nouvelle voix (aperçu) » déplacé sur la ligne « Voix : … »,
      à droite sous la vidéo (sous « Vidéo doublée », on le croyait lié au bouton de génération)
- [x] Aide : exemples (« Ceci est un tutoriel sur… », prononciation Zimbra / DXCare), « ▶ Voix » (peut prendre
      plusieurs secondes la première fois), génération décrite simplement, sous-titres incrustés simplifiés,
      aperçu « nouvelle voix » décrit avec la ligne Voix
- [x] Début des phrases recalé sur la parole : Whisper fait souvent commencer la première phrase à 0 s alors
      qu'on ne parle qu'après (exemple : 6 s), la voix partait trop tôt ; après la transcription, le début de
      chaque phrase est avancé jusqu'au premier son réel (silence de 0,3 s au moins, 0,1 s de marge) —
      nouvelles transcriptions seulement
- [x] Fin des phrases recalée sur la parole : la fin donnée par Whisper inclut la pause qui suit, donc
      beaucoup de voix étaient ralenties jusqu'au plafond ; fin ramenée au dernier son réel (+ 0,2 s).
      Le créneau (jusqu'à la phrase suivante) ne change pas : la voix peut toujours déborder sur la pause
- [x] Voix créées coupées en plein mot (cyrille, charlie ; estelle jamais) : mesuré sur la VM, la phrase
      générée est coupée quand l'échantillon est long (30 s → coupée vers 5 s, 20 s → dernier mot tronqué,
      10 et 15 s → complète) ; seules les 10 premières secondes de l'échantillon servent désormais (voix
      existantes comprises, sans les redéposer), et un nouvel échantillon est limité à 10 s
- [x] Enregistrer une voix : texte à lire en grand (« prompteur », environ 10 s, ton d'un tutoriel) et
      consignes (parler tout de suite, ton naturel, aller au bout, au calme avec le micro des tutoriels),
      sur la page Voix et dans l'aide (section « Les voix »)
- [x] Aide, Astuces : pause manquante après une virgule → `[,|.]` ou `[,|...]` (essayés par l'utilisateur :
      les sous-titres gardent la virgule, la voix marque la pause)

## Idées pour plus tard
- Glossaire de prononciation (noms de logiciels, sigles)
- Conserver les bruits de fond d'origine (clics) sous la nouvelle voix
