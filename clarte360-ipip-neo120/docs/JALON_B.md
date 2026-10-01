# Jalon B — Questionnaire
Version 0.2.0 — 20 septembre 2026

## Périmètre livré
- 120 items français V1.0 chargés exclusivement depuis le référentiel actif.
- Ordre 1–120 conservé.
- Échelle 1–5 issue du référentiel, sans recodage métier à ce jalon.
- 12 blocs de 10 items, réponses obligatoires avant passage au bloc suivant.
- Retour au bloc précédent possible.
- Sauvegarde atomique serveur et reprise par run_id.
- Version du référentiel attachée à la sauvegarde ; reprise refusée en cas de dérive de version.
- Aucun score intermédiaire, aucune facette, aucun domaine, aucune interprétation affichés.
- O6 utilise uniquement les quatre items non politiques du référentiel Clarté360 V1.0.

## Hors périmètre volontaire
Scoring (Jalon C), interprétation (D), rapport/ressenti (E), liaison Gestion des Actions (F), recette intégrée (G).

## Critère de sortie
Les tests automatisés A+B doivent être verts. Le questionnaire doit couvrir 120 items exactement une fois et la sauvegarde/reprise doit être déterministe.
