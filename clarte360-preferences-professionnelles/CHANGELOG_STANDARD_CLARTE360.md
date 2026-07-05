# CHANGELOG STANDARD CLARTE360

## v1.9.2-socle-clarte360 - 2026-07-05
- Correction bloquante : réintégration du chargement du questionnaire actif avant le démarrage après validation du code d'accès.
- Alignement RGPD sur le socle Moteurs Professionnels v1.8 : consentement unique avant code, texte RGPD complet, onglet "Protection des données et traçabilité".
- Ajout de l'affichage de traçabilité : session en cours, nombre de sessions, temps cumulé, historique des sessions, consentement RGPD avec date, heure et version du texte.
- JSON renforcé : conservation simultanée de `rgpd` et `rgpd_acceptance` pour compatibilité socle Clarté360.
- Aucune modification métier : questions, scores, dimensions, interprétations et logique de calcul inchangés.

## v1.9.1-socle-clarte360 - 2026-07-05
- Harmonisation initiale socle Clarté360 : JSON, contact, RGPD, timeout, PDF institutionnel.
