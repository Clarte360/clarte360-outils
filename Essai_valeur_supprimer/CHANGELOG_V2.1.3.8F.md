# Clarté360 - Recherche de mes valeurs - V2.1.3.8F-preproduction

## Objet
Version de stabilisation préparant le passage à la version 9.

## Corrections principales

- Correction linguistique obligatoire pour toutes les réponses libres des modules 1, 2 et 3 avant analyse ou reformulation éventuelle.
- Distinction maintenue entre correction orthographique et reformulation de fond.
- Traitement contextuel des noms de valeurs saisis ou dictés : retrait des articles, hésitations et répétitions orales.
- Détection prudente des erreurs de transcription proches d'une valeur du référentiel, par exemple « Loopisme » vers « Optimisme », toujours avec validation explicite du bénéficiaire.
- Une transcription manifestement impropre au champ « nom de valeur » ne peut plus être conservée directement lorsqu'une correction contextuelle est proposée.
- Un seul clic sur « Transcrire et comparer » suffit : le résultat est affiché dans le même cycle d'exécution.
- Conservation de la présence réelle dans le référentiel comme fait calculé par Python, indépendant de l'analyse IA.
- Référentiel lu dynamiquement sans dépendance à un nombre fixe de lignes. Le fichier livré contient 318 entrées.
- Rapport PDF : titres solidaires du contenu suivant, garde-fous de pagination et prévention des titres isolés en bas de page.
- Version du schéma JSON portée à 2.1.3.8F.

## Nettoyage de la livraison

Les anciens changelogs, rapports d'audit et rapports de tests intermédiaires ont été retirés du ZIP. La livraison conserve uniquement les fichiers utiles à l'exploitation, au déploiement et au contrôle de la version F.

## Correctif reprise d'une valeur en attente

- Une valeur sélectionnée dans « Valeurs à examiner » passe désormais en mode `examen_attente`.
- Elle peut être renommée, redéfinie et retraitée intégralement sans être bloquée comme son propre doublon.
- La migration des anciens JSON ne recrée plus la valeur à chaque rerun Streamlit pendant son examen.
- La décision finale nettoie les anciens marqueurs contradictoires (`abandonnee`, `discarded`, `en_cours_analyse`) afin d'éviter une nouvelle réapparition.
- Compatibilité maintenue avec les JSON historiques V2.1.3.7, notamment celui de Solange.
