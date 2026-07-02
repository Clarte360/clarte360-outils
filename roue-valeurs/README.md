# Clarté360 - Roue des valeurs V2.2

## Corrections V2.2

- Ajout d'un accès bénéficiaire par code obligatoire.
- Envoi du code d'accès au bénéficiaire par email via SMTP Streamlit Secrets.
- Notification automatique au consultant Clarté360 lors de la génération d'un code.
- Ajout de l'adresse email et du consultant dans les données bénéficiaire.
- Information explicite du bénéficiaire sur l'utilisation du JSON dans le cadre de l'accompagnement.
- Ajout d'un bouton de transmission du JSON final au consultant Clarté360.
- Conservation des exports JSON / CSV / PNG / PDF existants.

## Streamlit Secrets

A configurer dans l'app Streamlit au format TOML :

```toml
[email]
smtp_server = "ssl0.ovh.net"
smtp_port = 465
smtp_user = "contact@clarte360.com"
smtp_password = "MOT_DE_PASSE"
from_email = "contact@clarte360.com"
to_email = "contact@clarte360.com"
```

## Déploiement

Remplacer le contenu du dépôt GitHub de l'application par les fichiers de cette version.

Commit conseillé :

`V2.2 - Ajout code d'accès et transmission JSON consultant`
