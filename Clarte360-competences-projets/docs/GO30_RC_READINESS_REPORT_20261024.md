# GO30 — Rapport de préparation Release Candidate

**Date :** 24 octobre 2026  
**Candidate évaluée :** `0.4.29-go29-work`, schéma 13  
**Référentiel GO30 :** ZIP/package propre de recette, rapport de tests, zéro anomalie bloquante connue, procédure d’installation/rollback, puis GO pour recette utilisateur.  
**Dernier jalon officiellement validé :** GO21 RC2. GO22 à GO31 ne sont pas déclarés validés.

## Décision

**NO GO — le lancement de la recette utilisateur n’est pas autorisé à ce stade.**

Le paquet local contient des preuves utiles et une démonstration fictive, mais il n’est pas raccordé à une copie de GDA/Émargement testable. Aucun environnement intégré de recette n’est disponible ici. Le test du parcours réel accompagné/bénéficiaire, des documents et des permissions GDA ne peut donc pas commencer. L’absence de test intégré est un prérequis bloquant à lever; elle ne doit pas être présentée comme « zéro anomalie bloquante ».

## Vérification des critères GO30

| Critère | État constaté | Preuve / écart |
|---|---|---|
| Package propre, identifiable et reproductible | Partiel | ZIP candidate `0.4.29`, données de démonstration fictives, procédure locale présente. Le nom et le guide antérieurs laissaient entendre une recette GO30 alors que le raccordement réel est absent; le guide est corrigé en « préparation pré-RC ». |
| Rapport de tests | Partiel | 330 tests automatisés réussis; compilation Python réussie; 30 contrôles ciblés multi-rôles; smoke Streamlit local avec santé `ok` et liens signés synthétiques HTTP 200. Ce sont des contrôles locaux isolés. |
| Zéro anomalie bloquante connue | Non démontré | Aucune anomalie bloquante logicielle n’a été observée dans les tests locaux rapportés. Mais les fonctions GDA, les API/IA en direct, l’instance VPS/navigateur et le parcours humain intégré n’ont pas été testés. Il est donc impossible de certifier le critère global « zéro bloquante » pour la RC intégrée. |
| Procédure d’installation et de rollback | Partiel | Les consignes décrivent l’installation locale fictive et un déploiement temporaire hypothétique. Le raccordement GDA et le rollback d’une copie réellement installée n’ont pas été exécutés ni validés. |
| GO pour recette utilisateur | **Non** | Pas de GDA/Émargement de test raccordé et vérifié, pas d’URL de recette intégrée, pas de revue des parcours complets par les deux rôles. |

## Rapport de tests disponible

- Suite complète locale : **330 réussis**, selon le relevé du 24/10/2026.
- Contrôles ciblés session/interface bénéficiaire/intersession : **30 réussis**.
- Compilation Python de l’application, outils et patch candidat : réussie.
- Smoke local Streamlit : endpoint `/_stcore/health` à `ok`; liens signés synthétiques accompagnateur et bénéficiaire en HTTP 200.
- Vérification locale sauvegarde/restauration SQLite : intégrité et présence du dossier fictif restauré contrôlées.
- Aucun test réel dans GDA/Émargement, sur VPS, dans un navigateur connecté à l’instance distante, sur les API France Travail/OpenAI ou sur le flux de retour/archivage GDA n’est attesté.

Ces résultats ne sont pas un rapport de recette métier et n’autorisent pas à annoncer GO28, GO29 ou GO30 validés.

## Écarts bloquants avant émission du GO

1. Mettre à disposition une copie isolée de GDA/Émargement et la base correspondante, avec un dossier fictif, un accompagnateur et un bénéficiaire fictifs.
2. Installer le bridge et le patch `CP_V1` sur cette copie; vérifier l’activation du seul outil candidat dans l’environnement de test.
3. Fournir l’URL de recette intégrée et les secrets/identifiants de test au moyen du coffre prévu, sans les inclure dans le ZIP.
4. Exécuter et consigner les tests de lancement, rôles, prescription/affectation, droits documentaires, lien manuel, export/retour idempotent, révocation et rollback GDA.
5. Exécuter les parcours humains complets accompagnateur et bénéficiaire suivant A3; compléter API/IA réelles avec données synthétiques, contrôles navigateur/VPS, documents PDF/DOCX, sauvegarde/restauration et suivi à six mois selon le périmètre de recette convenu.
6. Mettre à jour ce rapport avec les anomalies ouvertes et leur sévérité. Le GO ne pourra être émis qu’après démonstration d’un paquet cohérent, d’un rollback praticable et d’aucune anomalie bloquante ouverte.

## Portée du paquet existant

Le ZIP actuellement nommé `CLARTE360_COMPETENCES_PROJETS_GO30_RECETTE_HUMAINE_CANDIDATE_0.4.29_20261024.zip` doit être traité comme **support de prévisualisation locale / préparation pré-RC uniquement**. Il n’est ni une RC GO30 intégrée, ni une demande de test utilisateur, ni une livraison de production. GO21 RC2 demeure le dernier jalon officiellement validé.
