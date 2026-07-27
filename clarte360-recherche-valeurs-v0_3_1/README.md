# Clarté360 – Recherche de mes valeurs

Version 1.0.0 préproduction.

Application Streamlit construite sur le socle Clarté360 de référence et dédiée uniquement à la recherche, à la clarification et à la validation des valeurs du bénéficiaire selon RVC360.

## Déploiement Streamlit

Fichier principal : `app.py`

Secrets requis :

```toml
[email]
smtp_server = "..."
smtp_port = 465
smtp_user = "..."
smtp_password = "..."
from_email = "..."
to_email = "..."

[security]
session_limit_minutes = 60

[openai]
api_key = "..."
model = "gpt-5.6-terra"
```

Le bloc `[email]` reprend exactement le format utilisé par les applications Clarté360 existantes. La clé OpenAI ne doit jamais être placée dans le dépôt GitHub.

## Version 1.1.0-preproduction
- Prerequis en saisie libre et valeurs personnelles.
- Tri des hypotheses avant questionnaire HEC.
- Questionnaire specifique successif obligatoire.
- Boucle de recherche depuis les resultats.
- Reponse vocale et lecture des questions.
- Rapport PDF enrichi et optimisation des appels IA.
- Correction du formulaire Contact.


## Version 1.2.0
- Hypothèses examinées une par une jusqu’à validation ou abandon.
- Nouvelle question après chaque cycle de valeur.
- Consentement explicite avant la fin de la recherche.
- Valeurs validées visibles dans un panneau latéral droit.
- Avatar Clarté360 allégé.
- Retour garanti depuis les pages auxiliaires.
- Rapport limité aux valeurs validées.
