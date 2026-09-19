# Rapport Jalon I — Recette finale liaison PIP / Gestion des Actions

## Base et périmètre
- Base exclusive : `3.0.0-I9-J2C-PIP-LIAISON-H-INTEGRATION`.
- Jalon I = gel fonctionnel, recette finale locale et préparation de livraison.
- Aucun changement fonctionnel apporté au code métier du Jalon H.
- Aucun changement Calendar / Teams.
- Aucun changement du programme PIP parallèle.

## Résultat des tests
La suite complète contient 358 tests. Pour respecter la limite d'exécution de l'environnement, elle a été exécutée en trois lots couvrant exactement les 58 fichiers `tests/test_*.py` :
- lot 1 : 156 réussis ;
- lot 2 : 91 réussis ;
- lot 3 : 111 réussis ;
- total : **358 réussis, 0 échec**.

Recette ciblée liaison PIP A à H + contrat RC8 : **62 réussis, 0 échec**.

## Contrôles fonctionnels couverts
- PUBLIC : premier contact, e-mail normalisé, reprise même e-mail, fusion des intérêts, ajout `PIP-RIASEC`, consentement marketing oui/non.
- Idempotence/sécurité : registre d'événements, collisions, retries, HMAC, absence de payload sensible persistant.
- Callback : activité CRM, date/heure, notification interne, absence de données PIP/étude, anti-doublon.
- ACCOMPAGNEMENT : lancement signé, champs lisibles, droits/scopes, statuts, résumé final strict, interdiction des réponses brutes.
- Documents : rapports PIP et O*NET, rattachement prescription/action/bénéficiaire, SHA/idempotence, droits existants.
- Études : lecture du stockage pseudonymisé, séparation CRM/étude, déduplication, exports contrôlés.
- Intégration H : compatibilité avec le contrat observé du PIP E1 et enveloppe cible documentée.

## Écart externe restant avant recette bout-en-bout VPS
Le PIP E1 audité ne produit pas encore les trois événements PUBLIC signés `CONTACT_EMAIL_VERIFIED`, `CONTACT_UPDATED`, `CALLBACK_REQUESTED` et ne transmet pas encore automatiquement les PDF vers Gestion des Actions. Gestion des Actions est prête à les recevoir. L'activation de ces émissions appartient au chantier PIP parallèle.

En conséquence, la candidate I est **validée techniquement en local**. La recette bout-en-bout de production ne pourra être déclarée complète qu'après raccordement de ces flux côté PIP et déploiement contrôlé sur VPS selon la procédure prévue.
