# J4 — Notifications et échanges transversaux (10/10/2026)

Source fiable : P5-RC2-J3-CANDIDATE, SHA-256 c613a5027f9b961675ce8cb5a88fd1f7977607e56bf8c4cf32878b1e56ed93c3.

## Livrable
- Schema additif `workspace_notifications` et `external_notification_identity_links` ; aucune table historique détruite.
- Notifications role/action/personne à contenu minimisé ; affichage et ouverture contrôlés dans les quatre espaces.
- Origines internes : Qualité nouvelle fiche/réponse/statut/CAPA ; dépôt/publication/partage des documents ; planning.
- Les réponses réellement adressées à l'auteur restent dans un fil consultable ; notes internes masquées.
- Déduplication par source_event_id + destinataire et contrôle dynamique de l'habilitation.
- Avant activation du compte Client, l'alerte documentaire est conservée mais n'est pas exposée.
- Gestion Clients / Fournisseurs n°17 : une interface locale événementielle v1 est préparée ; elle ne déclenche aucun accès réseau et ne partage pas de tables CRM. L'authentification du connecteur et les essais inter-applications restent obligatoires en J8/J10/J11.

## Tests / portée
- 27 scénarios J4 dont notifications de qualité, non-divulgation, révocation, Client avant activation, idempotence, planning, documents, purge J1 et événement futur GC17.
- Campagne complète : 754/754 réussis hors production ; voir trace de tests archivée séparément.
- Restrictions : aucun déploiement intermédiaire, aucun changement GitHub/VPS ; recette réelle par le propriétaire seulement après ZIP final.
- À vérifier sur version Streamlit installée : libellé natif de limite de fichier 50 Mo sur un signalement plafonné côté métier à 10 Mo ; limiter le composant ou harmoniser sa présentation sans réduire les dépôts documentaires métier à 25 Mo.

## Fichiers touchés
- `app.py`, `services.py`, `client_portal.py`, `db.py`, `CHANGELOG.md`, test historique de J3 ; plus `workspace_notifications.py` et nouveaux tests J4.
- Aucune évolution appliquée aux Frameworks officiels en attente de validation transversale ; doctrine disponible dans la note de contrat d'interface de J4.
