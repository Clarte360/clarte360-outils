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
