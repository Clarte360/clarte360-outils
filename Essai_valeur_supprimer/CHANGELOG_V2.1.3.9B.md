# Clarté360 – Recherche de mes valeurs – V2.1.3.9B-preproduction

## Objet
Activation conjointe des deux voies du Module 4 avec un premier moteur complet de questionnement vertical, de recherche du mot et de conservation d'une hypothèse.

## Évolutions principales
- Voie 1 entièrement active à partir d'une situation vécue.
- Voie 2 entièrement active avec génération d'une question personnalisée à partir de l'ensemble du contexte disponible.
- Mémoire commune des couples question + réponse validée, quelle que soit la voie utilisée.
- Questionnement vertical limité : deux relances maximum avant la recherche du mot.
- Recherche prioritaire du mot par le bénéficiaire.
- Seconde recherche du mot possible lorsque le premier terme n'est pas suffisamment exploitable.
- Demande d'accord avant toute proposition de mots par Clarté360.
- Proposition de zéro à trois mots maximum, accompagnés de leur définition du référentiel.
- Une idée explorée = une seule hypothèse éventuellement retenue.
- Enregistrement exclusivement dans le panier Hypothèses.
- Nouveau cycle complet obligatoire pour rechercher une autre valeur.
- Contrôle des doublons avec les valeurs validées, à examiner, à revoir, les hypothèses et les refus.
- Invitation non contraignante à examiner les hypothèses uniquement à partir de trois hypothèses et lorsque valeurs validées + hypothèses atteint au moins huit.
- Conservation de toutes les grandes consignes avec écoute audio.
- Toutes les réponses ouvertes utilisent le moteur partagé texte/voix/correction/validation.

## Architecture IA
- Les règles invariantes de sécurité et de posture restent celles de RVC360.
- L'algorithme métier détaillé du Module 4 reste dans l'application afin que RVC360 ne bloque pas l'évolution métier et ne devienne pas spécifique à une seule application.
- Les appels API utilisent des schémas JSON stricts et ne modifient jamais directement les données finales.

## Limites de préproduction
- La qualité du questionnement et des hypothèses doit être testée sur plusieurs profils réels.
- Le comportement exact de la navigation vers le Module 3 après le seuil devra être confirmé en test d'interface.
