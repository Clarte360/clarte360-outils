# Clarté360 – APS – Entretien préliminaire v1.0.0

Application Streamlit destinée au premier entretien / phase préliminaire d’un bilan de compétences.

## Fonctions

- création et reprise d’un dossier bénéficiaire ;
- identité et coordonnées utiles à la contractualisation ;
- choix contrat individuel / convention / convention tripartite / financeur tiers ;
- données du donneur d’ordre et du signataire ;
- analyse de la situation, de la demande et du besoin ;
- co-définition des objectifs ;
- choix du format, du rythme et des outils envisagés ;
- traçabilité du volontariat, de la confidentialité, du RGPD et de l’accord de poursuite ;
- contrôle de complétude ;
- export JSON et PDF ;
- persistance SQLite compatible VPS.

## Lancement local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Sous Windows, l’activation du venv est `.venv\\Scripts\\activate`.

## Secrets

Copier `.streamlit/secrets.example.toml` vers `.streamlit/secrets.toml` uniquement en local.
En production Clarté360, utiliser le lien symbolique vers le fichier central de secrets VPS.

## Données

Par défaut : `data/clarte360_aps.db`.
Sur VPS, configurer `[database].path` vers un dossier persistant hors dépôt Git.
