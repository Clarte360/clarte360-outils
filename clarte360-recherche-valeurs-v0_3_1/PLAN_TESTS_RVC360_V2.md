# Plan de recette préproduction – V2.1.2

## Navigation et recalcul

1. Réaliser un parcours jusqu’aux résultats.
2. Revenir à « Faisons connaissance » et modifier une réponse autre que le prénom.
3. Vérifier que les hypothèses et validations issues de l’application sont invalidées, tandis que les valeurs validées avec l’accompagnateur restent présentes.
4. Refaire l’exploration puis modifier une réponse ancienne depuis « Modifier une réponse précédente ».
5. Vérifier que la conversation reprend à la question modifiée et que tout l’aval est recalculé.
6. Modifier uniquement le prénom d’usage et vérifier qu’aucun recalcul métier n’est déclenché.
7. Modifier la définition personnelle d’une valeur et vérifier que seule sa validation est remise à zéro.
8. Supprimer une valeur découverte personnellement et vérifier la disparition de ses validations et de son affichage latéral.

## Voix

1. Tester chaque question ouverte au clavier puis à la voix.
2. Prononcer volontairement : « euh… je… je souhaite davantage de liberté, enfin je veux dire de liberté dans mes choix ».
3. Vérifier l’affichage séparé de la transcription brute et de la proposition corrigée.
4. Choisir successivement la transcription brute, la correction proposée et une correction manuelle.
5. Vérifier qu’aucune réponse n’est utilisée avant validation.
6. Demander une reformulation puis conserver le texte initial.
7. Réenregistrer après une mauvaise transcription.
8. Désactiver la lecture vocale globale et vérifier la disparition des boutons d’écoute.

## Questionnaire bénéficiaire

Vérifier la présence des questions distinctes : situation actuelle, parcours, personnes ou activités importantes, passions, projets ou changements, attente vis-à-vis de la recherche.

## JSON de reprise

1. Sauvegarder au milieu d’une validation HEC.
2. Importer le JSON.
3. Vérifier l’accueil personnalisé puis la reprise exacte de la page, de la valeur, du niveau de validation, de la navigation et des réponses.

## Clôture

1. Modifier une donnée après le contrôle de complétude.
2. Vérifier le blocage de la clôture.
3. Refaire le contrôle de complétude.
4. Vérifier la génération du PDF et du JSON final.
5. Importer le JSON final et confirmer le mode lecture seule sans appel IA.
