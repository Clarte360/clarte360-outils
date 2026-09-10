# Architecture L1-A

## Principe

Le projet reprend le Framework Clarte360 V4 et l'application Moteurs Professionnels V1.8 comme reference comportementale. Le Framework V4 demande une responsabilite unique par service et prepare explicitement une modularisation en modules Python. L1-A applique cette modularisation sans modifier les principes du socle.

## Couches

- `app.py` : point d'entree Streamlit unique et orchestration.
- `clarte360_pip/framework/` : services permanents Framework (configuration, branding, session, navigation, RGPD, persistance, timeout, SMTP, contact).
- `clarte360_pip/domain/` : objets métier PIP independants de Streamlit.
- `clarte360_pip/ui/` : points d'entree et ecrans.
- `clarte360_pip/connectors/` : ports explicites O*NET, ROME et Gestion des actions, volontairement non implementes en L1-A.
- `data/` : schemas et futures ressources runtime publiees depuis le tableur maître.
- `docs/sources/` : quatre sources de verite PIP conservees dans le livrable cumulatif.
- `tests/` : tests automatises.

## Modes

Le mode n'est pas un choix libre dans l'interface. Le point d'entree le determine. Le mode PUBLIC ne transporte aucun identifiant de dossier. Le mode ACCOMPAGNEMENT exige les identifiants structurants, en attendant le jeton signe du futur connecteur Gestion des actions.

## Secrets

Le code accepte l'absence de secrets en developpement/test. O*NET est configure exclusivement via la section `[ONET]`; aucune cle n'est stockee dans le depot. L'URL de base non secrete peut etre fournie par configuration.

## Hors L1-A

Aucune question PIP, aucun scoring, aucun code Holland, aucune restitution ROME, aucune passation O*NET et aucune integration active Gestion des actions ne sont developpes ici.
