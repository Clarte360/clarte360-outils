# Jalon P2 — Documentation avancée — RC1 — 09/10/2026

## Base et objectifs

Base exclusive : `clarte360-gestion-actions-v3.0.0-P1-DROITS-DOCS-RC1.zip` validée implicitement par GO P2.
Une **refonte documentaire additive**, sans refonte des menus validés (P3), ni espace Client (P4), ni intégration Compétences & Projets (GO-14 gelé).

## Nouvelles fonctionnalités

- Une pièce documentaire se définit par contexte (action, bénéficiaire, participant, audience, catégorie, nom de pièce normalisé) et empreinte SHA-256.
- Même pièce et mêmes octets : même référence ; contenu changé : nouvelle version liée à l'ancienne, originaux conservés.
- Nouvelle version en brouillon : ancienne version publiée maintenue jusqu'à une publication explicite.
- Validation (À vérifier / Validé / Finalisé) séparée de publication ; version finalisée modifiable uniquement par création d'une nouvelle version avec motif explicite.
- Le bénéficiaire ne voit jamais un brouillon ou un document d'une autre action ; l'intervenant est limité par affectation, compte actif et habilitation métier P1.
- Notification dans l'espace du destinataire habilité lors d'une nouvelle publication ; lecture marquée personnellement. Emails documentaires désactivés tant que `[documents] email_notifications_enabled = true` n'est pas explicitement ajouté et que le destinataire n'a pas donné son opt-in ; message non nominatif, sans contenu ni lien de téléchargement non signé.
- Export d'une action en ZIP contenant exclusivement des pièces téléchargeables selon le rôle ; manifeste ID/version/provenance/SHA-256.
- La progression visible indique seulement les étapes de traitement serveur, pas la progression réseau du navigateur.

## Base de données et migrations

Ajouts exclusivement additifs, exécutés par `init_db()` : tables `document_notifications`, `document_notification_preferences`, colonnes de workflow/versions sur `document_references`, index de clé logique active. Aucun effacement des anciens enregistrements. Les documents anciens sont considérés publiés par défaut si et seulement s'ils passent les contrôles de visibilité P1 ; les flux existants n'ont pas à être réimportés.

**Important** : aucune migration n'a été exécutée sur VPS ni sur sa base réelle. Avant production : sauvegarde selon PRA du dossier `99 BACKUP VPS CLARTE360`, restauration isolée testée, copie de recette, vérification des schémas et des fichiers existants ; ne jamais écraser le dossier `data/` historique (~1,2 Go).

## Limites et décisions restant à figer

- Confidentialité QAP en contexte multi-intervenant : la règle validée de partage avec les formateurs habilités est en place, le cas coordinateur/référent multi-formateurs reste à formaliser.
- Retention/destruction des documents de bilan de compétences : classes préparatoires uniquement, aucune purge automatisée ; arbitrage RGPD / Code du travail préalable obligatoire.
- Notifications SMTP live et Microsoft Teams/Graph non recettées en intégration réelle.
- Les droits côté futur client, le lancement générique des applications et le flux documentaire bidirectionnel sont préparés par la conception, mais seront recettés aux jalons appropriés P3/P4/P5 puis GO-14.
- La génération PDF / signature ou validation règlementaire n'est pas assimilée à un statut documentaire interne.

## Recette hors production

Tests unitaires, sécurité, régression en lots ; tests depuis une extraction propre du ZIP, `compileall`, vérification des exclusions ZIP ; voir le journal de recette joint. Vérifier manuellement les écrans avant toute mise en production.

## Gouvernance

Livraison en ZIP complet propre + rapport Word + matrice Excel + manifeste + journal de tests dans OneDrive Clarté360 `11 EMARGEMENTS/0 DOSSIER DE TRAVAIL/P2 DOCUMENTAIRE AVANCE RC1 20261009`. La racine conserve le ZIP de référence fiable jusqu'au GO suivant. **GitHub, import/commit/push : uniquement le propriétaire. Aucun déploiement VPS.**
