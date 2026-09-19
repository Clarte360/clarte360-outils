# RAPPORT — JALON G — ETUDES PIP/O*NET

## Base
Jalon F `3.0.0-I9-J2C-PIP-LIAISON-F-PDF-DOCUMENTS`.

## Réalisé
- stockage d'études PUBLIC pseudonymisé configurable et contrôlé en lecture seule ;
- état de disponibilité visible dans l'interface administrateur ;
- filtrage renforcé des données identifiantes et de toute clé de rapprochement CRM/étude ;
- déduplication par pseudonyme `study_id` ;
- conservation des fonctions d'analyse/export déjà présentes ;
- exports limités aux passations avec consentement recherche et journalisés ;
- exemple de configuration VPS documenté.

## Frontière PIP
Le lieu/transport final de production du dataset reste à confirmer avec le chantier PIP au jalon H. Gestion des Actions ne produit ni ne recalcule les réponses/scores PIP/O*NET.

## Tests
63 tests ciblés réussis, incluant les jalons A à G, études I9-F, connecteur RC8, CRM et documents. Compilation Python réussie.
