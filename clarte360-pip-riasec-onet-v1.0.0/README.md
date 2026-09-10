# Clarté360 — PIP RIASEC + O*NET Interest Profiler

**Version : 1.0.2-l1-vps**  
**Incrément : L1-D — LIVRABLE 1 FINAL**  
**Framework : Clarté360 V4.0 + FRAMEWORK VPS CLARTÉ360 V1.0**

## Objet
Première version testable de la vraie application PIP RIASEC Clarté360. Le moteur PIP est commun aux futurs modes public et bénéficiaire accompagné. Le PIP est un questionnaire français original, complet et autonome, fondé sur le modèle RIASEC de Holland et mesurant principalement l'attraction / l'intérêt.

## Contenu du Livrable 1
- socle Clarté360 : navigation, session, RGPD, timeout, contact, configuration, persistance ;
- architecture modulaire et points d'extension O*NET, ROME et Gestion des actions ;
- pipeline tableur maître -> ressource runtime versionnée ;
- banque pilote de 120 items avec validations automatiques ;
- moteur de passation par blocs avec dimensions mélangées et échelle fermée 1–5 ;
- aucune dimension, facette, interprétation ou score intermédiaire visible ;
- scoring déterministe des six dimensions, indices 0–100 et préparation prudente du code Holland ;
- sauvegarde/reprise `clarte360.pip.run.v1` ;
- parcours PIP seul / PIP puis O*NET 60 avec verrou anti-influence ;
- structure du ressenti fermé préparée pour son moment métier ;
- tests automatisés et recette utilisateur L1.

## Hors périmètre volontaire L1
La passation O*NET réelle/API, la restitution/rapport professionnel final, l'exploration ROME finale et l'intégration signée Gestion des actions appartiennent aux lots suivants. Aucun O*NET seul n'est proposé.

## Lancer en développement
```bash
python -m pip install -r requirements.txt
streamlit run app.py
```
Le mode public est le point d'entrée par défaut. Pour le smoke-test technique du futur mode accompagné : `?mode=accompagnement&beneficiary_id=B1&action_id=A1&prescription_id=P1`.

## Tests
```bash
PYTHONPATH=. python -m pytest -q
```

## Recette utilisateur
Voir `docs/RECETTE_UTILISATEUR_LIVRABLE_1.md`.

## Secrets
Aucune clé réelle ne doit être présente dans le dépôt. Sur le VPS : `/opt/clarte360/secrets/secrets.toml`. L'application prévoit `st.secrets["ONET"]["ONET_API_KEY"]` et `st.secrets["ONET"]["ONET_API_BASE_URL"]`; l'absence de secret en développement/test est gérée proprement.

## Repères VPS
- SSH : `ssh ubuntu@51.255.160.207`
- Applications : `/opt/clarte360/clarte360-outils/`
- Dossier stable PIP : `/opt/clarte360/clarte360-outils/clarte360-pip-riasec-onet-v1.0.0/`
- Secrets centraux : `/opt/clarte360/secrets/secrets.toml`
- Ressources versionnées : `resources/`
- Données persistantes hors Git : `data/`
- Environnement Python local : `.venv/`

Procédure détaillée : `docs/deployment/VPS_DEPLOYMENT.md`.
