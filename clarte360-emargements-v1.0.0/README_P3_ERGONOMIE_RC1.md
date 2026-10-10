# Gestion des Actions — P3 ERGONOMIE RC1

Candidate complete fondee sur l'archive P2 `3.0.0-P2-DOCUMENTS-RC1`.
Navigation de la maquette approuvee : menu vertical retractable Streamlit, choix explicite de l'action puis rubrique contextuelle.
Les droits restent controles dans les services metier; ce menu ne confere jamais de permission.
L'espace Client/DRH de la maquette reste a developper au P4.

## Repartition

- Beneficiaire : accueil multi-actions, profil, parcours, planning/ICS, Teams, outils, documents, cours/travaux, questionnaires, emargements, transmissions, archives.
- Intervenant : selecteur d'intervention, vue d'ensemble, planning, Teams, emargements/QR, codes, documents, outils, qualite, transmissions.
- Administrateur : pages generales inchangees avec libelles, selection d'action, douze rubriques contextuelles et dossier de referencement d'intervenant en navigation verticale.
- Aucun lien client ne doit ouvrir des donnees individuelles au P3.

## Tests

Tests de navigation hors production, couverture des modules, suite PyTest complete, validation syntaxique et verification du ZIP extrait.
Aucune recette authentifiee M365/Graph, SMTP live, sauvegarde/restauration ou migration SQLite n'est revendiquee.

## Livraison

ZIP code seul. Ne contient aucune base, document reel, signature ou secret. NE PAS ecraser `data/` sur VPS. GitHub et VPS sous controle exclusif du proprietaire.
