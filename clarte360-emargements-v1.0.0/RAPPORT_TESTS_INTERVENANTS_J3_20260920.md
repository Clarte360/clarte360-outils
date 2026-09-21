# Rapport de tests - Intervenants J3
Date : 20/09/2026

Commande : `PYTHONPATH=. pytest -q`

Resultat : **381 passed**.

- Base J2.1 : 376 tests.
- Nouveaux tests J3 : 5.
- Regression : 0.

Scenarios J3 couverts :
1. candidat non operationnel avant validation humaine ;
2. completude et garde PRET_DECISION ;
3. demande de complement historisee et resoluble ;
4. validation conservant le meme professional_person_id et creant le lien operationnel ;
5. refus sans creation d'intervenant operationnel.

Compilation `app.py`, `db.py`, `services.py` : OK.
