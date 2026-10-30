# Clarté360 — Compétences & Projets professionnels

## Candidate D5 GO30 — version 0.4.30

Cette arborescence contient l’application Python D5 destinée à fonctionner sur le VPS Clarté360 et à être ouverte depuis Gestion des Actions. Le point d’entrée web est `app.py` : il charge l’identité de l’application, résout le contexte sécurisé de lancement puis ouvre le dossier d’accompagnement.

Le raccordement prévu à Gestion des Actions utilise le connecteur CP_V1 et le bridge GDA. Les modules et exemples de configuration sont dans `clarte360_cp/`, `integration/`, `config/` et `deploy/`. Les secrets restent sur le VPS et ne doivent jamais être ajoutés au dépôt.

## État réel

- Version : `0.4.30-go30-dual-candidate`.
- Statut : candidate non déployée et non validée GO30.
- Le dépôt contient le code de l’application web, ses modules Python, ses migrations et ses tests.
- Le raccordement doit encore être installé et vérifié sur le VPS avec Gestion des Actions, le DNS et HTTPS selon le document FW VPS.
- La présence du code et des tests automatisés ne prouve pas que les API, l’IA, le lancement depuis Gestion des Actions ou les échanges de documents fonctionnent en réel.
- L’adresse web prévue est `https://competences-projets.clarte360.com` ; elle ne doit être annoncée comme opérationnelle qu’après vérification sur le VPS.

## Mise en service

Le service web VPS doit lancer `app.py` avec l’environnement Python défini par la procédure FW VPS. Cette application ne se déploie pas en lançant un fichier Windows `.cmd`. Les étapes DNS, service, secrets, reverse proxy HTTPS, contrôle de santé et retour arrière sont celles du FW VPS et des documents de déploiement référencés ci-dessous.

## Vérifications et recette

- Guide de mise en service : `docs/DEPLOIEMENT_GO30_CANDIDAT.md`.
- Mode opératoire de recette connectée CP/GDA : `docs/MODE_OPERATOIRE_GO30_CP_GDA.md`.
- Avis d’intégration : `docs/GO30_AVIS_INTEGRATION_CP_GDA.md`.
- État de préparation et limites : `docs/GO30_RC_READINESS_REPORT_20261024.md`.

GO30 ne sera validé qu’après installation sur le VPS, essais navigateur avec Gestion des Actions et les intégrations réelles, compte rendu complet, zéro anomalie bloquante et contrôle du retour arrière.

Les notes historiques GO21–GO29 sont conservées dans `docs/README_HISTORIQUE_GO21_GO29.md`. Elles ne décrivent pas l’état courant de la candidate 0.4.30.
