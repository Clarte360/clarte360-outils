# CLARTE360 PIP RIASEC/O*NET - Jalon H3

Date : 2026-09-19  
Base obligatoire : `CLARTE360_PIP_RIASEC_ONET_JALON_H2_20260919.zip`

## Objet
Correctif ciblé de recette réelle PUBLIC et compatibilité avec les protections de Gestion des Actions, sans modification de Gestion des Actions.

## Audit H2 - constats confirmés

1. Les événements CRM PUBLIC étaient écrits dans l'outbox active `data/connector_outbox/gestion_actions/events.jsonl` via `_outbox_root() = PERSISTENT_DATA_DIR / "connector_outbox" / "gestion_actions"`.
2. `_public_contact_payload()` exportait encore `participant_id`, ce qui créait une clé de jonction interdite et entraînait le rejet par Gestion des Actions.
3. `CALLBACK_REQUESTED` réinjectait lui aussi `participant_id` dans son payload.
4. Le dataset étude H2 était déjà pseudonymisé par un `study_id` aléatoire indépendant, mais son `schema` était `clarte360.pip.public-study.v2`, incompatible avec le lecteur réel de Gestion des Actions qui attend `clarte360.pip.public-study.v1`.
5. H2 contenait déjà la prévisualisation du rapport avant le ressenti. Cette correction est conservée telle quelle.

## Correctifs H3

### H3-A - séparation CRM PUBLIC / étude
- Suppression de `participant_id` de `_public_contact_payload()`.
- Suppression de `participant_id` de `CALLBACK_REQUESTED`.
- Ajout d'un garde-fou central dans `GestionActionsPort.publish_event()` pour les types PUBLIC CRM :
  - `CONTACT_EMAIL_VERIFIED`
  - `CONTACT_UPDATED`
  - `CALLBACK_REQUESTED`
- Le garde-fou refuse les clés interdites même si elles sont imbriquées : `beneficiary_id`, `action_id`, `participant_id`, `prescription_id`, `study_id`, `study_pseudonym`, `pseudonym`, `passation_id`, `scores`, `score`, `holland_code`, `pip_answers`, `onet_answers`, `answers`, `responses`, `report`, `report_ref`.
- Le fonctionnement interne du `public_participant_id` n'est pas supprimé : seule son exportation CRM est interdite.
- L'idempotence de l'outbox reste basée sur le contenu canonique de l'événement.

### H3-B - dataset étude compatible Gestion des Actions
- `schema` fixé exactement à `clarte360.pip.public-study.v1`.
- `study_id` conservé : aléatoire, non vide, indépendant de toute identité/CRM/passation.
- Ajout explicite de `pip_scoring_version` lorsqu'il est disponible.
- Conservation des données méthodologiques utiles : banque, réponses PIP, scoring, O*NET, ressenti, timing O*NET, parcours, consentement étude.
- Ajout d'un garde-fou récursif interdisant les clés identifiantes/de jonction dans le dataset étude.
- `save_public_study_record()` ne crée aucun fichier si `study_consent` est faux.

### H3-C - ressenti après restitution
- Correction H2 conservée sans modification fonctionnelle : grande prévisualisation PDF avant le questionnaire, ouverture page 3, bouton « J’ai consulté ma synthèse — donner mon ressenti ».

## Outbox retenue
Chemin unique actif côté PIP :
`data/connector_outbox/gestion_actions/events.jsonl`

Les enveloppes individuelles restent sous :
`data/connector_outbox/gestion_actions/pending/` puis `delivered/`.

Aucun troisième emplacement n'a été créé.

## Éléments non modifiés
- banque 72 items `PIP-BANK-0.5` ;
- scoring `PIP-SCORE-0.5` ;
- code Holland ;
- référentiel d'interprétation `PIP-INT-1.0` ;
- O*NET ;
- ROME ;
- rapport PUBLIC 5 pages `PIP-RPT-1.6` ;
- fonctionnalités ACCOMPAGNEMENT ;
- prévisualisation/ressenti H2.

## Fichiers runtime modifiés
- `clarte360_pip/framework/public_access.py`
- `clarte360_pip/ui/pages.py`
- `clarte360_pip/connectors/gestion_actions.py`
- `clarte360_pip/version.py`

## Tests modifiés/ajoutés
- `tests/test_jalon_g_outbound_contracts.py` : adaptation au contrat réel corrigé ;
- `tests/test_jalon_h3_public_separation.py` : nouveaux tests H3 ;
- `tests/test_jalon_h_final_acceptance.py` : métadonnées de jalon H3 ;
- `tests/test_l1d_consolidation.py` : métadonnées de build H3 ;
- `tests/test_structure_and_security.py` : métadonnées de build H3.

## Résultat
- Suite complète : 190 tests réussis, 0 échec.
- Sources PIP : OK.
- Tableur maître / runtime : synchronisés.
- Référentiel interprétation / runtime : synchronisés.
- ROME : 1911 fiches, synchronisé.
- Compilation Python : OK.

Aucun déploiement VPS n'a été effectué.

## Liste exacte des fichiers différents de H2
- `CHANGELOG.md`
- `RAPPORT_JALON_H3_20260919.md` (nouveau)
- `RAPPORT_TESTS_JALON_H3_20260919.md` (nouveau)
- `clarte360_pip/connectors/gestion_actions.py`
- `clarte360_pip/framework/public_access.py`
- `clarte360_pip/ui/pages.py`
- `clarte360_pip/version.py`
- `tests/test_jalon_g_outbound_contracts.py`
- `tests/test_jalon_h3_public_separation.py` (nouveau)
- `tests/test_jalon_h_final_acceptance.py`
- `tests/test_l1d_consolidation.py`
- `tests/test_structure_and_security.py`

## Procédure de déploiement H2 -> H3
1. Ne pas déployer automatiquement : faire d'abord le contrôle local de la livraison H3.
2. Remplacer le contenu du dépôt local GitHub par H3 puis Commit + Push via GitHub Desktop.
3. Sur le VPS, sauvegarder les données PIP persistantes avant toute mise à jour.
4. Vérifier `git status`, `git fetch`, le commit H3 puis `git pull --ff-only origin main`.
5. Exécuter la suite complète de tests dans `.venv` ; cible : 190/190.
6. Vérifier les chemins persistants : `data/public/study` et `data/connector_outbox/gestion_actions/events.jsonl`.
7. Redémarrer le service PIP uniquement après tests verts.
8. Rejouer une passation PUBLIC réelle de bout en bout et contrôler CRM + demande de rappel + dataset étude + écran Études PIP/O*NET.
