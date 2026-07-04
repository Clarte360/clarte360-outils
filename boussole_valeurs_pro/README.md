# Clarté360 - Boussole des valeurs professionnelles

Application Streamlit dérivée de la Roue des valeurs Clarté360, adaptée au bilan de compétences.

## Finalité

L'outil ne recherche pas les valeurs à la place de l'accompagnateur et ne réalise aucune interprétation automatique.
Il sert de support d'entretien pour construire la roue des valeurs du bénéficiaire à partir de valeurs déjà repérées pendant l'accompagnement.

## Adaptation bilan de compétences

La validation de chaque valeur se fait sur deux points d'appui :

1. Travail / expérience professionnelle
2. Engagements personnels / vie hors travail

Pour chaque valeur, le bénéficiaire renseigne des exemples concrets, datés ou situés dans le temps. La cotation reste liée à la qualité des exemples : sans exemple concret, la cote reste faible.

## Valeurs énergies

L'espace Valeurs énergies est conservé comme module optionnel, accessible uniquement par code consultant.
Code par défaut : `CLAENER360`

## Installation locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Secrets Streamlit pour l'envoi email

Créer `.streamlit/secrets.toml` avec :

```toml
[email]
smtp_server = "smtp.example.com"
smtp_port = "587"
smtp_user = "user@example.com"
smtp_password = "mot_de_passe"
from_email = "contact@clarte360.com"
to_email = "contact@clarte360.com"
```

## Fichiers importants

- `app.py` : application principale
- `requirements.txt` : dépendances
- `assets/logo_clarte360.png` : logo
- `.streamlit/config.toml` : configuration Streamlit
