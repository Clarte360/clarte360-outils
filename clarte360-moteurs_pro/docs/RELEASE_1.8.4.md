# Clarté360 Moteurs professionnels — V1.8.4

Date : 21/09/2026

## Objet
Correctif de continuité de session entre les anciennes passations Streamlit Cloud et la version VPS.

## Correctif principal
L'écran de reprise appelait le référentiel `active` sans le recevoir dans sa fonction, provoquant l'erreur `name 'active' is not defined` avant même la validation du JSON. `import_json_screen` reçoit désormais explicitement `active` depuis `main`.

## Règle fonctionnelle conservée
Un JSON valide provenant d'une passation antérieure compatible constitue la preuve de continuité : la restauration positionne l'accès comme déjà validé et ne redemande pas un nouveau code.

## Non modifié
- questionnaire et 60 curseurs ;
- fichier Excel source ;
- calculs et scoring ;
- définitions enrichies du rapport V1.8.3 ;
- contrat Hub et garde-fou de sauvegarde.

## VPS
- URL : https://moteurs-professionnels.clarte360.com
- service : clarte360-moteurs-professionnels.service
- port : 8506
- dossier : /opt/clarte360/clarte360-outils/clarte360-moteurs_pro

## Validation
33 tests automatisés réussis + compilation Python + validation d'un JSON historique complet V1.8.0.
