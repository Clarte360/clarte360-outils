# Clarte360 - Roue des domaines de vie

Application Streamlit d'exploration accompagnee : construction de la roue actuelle, debriefing, construction de la roue ideale sans contrainte, comparaison et actions imaginables.

## Lancement local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Secrets Streamlit / SMTP OVH

Ajouter dans les Secrets Streamlit :

```toml
[email]
smtp_server = "ssl0.ovh.net"
smtp_port = "465"
smtp_user = "votre_adresse@domaine.com"
smtp_password = "votre_mot_de_passe"
from_email = "votre_adresse@domaine.com"
to_email = "contact@clarte360.com"
```

Le code d'acces est envoye au beneficiaire par email. Un message automatique est envoye a l'adresse `to_email` pour informer Clarte360 de l'utilisation du programme, avec les coordonnees saisies et le code genere. Le code est valable 30 minutes.
