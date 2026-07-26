# Audit de pré-déploiement — RVC360 V0.3.1

## Verdict

Version techniquement prête à être déposée sur GitHub et déployée sur Streamlit Community Cloud, sous réserve de renseigner les Secrets Streamlit obligatoires.

## Contrôles réalisés

- structure complète du dépôt ;
- compilation Python sans erreur ;
- référentiel Excel chargé : 240 valeurs, aucun doublon ;
- absence de clé API ou mot de passe réel dans les fichiers ;
- exclusion des secrets par `.gitignore` ;
- appel OpenAI via Responses API ;
- sortie structurée par schéma JSON strict ;
- `store=False` ;
- filtrage local du référentiel avant appel IA ;
- filtrage des valeurs hors liste autorisée ;
- contrôle lexical anti-interprétation ;
- timeout réseau et tentatives limitées ;
- plafond de sortie IA ;
- comptage des appels et tokens dans l'export JSON ;
- compatibilité des chemins avec Streamlit Cloud.

## Secrets obligatoires pour le déploiement

```toml
[openai]
api_key = "VOTRE_CLE_API"
model = "gpt-5-mini"

[security]
session_limit_minutes = 15

[smtp]
host = "..."
port = 587
user = "..."
password = "..."
sender = "..."
```

Le `local_master_code` ne doit être utilisé qu'en test local avec `CLARTE360_LOCAL=1`.

## Limite connue

La reprise à partir d'un fichier JSON n'est pas encore implémentée dans l'interface, même si l'export JSON est disponible. Le message d'expiration a donc été laissé comme indication de conservation manuelle, mais la réimportation devra faire l'objet d'une version ultérieure.
