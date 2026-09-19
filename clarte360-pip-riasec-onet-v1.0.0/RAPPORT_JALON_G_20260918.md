# Rapport Jalon G - PIP RIASEC / O*NET Clarté360

## Base
Jalon F officiel récupéré depuis OneDrive. Aucune modification de Gestion des Actions dans ce chantier.

## Réalisé
- Outbox durable/idempotente `PIP-GA-OUTBOUND-1.0` avec réessai et conservation des erreurs.
- Signature HMAC prête pour le transport serveur-à-serveur.
- Émission PUBLIC `CONTACT_EMAIL_VERIFIED` immédiatement après validation du code e-mail.
- Contrat `CONTACT_UPDATED` disponible pour les enrichissements futurs.
- Question finale PUBLIC de demande de rappel et événement `CALLBACK_REQUESTED` sans score/profil/réponse.
- Suppression des émissions `TERMINE` trop précoces en fin de PIP ou O*NET.
- `TERMINE` ACCOMPAGNEMENT émis après ressenti et génération réussie des rapports.
- Persistance des PDF accompagnement avec SHA-256, taille et référence relative.
- Synthèse finale : versions PIP/banque/scoring, scores, rangs, code, O*NET éventuel, ressenti utile, documents.
- Aucune réponse brute PIP/O*NET dans les événements.
- Séparation CRM/étude renforcée : dataset étude v2 sans clé de jonction volontaire et `study_id` aléatoire indépendant.

## Hors périmètre volontaire
- Aucun changement du code de Gestion des Actions.
- Aucun endpoint Hub inventé : la livraison reste asynchrone par outbox, prête pour le worker/contrat du chantier Gestion des Actions.
- Aucun déploiement VPS.

## Tests
Voir `RAPPORT_TESTS_JALON_G_20260918.md`.
