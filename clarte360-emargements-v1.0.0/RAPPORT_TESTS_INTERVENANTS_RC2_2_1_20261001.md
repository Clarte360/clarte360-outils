# RAPPORT DE TESTS — INTERVENANTS RC2-2-1 — 01/10/2026

Version : `3.0.0-INTERVENANTS-RC2-2-1`

## Compilation
Commande exécutée dans l'environnement d'analyse :
`PYTHONPATH=. python -m compileall -q .`

Résultat : **OK**.

## Tests ciblés fusion PIP / IPIP / registre / prescriptions
Commande :
`PYTHONPATH=. pytest -q tests/test_j2c_rc7_tools_simple.py tests/test_ipip_rc1_connector.py tests/test_rc2_2_1_consolidation.py tests/test_j2c_rc5_outils_pip.py tests/test_j2c_rc6_tools_pip110.py tests/test_v3_i9d_hub_tools.py`

Résultat : **34 passed**.

Contrôles couverts notamment :
- présence IPIP dans le registre ;
- URL/version/launch_type IPIP ;
- contrat HMAC IPIP et absence d'identité civile dans le token ;
- scopes IPIP exacts ;
- TERMINE IPIP sans rapport refusé ;
- PIP : `expires_at` historique ignoré par le lancement spécialisé ;
- PIP et IPIP : `TERMINE` bloque le même lancement ;
- nouvelle prescription autorisée après une prescription `TERMINE` ;
- outil arbitraire ne peut pas devenir `EXTERNAL_SIGNED` ;
- présence simultanée app/services/worker du connecteur IPIP ;
- garde-fou espace bénéficiaire multi-outils.

## Campagne complète
Collecte : **475 tests**.

Commande exécutée :
`PYTHONPATH=. pytest -q`

Résultat final : **475 passed in 53.64s**, 0 échec.

Total : **475/475 verts**.

## Test manuel UI
Le test manuel navigateur réel (bénéficiaire avec PIP + IPIP + autres outils) ne peut pas être exécuté dans l'environnement de construction actuel, qui ne fournit ni runtime Streamlit utilisable ni navigateur authentifié vers le VPS. Il reste donc **obligatoire avant de déclarer la recette déployée/acceptée**.

La checklist exacte est fournie dans `CHECKLIST_RECETTE_INTERVENANTS_RC2_2_1_20261001.md`.

## Test VPS obligatoire avant recette fonctionnelle
Après PUSH utilisateur puis PULL volontaire sur le VPS, exécuter depuis le dossier stable :
1. `PYTHONPATH=. ./.venv/bin/pytest -q`
2. `PYTHONPATH=. ./.venv/bin/python -m compileall -q .`
3. redémarrage `clarte360-emargements.service` et `clarte360-emargements-worker.service`
4. contrôle `is-active` des deux services
5. contrôle HTTP local sur `127.0.0.1:8501`
6. recette manuelle multi-outils.
