# CLARTE360 PIP RIASEC / O*NET - Jalon H3.1

## Objet
Correctif simplifie construit exclusivement a partir de H3 pour garantir l'idempotence de la reprise JSON PUBLIC sur les nouvelles sauvegardes H3.1 et suivantes.

## Decision de perimetre
Aucune migration complexe des anciens JSON H1/H2 n'est implementee. Les bases d'essai seront videes avant la recette reelle.

## Correctif applique
- `public_study_id` est maintenant inclus dans le JSON de sauvegarde via `build_snapshot()`.
- `public_study_id` est restaure via `restore_snapshot()`.
- Le meme JSON H3.1 recharge plusieurs fois conserve donc le meme `study_id`.
- `save_public_study_record()` reutilise ce meme identifiant et reecrit le meme fichier `<study_id>.json` au lieu de creer plusieurs etudes.
- Le `study_id` reste absent des payloads CRM et demeure independant de l'identite et du CRM.

## Elements inchanges
- Banque 72 items : inchangee.
- Scoring RIASEC : inchange.
- Code Holland : inchange.
- O*NET : inchange.
- ROME : inchange.
- Rapports PUBLIC/ACCOMPAGNEMENT : inchanges.
- Parcours ACCOMPAGNEMENT : inchange.
- Correctifs H2 et H3 : conserves.

## Fichiers modifies depuis H3
1. `clarte360_pip/framework/persistence.py`
2. `clarte360_pip/version.py`
3. `tests/test_jalon_h31_public_resume_idempotence.py` (nouveau)
4. `tests/test_jalon_h_final_acceptance.py`
5. `tests/test_l1d_consolidation.py`
6. `tests/test_structure_and_security.py`
7. `CHANGELOG.md`

## Resultat
193 tests passes, 0 echec.

## Deploiement
Aucun deploiement VPS n'a ete effectue.
