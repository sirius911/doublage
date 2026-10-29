# Journal

Historique des sessions, la plus récente en haut.

## 2026-10-29 — Notation [écrit|prononcé], état de l'enregistrement en bas de la fenêtre
- Éditeur : phrase d'explication sous la vidéo retirée ; « Enregistré. » / erreurs dans une étiquette fixe en
  bas à droite de la fenêtre (la barre d'état du navigateur n'est plus accessible aux pages).
- Idée « mot phonétique pour la voix, correct dans les sous-titres » : trois formes proposées (deux textes par
  phrase, glossaire commun, notation dans le texte) ; l'utilisateur a choisi la notation.
  `[Zimbra|Zimm-bra]` : sous-titres (SRT, VTT, incrustés) « Zimbra », voix « Zimm-bra ». Notation mal formée
  soulignée en rouge avec « ⚠ notation » (sinon crochets visibles dans les sous-titres). Aide : section
  Prononciation. Le glossaire reste dans les idées pour plus tard.
- Les phrases déjà écrites phonétiquement (vidéo 4) sont à reprendre à la main (↺ puis notation).
- Suite : essai sur la VM.

## 2026-10-29 — Vitesse réglable par phrase
- Demande de l'utilisateur : le ralentissement automatique rend parfois la voix monotone ; régler la vitesse
  phrase par phrase donne plus de naturel.
- Fait : clic sur la pastille → curseur ×0,80 à ×1,25 placé sur la vitesse automatique, bouton « auto ».
  Vitesse enregistrée avec la phrase (`speed`, absente = automatique), gardée si le texte change ; la pastille
  et son explication en tiennent compte ; valeur affichée en bleu après la pastille.
- « ▶ Voix » joue désormais à la vitesse de la phrase (automatique ou choisie), avec la lecture du navigateur
  qui garde la hauteur ; la vidéo doublée utilise toujours ffmpeg (atempo) : rendu très proche, pas identique.
- Suite : essai sur la VM.

