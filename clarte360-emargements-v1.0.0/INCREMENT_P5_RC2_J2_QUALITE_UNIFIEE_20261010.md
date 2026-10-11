# P5-RC2 - J2 : circuit Qualite de reference, statuts et historique

Date : 10 octobre 2026. **Base : ZIP J1 valide ; ce livrable n'est pas deployable sur VPS.**

## Perimetre

J2 du plan officiel P5-RC2 : COR-006, COR-014, COR-015, AME-007 et AME-011. Convergence des fiches et signaux Qualite, CAPA, suivis et correspondances, sans supprimer les historiques preexistants. Les tableaux de questionnaires et notes /5 sont prevus en J3 ; les notifications des utilisateurs et documents en J4. Le site en production reste P5-RC1.

## Evolution des donnees - additive

- `quality_source_links` : rapprochement explicite entre un evenement Qualite de reference et une fiche ancienne (`TRAINER_REPORT`, `BENEFICIARY_REPORT`, `QUALITY_ISSUE`) ; contrainte d'unicite de source et controle de l'action et de l'identite.
- `quality_event_history` : revisions horodatees non ecrasees pour creation, decisions, statuts, responsable, messages, et CAPA.
- `quality_capa_source_links` : provenance explicite des anciennes `improvement_actions` rapprochees des nouvelles CAPA.
- Aucun effacement automatique des historiques anciens ; aucune fusion probabiliste de sources a partir des libelles. Les donnees non rapprochees restent visibles pour instruction humaine.

## Parcours administratif

- La Qualite generale et la Qualite de chaque action appellent le **meme composant de fiche** (`render_quality_case_workbench`).
- Fiche de reference : statut, responsable, gravite, urgence, echeance, analyse, decision motivee de classement/refus, mesures et CAPA.
- Correspondance et historique sont conserves sous forme de messages successifs et de revisions avec avant/apres.
- Les nouveaux signalements Intervenant/Beneficiaire restent compatibles avec leurs anciens espaces ; le statut et la derniere reponse y sont projetes depuis le circuit de reference.
- Les archives anciennes non rapprochees sont exposees dans un volet specifique et un rattachement exige une validation administrative explicite et controlee.

## Compatibilite J1

- L'inventaire et la purge securisee d'une action d'essai incluent les nouvelles tables J2 ; les pieces liees a une action temoin restent intactes.
- Conserver l'archivage des actions reelles selon la reglementation applicable. Pas de purge retroactive d'anciennes fiches orphelines.

## Controle et gouvernance

- Tests specifiques J2 : `tests/test_p5_rc2_j2_quality_unification.py` (15 cas) ; `tests/test_rc2_1_transversal_tables.py` adapte a la nouvelle interface sans renoncer aux controles anciens.
- Campagne complete `PYTHONPATH=. pytest -q` et simulation de donnees fictives exigibles avant validation J2 ; resultats dans le dossier officiel du jalon.
- Aucun push/commit GitHub par l'assistant. Le proprietaire intervient SEUL sur GitHub a la livraison de l'unique ZIP FINAL P5-RC2. Aucun deploiement VPS dans les jalons intermediaires.
