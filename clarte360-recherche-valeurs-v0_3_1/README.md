## Version actuelle

V2.1.3.8F-preproduction

# Clarté360 – Recherche de mes valeurs V2.1.2

Application Streamlit reconstruite depuis la V2.0 puis consolidée selon le Canvas V2.1 et les règles de navigation du Framework Clarté360.

## Évolutions centrales de cette version

- suppression de la numérotation visible des écrans ;
- navigation libre vers toutes les étapes déjà ouvertes ;
- recalcul et invalidation automatique des données dépendantes après modification ;
- reprise exacte de la page, des files de validation, de la navigation et des états métier depuis le JSON de travail ;
- composant unique pour toutes les questions ouvertes : écoute, clavier, voix, transcription, correction, validation et reformulation facultative ;
- nettoyage des hésitations, répétitions involontaires et reprises de phrase avant validation ;
- questionnaire bénéficiaire structuré en plusieurs questions courtes ;
- audit de cohérence bloquant avant clôture définitive.

## Installation

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Secrets requis

Copier `.streamlit/secrets.example.toml` vers `.streamlit/secrets.toml`, puis renseigner la clé et le modèle OpenAI, le modèle de transcription, le code de déblocage, les paramètres SMTP et la durée maximale de session.

Ne jamais publier le fichier réel `secrets.toml`.

## Contrôles locaux

```bash
python -m py_compile app.py
python -m pytest -q
```

Résultat de fabrication : **11 tests réussis**.

## Versions

- Application : 2.1.2
- Référentiel RVC360 : 2.1
- Framework déclaré : 4.0

## Stabilisation finale 8F
Cette livraison stabilise le module 3 et son panier de gestion des valeurs. Les hypothèses du futur module 4 ne constituent pas un quatrième panier : une hypothèse sélectionnée sera envoyée dans le parcours normal de validation d’une nouvelle valeur.
