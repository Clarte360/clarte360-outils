# RAPPORT DE TESTS — V3 I9-C

Date : 12/09/2026
Source : I9-B

## Résultat
- `PYTHONPATH=. pytest -q`
- **146 passed**
- Compilation : `python -m py_compile app.py db.py services.py worker.py graph_client.py mailer.py excel_import.py security.py pdf_utils.py persistent_session.py ui_guard.py`
- **COMPILE_OK**

## Nouveaux tests I9-C
- champs permanents d'identité Microsoft additifs ;
- aucune création Guest silencieuse ;
- création uniquement après demande explicite ;
- double recherche Entra avant invitation ;
- identité existante empêchant la création d'un doublon ;
- prochaine réunion calculée depuis les créneaux métier ;
- présence Teams sous un autre email laissée non attribuée ;
- rapprochement manuel explicite avec participant de la même action ;
- absence de Meeting ID / Entra ID dans les portails intervenant et bénéficiaire.

## Recette externe différée
La recette Microsoft réelle (tenant, certificat, permissions Graph, Application Access Policy, Guest, coorganizer, rapports de présence) sera réalisée à la recette finale conformément à la décision projet.
