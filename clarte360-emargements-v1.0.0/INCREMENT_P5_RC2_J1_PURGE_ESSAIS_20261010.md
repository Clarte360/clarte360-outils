# CLARTÉ360 — Gestion des Actions — J1 / P5-RC2

**Jalon intermédiaire de préparation, non installable directement sur le VPS**.
Source vérifiée : `clarte360-gestion-actions-v3.0.0-P5-RECETTE-RC1.zip`, SHA-256 `48122aa71dfb4310a4c3c089b469377d84b58683343216ea1c3aa7a263ea8574`, GitHub `b2dd9944da107a2bd46df0db3419425cf0744406`.

## COR-013 — Objectif

La suppression P5-RC1 laissait des événements qualité (`quality_events`), leurs CAPA et messages, voire certains fichiers, malgré le retrait de l'action. Le circuit J1 réserve la suppression **aux dossiers explicitement attestés fictifs par un administrateur**, jamais au seul titre contenant « ESSAI ».

## Nouveau circuit

1. Sur la page Paramètres de l'action, ouvrir « Supprimer un dossier d’essai (contrôle renforcé) » : inventaire des dépendances, documents et anciennes fiches globales sans action.
2. L'administrateur atteste explicitement l'absence de données réelles ou d'obligations de conservation ; saisit `JE CERTIFIE ESSAI <ref>` avec sa justification et son mot de passe.
3. La prévisualisation est recalculée après cette attestation. Toute modification de l'action, de ses références, des statuts et documents invalide l'attestation et oblige à recommencer.
4. Deuxième confirmation écrite `SUPPRIMER ESSAI <ref>` et vérification du mot de passe administrateur.
5. Journal durable `action_purge_journal` en statut PREPARED, fichiers exclusivement concernés déplacés en quarantaine, transaction SQL avec contrôle d'intégrité, puis nettoyage des fichiers en quarantaine.
6. Si échec SQL/fichier : restauration des fichiers déjà déplacés et refus de déclarer un succès. Si interruption après COMMIT : reprise du nettoyage depuis le journal. Vérification/reprise accessible depuis la même rubrique.

## Couverture SQL et fichiers

- Suppression explicite des `quality_events`, `quality_event_actions`, `quality_event_messages`, `quality_issues`, `improvement_actions`, `quality_review_points`, `document_notifications` et audit d'action, en plus des suppressions en cascade existantes.
- Vérification des dépendances HOT/COLD, signatures, créneaux, intervenants, bénéficiaires, outils, autorisations Client et fichiers de reporting ; les personnes/contacts globaux restent partagés.
- `stored_files` préservé s'il est utilisé dans une autre action ou dans un dossier professionnel ; fichier supprimé seulement si la dernière référence est retirée. Les chemins externes au répertoire de données et les chemins physiques partagés bloquent la purge.
- Les fiches qualité historiquement détachées (`action_id IS NULL`) ne sont **pas** attribuées ou supprimées par déduction : contrôle en lecture seule et analyse de provenance requise avant décision.
- Les sauvegardes PRA ne sont **jamais** purgées par ce circuit. Le journal de destruction minimal de l'action d'essai demeure dans la base technique.

## Fichiers modifiés/ajoutés

- `purge_guard.py` : nouveau moteur, prévisualisation, certification, garde-fous, journal SQL/fichiers, récupération.
- `services.py` : remplacement de l'ancienne purge non transactionnelle par un délégataire strict.
- `db.py` : deux tables additives pour la certification et les états de purge (schéma de 110 à 112 tables métier).
- `app.py` : écran de prévisualisation, certifications et double confirmation, accessible uniquement sur Paramètres.
- `tests/test_p5_rc2_j1_purge.py` : nouveaux tests et pannes simulées.
- `tests/test_v111.py`, `tests/test_v2_increment2_quality.py` : anciens tests de suppression adaptés au circuit sécurisé.

## Réserves / prochaine étape

J1 est un travail sur base fictive, **pas** une autorisation de suppression réelle, de modification de GitHub ni de déploiement VPS. Aucune réattribution automatique des orphelins anciens, aucun nettoyage de données historiques sans preuve de filiation. Les parcours web finaux, la restauration PRA et les obligations de conservation restent à recetter avant l'unique installation finale P5-RC2.

À la reprise de J2, repartir du ZIP J1 validé par les tests, pas d'une ancienne version ni du dépôt GitHub P5-RC1. Consulter le registre 0.9 inchangé et le POINT DE REPRISE officiel avant toute modification.
