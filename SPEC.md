# Doublage — Descriptif de l'application

## Objectif
Remplacer la voix d'un tutoriel vidéo (démonstration d'un logiciel, commentée en direct par son auteur)
par une **voix de synthèse** claire, à partir d'un texte relu et corrigé, tout en gardant la
**synchronisation avec l'image** (les clics et les manipulations à l'écran).

Le traitement est **entièrement interne à l'établissement** : aucune donnée n'est envoyée à un service extérieur.

## Utilisateurs
- 2 à 3 personnes : les auteurs des tutoriels.
- Accès depuis le réseau interne, via un navigateur.
- Connexion par identifiant et mot de passe (sécurité simple : le site peut être visible de tout le réseau
  interne, mais seuls les utilisateurs ayant un compte y accèdent).

## Parcours utilisateur
1. **Dépôt** d'un fichier vidéo complet (MP4, MKV, MOV…).
2. **Transcription automatique** : la piste audio est extraite et envoyée au serveur Whisper
   de l'établissement (modèle finetuné maison). Résultat : une liste de phrases, chacune avec
   son timecode de début et de fin.
3. **Éditeur sur l'image** :
   - la vidéo est affichée en fond ;
   - le texte de la phrase en cours est affiché sur l'image, au timecode correspondant
     (à la manière d'un sous-titre) ;
   - l'utilisateur peut modifier le texte directement, la vidéo servant de repère ;
   - une liste des phrases (timecode + texte) permet de naviguer : cliquer sur une phrase
     place la vidéo à ce moment ;
   - possibilité d'écouter l'original et la version synthétique d'une phrase ;
   - possibilité de fusionner / couper des phrases et d'ajuster les timecodes.
4. **Génération de la voix** avec Pocket TTS, phrase par phrase.
5. **Calage** : chaque phrase synthétique est placée à son timecode d'origine. Si elle est trop
   longue pour son créneau, l'application le signale et propose une solution (accélération
   légère, débord sur le silence suivant, ou reformulation).
6. **Export** : la vidéo d'origine avec la nouvelle bande son (et éventuellement la piste audio
   seule et un fichier de sous-titres).

## Briques techniques
- **Transcription** : serveur Whisper interne (modèle finetuné), API compatible OpenAI
  (`/v1/audio/transcriptions`, réponse `verbose_json` avec segments horodatés). Accès via un module
  « adaptateur » isolé.
- **Synthèse vocale** : [Pocket TTS](https://github.com/kyutai-labs/pocket-tts) (Kyutai), sur processeur,
  modèle `french` (ou `french_24l`, plus fin mais plus lent).
- **Vidéo / audio** : ffmpeg (extraction, assemblage, ré-encodage de la bande son).
- **Application** : application web Python hébergée sur la VM `svp-recvoc-a3p`, dans des conteneurs
  **Podman** (podman-compose), isolée des applications déjà présentes.

## Voix
- **Version 1** : voix « estelle » (fournie avec Pocket TTS).
- **Plus tard** : choix parmi un catalogue plus large de voix, et éventuellement des voix
  créées à partir d'un échantillon (avec l'accord de la personne enregistrée).

## Masquage des données patients
Certains logiciels (ex. Lifen) n'ont pas d'environnement de test : leurs tutoriels montrent de vraies données
patients. Ces données doivent être **cachées de façon sûre** dans la vidéo exportée. Pour tous les autres
logiciels, la règle reste de tourner sur l'environnement de test avec des patients fictifs.
- **Boîte opaque** (pas de flou, qui laisse deviner un texte) : rectangle dessiné sur la vidéo en pause,
  visible entre deux timecodes, d'une couleur de fond choisie par l'utilisateur (pipette sur l'image).
- **Texte de remplacement** facultatif dans la boîte (données fictives : « DUPONT Jean »…), couleur et taille
  choisies : on remplace la donnée vue par une autre, pour que l'explication reste lisible.
- **Défilements d'écran** : boîte qui suit le contenu (positions posées par l'utilisateur à quelques images,
  interpolées en ligne droite entre elles) ; sur chaque image, la boîte gravée couvre aussi sa place sur les
  images voisines. Pour un défilement trop irrégulier : une grande boîte fixe sur la zone qui défile.
- Aperçu dans l'éditeur, boîtes gravées dans l'image à l'export (ré-encodage), et dans l'image d'aperçu
  des sous-titres.
- **Vérification image par image** de la vidéo avant diffusion (aucune image ne doit laisser voir une donnée).
- Les vidéos de l'enregistreur de Windows sont à fréquence d'images fixe (30 ou 29,97 i/s, mesuré sur la VM) :
  les débuts et fins de boîtes sont calés sur les images de chaque vidéo, sans conversion au dépôt.
- La vidéo source reste en clair sur la VM, gérée par les deux utilisateurs : ils suppriment le projet
  (vidéo source, audio et fichiers de travail compris) une fois la vidéo doublée exportée. Pas de suppression
  automatique. Usage validé par le DPO et la DSI (Q16, Q17).

## Hors périmètre (pour l'instant)
- Traduction dans une autre langue.
- Montage vidéo (coupes, effets), hormis le masquage des données patients ci-dessus.
- Détection automatique des données à masquer (OCR, visages) : un oubli serait une fuite invisible.
- Accès depuis l'extérieur de l'établissement.
