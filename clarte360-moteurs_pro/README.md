# Clarté360 – Moteurs professionnels

Application Streamlit bénéficiaire utilisant des curseurs à 11 positions entre deux propositions positives.

## Fonctionnement
- Identification obligatoire : prénom, nom, email.
- Code d'accès obligatoire envoyé au bénéficiaire par email.
- Notification envoyée à contact@clarte360.com au démarrage.
- 60 curseurs affichés dans un ordre aléatoire.
- Sauvegarde intermédiaire JSON téléchargeable.
- Reprise possible depuis le JSON intermédiaire.
- JSON final envoyé automatiquement à Clarté360 à la fin.
- Rapport PDF et JSON téléchargeables par le bénéficiaire.
- Lecture vocale de la situation + proposition gauche + proposition droite.

## Secrets Streamlit
Dans Streamlit Cloud > Settings > Secrets, coller :

```toml
[email]
smtp_server = "ssl0.ovh.net"
smtp_port = 465
smtp_user = "contact@clarte360.com"
smtp_password = "TON_MOT_DE_PASSE_ROUNDCUBE"
from_email = "contact@clarte360.com"
to_email = "contact@clarte360.com"

[security]
code_expiration_minutes = 15
```

## Modifier le questionnaire
Modifier uniquement `data/moteurs_professionnels_curseurs_v0_1.xlsx`, puis commit/push sur GitHub.