## 2026-10-29 — Hallucinations, phrase effacée, ralentissement
- Après relance de la vidéo 4 avec le prompt : 43 phrases (médiane 7 s, max 21 s, 36 ponctuées, aucune
  d'un ou deux mots). Décalage acceptable à l'écoute sur les phrases longues : découpe (Q10) toujours repoussée.
- Hallucination vue en fin de vidéo (une phrase répétée en boucle sur un silence) → filtre à la transcription :
  taux de compression du texte > 2,4 (seuil de Whisper), sur les tronçons puis sur les phrases regroupées.
  Marge mesurée : parole répétitive réelle ~1,6 ; la boucle observée ~10.
- Phrase effacée : texte vidé → ni voix ni sous-titre, grisée avec une indication, ↺ la rétablit.
- Ralentissement automatique d'une voix nettement plus courte que la phrase d'origine, jusqu'à 10 %
  (`DOUBLAGE_VITESSE_MIN`, 0.9 par défaut) ; jamais sur le son d'origine ; indiqué au survol de la pastille.
  Attention : les timecodes de Whisper étant collés, la « durée d'origine » inclut la pause qui suit ;
  beaucoup de phrases seront ralenties jusqu'au plafond. À juger à l'écoute.
- « ▶ Voix » joue la voix brute (sans ralentissement ni accélération) ; l'aperçu de la vidéo doublée, si.
- Suite : essai sur la VM ; le filtre ne vaut que pour les nouvelles transcriptions (vidéo 4 : effacer la
  phrase inventée à la main).

## 2026-10-29 — Whisper : ponctuation et vraies phrases
- Constat sur le tutoriel de 5 min (vidéo 4) : 134 tronçons de 2 s en médiane, collés les uns aux autres,
  aucune ponctuation → synthèse hachée (chaque morceau prononcé comme une phrase), voix d'origine coupée
  en pleine phrase. Diagnostic par chiffres seuls, sans faire sortir le texte de l'établissement.
- Essai sur la VM : avec un texte d'exemple ponctué (`prompt`), 56 phrases dont 52 ponctuées, médiane 3,9 s.
- Fait : `prompt` envoyé à Whisper (`DOUBLAGE_WHISPER_PROMPT`, texte neutre par défaut) ; regroupement des
  tronçons d'une même phrase (15 s au plus, pas par-dessus un silence de plus de 1 s). Q10 en partie traitée.
- Projets existants : pas de regroupement après coup ; l'utilisateur relance la transcription de la vidéo 4.
- À vérifier : le texte par défaut diffère un peu de celui de l'essai (sans « messagerie »), refaire les
  statistiques après la relance ; surveiller que des mots du prompt n'apparaissent pas sur des silences.

## 2026-10-28 — Nom de la voix sur la vidéo doublée, case « voix d'origine »
- Deux idées intégrées (Phase 6) et réalisées.
- Vidéo doublée : « (générée le … avec la voix X) ». Le nom est noté à côté de la vidéo
  (`video_doublee.voix`) ; les vidéos générées avant n'affichent pas de voix.
- Case « voix d'origine » par phrase (décochée par défaut) : la phrase n'est pas synthétisée, la vidéo doublée
  reprend le son d'origine sur [début, fin], borné au début de la phrase suivante, avec des fondus de 10 ms.
  Son d'origine extrait une fois par projet à 24 kHz (`original-24000.wav`). « ▶ Voix », pastille et état
  masqués pour ces phrases ; sous-titres inchangés. Aide mise à jour.
- Limites connues : volume et timbre différents de la synthèse ; une fin de phrase coupée si Whisper a mal
  placé les timecodes.
- Suite : essai sur la VM (`dev` en avance sur `main`), puis avancer `main` si validé.

## 2026-10-28 — Durées lisibles, mesure du doublage d'un tutoriel de 5 min
- Progressions : durées en secondes, puis minutes, puis heures (fonction commune, testée avec Node).
- Q15 résolue : la voix à supprimer servait encore à un autre projet ; pas de bug.
- Mesure sur la VM : tutoriel de 5 min 17 s doublé (sans sous-titres, toutes les voix à générer) en
  1 min 34 s, soit environ 0,3 fois la durée de la vidéo. Avec sous-titres, compter environ un quart de la
  durée en plus (mesure précédente).
- `dev` en avance sur `main` : nettoyage des images dans `mettre-a-jour`, durées lisibles.

## 2026-10-28 — Whisper sur un vrai tutoriel de 5 min
- Vidéo d'un peu plus de 5 min redéposée : transcription en moins de 10 s (estimation de l'utilisateur).
  Tâche Whisper close. Reste au plan : redémarrage complet de la VM ; Q10 (fusionner / couper) repoussée.

## 2026-10-28 — Nettoyage de la VM
- Relevé : espace largement suffisant (`/srv/apps` 50 Go libres, stockage Podman 189 Go) ; projet de 90 s
  = 114 Mo. Restes : 14 images `<none>` (une par mise à jour, ~7,5 Go), conteneur `doublage-essai` arrêté,
  un second volume de modèles. Bloc de nettoyage fourni à l'utilisateur (stockage de doublage seulement).
- Nettoyage fait : conteneur d'essai et volume `doublage-modeles` (inutilisé) supprimés, anciennes images
  effacées ; stockage Podman passé de 12 Go à 5,5 Go utilisés ; `/sante` OK.
- `deploiement/mettre-a-jour` supprime désormais les anciennes images après la vérification de `/sante`
  (gardées en cas d'échec). Effectif à partir de la mise à jour qui suit celle qui récupère le script.
- `/home` à 82 % (stockage Podman de scribe, hors doublage) : signalé, à traiter séparément (Q7).
- Envoi d'une vidéo de ~5 min interrompu à ~77 % (sans doute un `mettre-a-jour` pendant l'envoi) :
  aucun reste côté serveur, il suffit de relancer.

## 2026-10-28 — Retour à la transcription d'origine
- Idée de l'utilisateur : petit ↺ gris sous le timecode, visible seulement si le texte diffère de la
  transcription d'origine ; confirmation (le bouton est petit, un clic par erreur effacerait la correction),
  puis enregistrement comme une correction ordinaire. Mentionné dans l'aide.
- `main` avancé jusqu'à `292a6e3` (avec l'avertissement chiffré), VM mise à jour ; ↺ validé par l'utilisateur.
- Reste : premier vrai tutoriel de ~5 min (transcription), redémarrage complet de la VM.

