# RAPPORT DE TESTS — CLARTÉ360 V3.0.0-I3
## Incrément I3 — Contresignatures + émargement V3

Date : 05 septembre 2026
Base : V3.0.0-I2 cumulative I1 + I2.

## Résultat automatisé

`95 passed`

95 tests réussis sur 95.

## Compilation Python

Compilation réussie de :
- `app.py`
- `worker.py`
- `services.py`
- `db.py`
- `pdf_utils.py`

## Tests I3 ajoutés

- refus serveur d'une contresignature de créneau futur ;
- refus tant qu'un participant reste EN_ATTENTE ;
- co-animation avec une preuve distincte et immuable par intervenant actif ;
- un seul email automatique INITIAL d'émargement ;
- neutralisation des anciens rappels PENDING RELANCE_1 / RELANCE_2 ;
- contresignature considérée comme preuve historique bloquant réécriture/report ;
- contrôle correct d'un créneau traversant minuit ;
- migration additive et idempotente des contresignatures V2 vers la structure V3.

## Points de non-régression conservés

- I1 migration additive ;
- I2 multi-intervenants et affectations par créneau ;
- absences, reports et rattrapages ;
- portail intervenant ;
- portail bénéficiaire ;
- qualité V2.2 existante ;
- documents et transmissions ;
- calculs timezone / créneaux nocturnes.

## Hors périmètre volontaire

- relances qualité manuelles/globales : I5 ;
- refonte des trois portes d'entrée et gestion du planning intervenant : I4 ;
- Microsoft Teams / Graph : I7.
