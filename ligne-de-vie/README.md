# Clarté360 - Ligne de vie V3.2

Application Streamlit pour construire une ligne de vie dans un cadre bilan de compétences / accompagnement Clarté360.

## V3.2 - code d'accès et transmission consultant

- Ajout d'un code d'accès obligatoire au démarrage.
- Fonctionnement aligné sur les outils Préférences et Moteurs : saisie prénom, nom, email puis réception du code par email.
- Notification automatique à Clarté360 lors de la demande de code.
- Information explicite du bénéficiaire sur la transmission possible du JSON au consultant.
- Ajout de l'email dans le JSON.
- Bouton de transmission du JSON final au consultant Clarté360.
- Conservation des exports existants : JSON, CSV, PDF et PNG.

## Secrets Streamlit attendus

```toml
[email]
smtp_server = "ssl0.ovh.net"
smtp_port = 465
smtp_user = "contact@clarte360.com"
smtp_password = "VOTRE_MOT_DE_PASSE"
from_email = "contact@clarte360.com"
to_email = "contact@clarte360.com"
```

## Fonctionnalités conservées

- Points de la ligne de vie reliés automatiquement.
- Placement intelligent des noms courts.
- Saisie des événements avec jour/mois/année, avec jour `00` accepté si le jour exact est inconnu.
- Classement automatique des événements.
- Zone de projection optionnelle à 5 ou 10 ans.
- Exploration facultative des remontées avec trace écrite optionnelle.
- Les remontées enregistrées apparaissent dans le PDF.

## Lancement local

```bash
pip install -r requirements.txt
streamlit run app.py
```
