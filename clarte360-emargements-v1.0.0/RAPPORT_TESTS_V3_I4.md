# RAPPORT DE TESTS — CLARTÉ360 V3.0.0-I4
## Incrément I4 — Portails séparés + gestion du planning

Date : 05 septembre 2026  
Base : V3.0.0-I3 cumulative I1 + I2 + I3.

## Résultat automatisé

`102 passed`

**102 tests réussis sur 102.**

## Compilation Python

Compilation réussie de :
- `app.py`
- `worker.py`
- `services.py`
- `db.py`
- `pdf_utils.py`

## Tests I4 ajoutés

- droits planning action et créneau explicitement séparés ;
- intervenant ponctuel limité à son créneau ;
- co-animation protégée contre une modification par un intervenant sans droit action ;
- recalcul de l'échéance INITIAL d'émargement après déplacement ;
- journal `planning_change_events` après propagation ;
- blocage d'un changement de volume horaire par intervenant ;
- blocage hors bornes de l'action ;
- blocage des chevauchements ;
- blocage de la modification d'une séance déjà terminée ;
- ajout de séance refusé s'il dépasse le volume contractuel ;
- ICS avec UID stable et annulation d'une occurrence reportée ;
- absence de liens Intervenant/Bénéficiaire sur l'écran Administration.

## Non-régression

Tous les tests I1, I2, I3 et V2.2 restent réussis, notamment :
- migration additive ;
- multi-intervenants ;
- reports/rattrapages ;
- contresignature future impossible ;
- co-animation et preuves immuables ;
- un seul envoi automatique d'émargement INITIAL ;
- bénéficiaires, documents, qualité et transmissions existants.

## Hors périmètre volontaire

- refonte qualité / relances globales : I5 ;
- import générique / multi-organisme : I6 ;
- création et synchronisation Microsoft Teams / Graph : I7.
