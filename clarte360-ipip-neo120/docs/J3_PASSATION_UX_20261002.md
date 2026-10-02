# J3 RC2 — Passation une affirmation à la fois

Date : 2026-10-02
Version : 0.8.0-RC2

## Objet
Remplacer l'affichage historique par blocs de 10 par une expérience bénéficiaire une affirmation à la fois, sans modifier le référentiel, le scoring, O6, l'interprétation, le ressenti ni le contrat Gestion des Actions.

## Implémentation
- Question X / 120 et barre de progression.
- Une seule affirmation visible.
- Échelle 1–5 issue directement du référentiel maître.
- PRÉCÉDENT / SUIVANT.
- Réponse obligatoire avant progression vers l'avant.
- Modification d'une réponse antérieure possible avant TERMINE.
- Sauvegarde serveur à chaque navigation.
- Position exacte `current_item` persistée.
- Lecture compatible des anciennes sauvegardes `current_block` de RC1/J1/J2.
- Aucun score, domaine ou facette exposé pendant la passation.
- Ajustements responsive pour smartphone.

## Non-régression
Le métier IPIP reste gelé. Le composant historique `block_items` est conservé uniquement pour compatibilité des tests/anciens composants ; il n'est plus utilisé par l'interface RC2.
