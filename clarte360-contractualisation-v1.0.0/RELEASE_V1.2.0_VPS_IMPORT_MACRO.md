# Release V1.2.0-VPS-IMPORT-MACRO

## Changement d'architecture

- La base `.xlsm` chargée dans l'application est **strictement en lecture seule**.
- L'application ne génère plus et ne propose plus de base `.xlsm` modifiée.
- La base sert à :
  - retrouver une action existante par `NO_CLAR` ;
  - attribuer le prochain `NO_CLAR` précréé et encore libre ;
  - relire les informations existantes de `CONV ADM` et, si disponibles, de `FINANCEMENTS`.
- Plusieurs contrats peuvent être préparés pendant une même session.
- En fin de session, l'application produit :
  - `CLARTE360_IMPORT_SESSION_*.xlsx` avec les onglets `CONV ADM`, `FINANCEMENTS`, `META` ;
  - une sauvegarde JSON de la session ;
  - un ZIP regroupant import + JSON + PDF/JSON contractuels.
- L'injection dans la vraie base `.xlsm` sera réalisée localement par une macro Excel dédiée, par correspondance de noms de colonnes, afin de préserver macros, tableaux et formules.

## Règles BC particulier validées

- `SPEC_BPF = Autres`.
- Le montant total HT de l'action va uniquement dans `INTRA_HT`.
- `FACTURE_A_ETABLIR_A` reprend tous les financeurs avec leur montant TTC.
- Les financeurs détaillés sont également exportés vers `FINANCEMENTS` avec la clé `NO_CLAR`.
- Pour un particulier bipartite, les champs de contact de mise en place sont explicitement marqués à vider lors de l'import macro.
- Le calendrier saisi est repris tel quel dans `CALENDRIER`.
- Les dates sont exportées comme vraies dates Excel avec format `jj/mm/aaaa`.
