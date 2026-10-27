# Règles de travail pour Claude

## Langue
- Tout en français : documents, messages de commit, commentaires dans l'interface.
- Le code (noms de variables, fonctions) peut rester en anglais.

## Début de chaque session
1. Lire SPEC.md, PLAN.md, QUESTIONS.md et les 2-3 dernières entrées de JOURNAL.md.
2. Lire IDEES.md : intégrer chaque nouvelle idée dans PLAN.md (à la bonne phase), puis la déplacer dans « Intégrées ».
   Si une idée est ambiguë ou contredit SPEC.md, poser la question dans QUESTIONS.md au lieu de deviner.
3. Lire les réponses dans QUESTIONS.md, les reporter (SPEC/PLAN), et déplacer les questions dans « Résolues ».

## Pendant la session
- Prendre la prochaine tâche `[ ]` non bloquée de PLAN.md, dans l'ordre des phases.
- Petites étapes : une tâche = un commit, avec tests qui passent (`pytest`).
- Ne jamais dépendre du vrai serveur Whisper dans les tests : utiliser l'adaptateur simulé.
- Une décision qui revient à l'utilisateur → l'écrire dans QUESTIONS.md et passer à une autre tâche.
- Ne pas ajouter de fonctionnalité absente de SPEC.md / PLAN.md.

## Fin de chaque session
- Mettre à jour les cases de PLAN.md.
- Ajouter une entrée en haut de JOURNAL.md : ce qui a été fait, ce qui bloque, la suite.
- Commit et push sur la branche de travail.

## Branches et déploiement
- Travail sur la branche `dev` ; `main` = version validée par l'utilisateur.
- Aucun déploiement en production sans validation explicite de l'utilisateur.

## Données
- Aucune vidéo, transcription ou audio ne doit être envoyé à un service extérieur à l'établissement.
- Ne pas committer de vidéos réelles ni de secrets (`.env`).