## 2026-10-28 — Durée de l'incrustation des sous-titres
- Mesure sur la VM (dates des fichiers du projet 3) : 23 s de ré-encodage pour 89 s de vidéo, soit environ
  un quart de la durée. L'avertissement (« plusieurs minutes ») exagérait : remplacé par ce chiffre, dans
  l'éditeur et dans l'aide. Une seule mesure : une vidéo plus grande ou plus animée prendra plus.
- Reste : premier vrai tutoriel de ~5 min (transcription), redémarrage complet de la VM.

## 2026-10-28 — Phase 6 : section « Vidéo doublée » réorganisée, page d'aide
- Idées intégrées (Phase 6) ; Q14 : aide illustrée par des dessins, pas de captures d'écran.
- Section « Vidéo doublée » : bouton puis case « Sous-titres incrustés » à sa droite (le bouton devient
  « … avec sous-titres », avertissement sur la durée seulement si cochée), téléchargements dessous.
- Page « Aide » (menu en haut, `/aide`) : les 4 étapes, dépôt, éditeur (schéma numéroté), pastilles,
  vidéo doublée, voix, astuces. Schémas en HTML/CSS (`doublage/aide.py`, `static/aide.css`), mêmes
  couleurs que l'éditeur. Le long texte sous la vidéo devient une ligne avec un lien vers l'aide.
- Rendu vérifié par capture (Edge sans interface) en large et en étroit ; pas encore vu sur la VM.
- Les schémas reproduisent l'interface à la main : à retoucher si elle change.
- `main` avancé jusqu'à `884fbfc` (accord de l'utilisateur), VM mise à jour ; aide validée (« très bien »).
- Suite : essai de durée maximale Whisper, durée de l'incrustation des sous-titres, redémarrage de la VM.

## 2026-10-28 — Essai de `french_24l` sur la VM
- Essai à part dans le conteneur (3 phrases, voix estelle, 2 cœurs, `nice`) : `french` 4,2 s de calcul pour
  11,4 s de voix (x0,37 du temps réel) ; `french_24l` 13,9 s (x1,21), soit 3,3 fois plus lent ; premier
  chargement 55 s (téléchargement des poids compris).
- Décision après écoute : on reste sur `french`, la différence ne vaut pas la lenteur.
- Reste à éprouver sur la VM : durée du ré-encodage des sous-titres, redémarrage complet, durée
  maximale acceptée par Whisper.

## 2026-10-28 — Phase 5 : suivi de l'envoi d'une voix, sous-titres incrustés
- Page « Voix » : barre de progression pendant l'envoi de l'échantillon (script du dépôt de vidéo
  factorisé en `upload_progress()`).
- Vidéo doublée : case « Sous-titres incrustés dans l'image », décochée à chaque génération, avec
  avertissement sur la durée. Texte corrigé aux timecodes d'origine (comme le SRT téléchargeable),
  ré-encodage H.264 `veryfast`, CRF 20, limité à `DOUBLAGE_TTS_THREADS` cœurs. Mention « sous-titres
  incrustés » à côté du lien de téléchargement. Police DejaVu ajoutée à l'image (reconstruction nécessaire).
- Non éprouvé : le vrai rendu ffmpeg (absent du poste ; test en intégration continue), la taille du
  texte (style par défaut de libass) et la durée sur la VM.
- Limite connue : dans l'aperçu « nouvelle voix » d'une vidéo à sous-titres incrustés, le texte de
  l'éditeur s'affiche en plus des sous-titres gravés.
- Suite : `main` avancé jusqu'à `1af1b11` (avec l'accord de l'utilisateur), VM mise à jour : envoi d'une
  voix et sous-titres incrustés validés (« fonctionne très bien »). Reste à mesurer la durée du
  ré-encodage, puis à essayer `french_24l`.

## 2026-10-28 — Phase 5 : voix
- Mise en production faite par l'utilisateur (VM sur `main`, `879ceed`).
- Choix de la voix par projet : catalogue = voix prédéfinies de `DOUBLAGE_TTS_VOICES` + voix ajoutées ;
  changer de voix efface les voix générées (texte conservé). Moteur Pocket TTS unique, voix en mémoire.
- Voix à partir d'un échantillon (page « Voix ») : 30 premières secondes d'un fichier audio ou vidéo,
  accord obligatoire, état exporté en `.safetensors` par modèle à la première utilisation.
