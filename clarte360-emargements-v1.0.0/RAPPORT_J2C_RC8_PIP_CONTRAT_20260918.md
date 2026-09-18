# RC8 — Contrat PIP ACCOMPAGNEMENT

Correctif construit à partir de RC7 OUTILS SIMPLES.

- Aucun renommage des secrets : Gestion des Actions conserve `pip_connector.launch_signing_key`.
- Le jeton PIP n'envoie plus les anciens droits `PIP_RIASEC` / `ONET60`.
- Droits envoyés : `PIP_RUN`, `PIP_RESUME`, `PIP_STATUS`, `PIP_RESULT_READ`.
- Le mode public du PIP n'est pas modifié.
- Les simplifications RC7 sur le catalogue/outils sont conservées.
