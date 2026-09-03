# RAPPORT TESTS — CLARTÉ360 ÉMARGEMENTS V1.1.1

Date : 03/09/2026

## Vérifications automatisées

- Compilation Python : OK (`app.py`, `db.py`, `services.py`, `pdf_utils.py`, `worker.py`).
- Pytest : **13 tests réussis / 13**.

## Scénarios couverts

- création action / participant / créneau ;
- absence et rattrapage collectif ;
- verrouillage d'un créneau contenant une preuve ;
- report conservant le créneau d'origine ;
- réinitialisation du code personnel ;
- certificat conditionné aux preuves et contresignatures ;
- rattrapage d'une absence ;
- impossibilité de déclarer ABSENT une personne déjà signée ;
- priorité d'une signature valide sur un ancien marqueur d'absence ;
- suppression définitive participant avec suppression des preuves liées ;
- suppression définitive créneau avec suppression des preuves liées ;
- suppression définitive action avec suppression des enfants ;
- création / affectation d'un formateur référencé et génération de son accès restreint.

## Points à vérifier en recette réelle VPS

- SMTP OVH réel (envoi code, demande de signature, relance) ;
- rendu responsive smartphone ;
- parcours administrateur → intervenant → bénéficiaire ;
- contresignature puis clôture et certificat final ;
- suppression réelle d'un dossier de test ;
- migration additive sur la base de production existante ;
- affichage Europe/Paris ;
- sauvegarde système et restauration.