- Constat : estelle est la seule voix française de Pocket TTS ; les autres sont étrangères (à écouter).
- Non éprouvé (Pocket TTS absent du poste) : `export_model_state`, relecture du `.safetensors`,
  modèle `french_24l`. Essai sur la VM nécessaire.
- Q13 : idée sur les sous-titres incomplète.
- Suite : clonage de voix validé sur la VM après acceptation des conditions Hugging Face (modèle à accès
  restreint, `HF_TOKEN` dans `.env`) ; export / relecture `.safetensors` OK. Voix retenues : estelle et
  marius. Q13 résolue (sous-titres gravés, case décochée).
- Corrigé : un échec de préparation de voix donnait une erreur 500 muette ; une voix retirée du catalogue
  laissait ses voix générées marquées à jour (mélange de voix possible).

## 2026-10-27 — Interface compacte, suppression des projets
- `main` mis à jour (avance rapide jusqu'à `4842483`) à la demande de l'utilisateur.
- Barre de titre d'une ligne sur toutes les pages ; éditeur à la hauteur de l'écran (vidéo toujours
  visible, phrases qui défilent à droite, boutons sur une ligne à part). Validé (« c'est mieux »).
- Suppression d'un projet (idée de l'utilisateur) : croix à droite dans la liste, confirmation du
  navigateur, tout le dossier est effacé ; refusée (409) pendant une transcription ou un doublage, attend
  la fin d'une voix ou d'une correction en cours. Ouverte à tout utilisateur connecté (collègues).
- Suite : fusion `dev` → `main` par l'utilisateur, comptes des collègues ; puis HTTPS (Q12) ou Phase 5.

## 2026-10-27 — Phase 4 : service installé sur la VM
- `doublage@doublage` activé ; premier passage de `deploiement/mettre-a-jour` réussi (conteneur recréé,
  service relancé, `/sante` OK) ; le conteneur est bien tenu par systemd (`podman start --attach`).
- Q11 : une seule instance (production), pas de staging. Q12 réduite au HTTPS (port 8091 joignable depuis
  le réseau de l'hôpital).
- Bloque : mise en production = fusion `dev` → `main` par l'utilisateur, puis instance sur `main`.
  Non éprouvé : redémarrage complet de la VM.
## 2026-10-27 — Phase 4 : démarrage avec la VM, script de mise à jour
- Aperçu et exports validés par l'utilisateur sur la VM.
- `deploiement/doublage@.service` (modèle, une instance = un nom = un dossier `/srv/apps/<nom>`) remplace
  `doublage.service` ; il reprend en main un conteneur démarré par podman-compose.
- `deploiement/mettre-a-jour` : git pull, construction pendant que l'ancienne version tourne, remplacement du
  conteneur, relance du service, vérification de `/sante` (journal affiché en cas d'échec).
- `compose.yml` : nom du conteneur et de l'image paramétrés par `DOUBLAGE_NOM` (défaut `doublage`).
- Questions : Q11 (organisation test / production), Q12 (accès des utilisateurs, HTTPS).
- Non éprouvé sur la VM : installation du service et premier passage du script.
## 2026-10-27 — Phase 3 : exports complémentaires (fin de la Phase 3, hors tâche repoussée)
- Sous la vidéo doublée : liens « voix seule (WAV) » (bande son de la dernière génération) et sous-titres
  SRT / VTT, générés à la demande à partir du texte corrigé, aux timecodes des phrases d'origine (pas
  ceux de la voix décalée ou accélérée).
- Reste en Phase 3 : fusionner / couper / recaler (repoussé, Q10).
- Suite : Phase 4 (service systemd, staging, production) — étapes à faire sur la VM avec l'utilisateur.
## 2026-10-27 — Phase 3 : aperçu avec la nouvelle voix
- Accélération validée par l'utilisateur sur la VM. Fusionner / couper / recaler : repoussé (Q10).
- Aperçu : une fois la vidéo doublée générée, « Son de la vidéo : original / nouvelle voix » sous le
  lecteur de l'éditeur. Le lecteur change de source en gardant sa position ; texte sur l'image et liste
  restent synchronisés. « ▶ Original » repasse sur le son d'origine. Avertissement si des corrections ont
  été faites depuis la dernière génération.
- Choix : l'aperçu réutilise la génération de la vidéo doublée (l'assemblage vidéo sans ré-encodage ne
  prend que quelques secondes) plutôt qu'une piste audio synchronisée à part dans le navigateur.
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
