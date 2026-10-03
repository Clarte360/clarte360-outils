# Audit et correctif JSON — Roue des valeurs v2.8.2

Date : 2026-10-03

La v2.8.1 pouvait conserver un `exit_json_bytes` antérieur après « Préparer mon JSON », puis servir cette ancienne copie après de nouvelles modifications.

## Correctif
- plus de cache binaire JSON dans la sidebar ;
- recalcul depuis l'état courant à chaque rerun ;
- sérialisation unique `json_snapshot_bytes()` ;
- empreinte métier liée aux téléchargements page 4, page 6, sidebar et timeout ;
- un état modifié après rendu n'est pas déclaré sauvegardé ;
- schéma JSON métier inchangé et anciens JSON compatibles.

## Recette obligatoire
Préparer → modifier → télécharger → réimporter ; page 4 ; page 6 ; timeout ; import v2.8.1 puis modification et nouveau téléchargement.
