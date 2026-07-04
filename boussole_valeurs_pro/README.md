# Clarté360 - Boussole des valeurs professionnelles V1.2

Application Streamlit Clarté360 dédiée à la construction d'une roue des valeurs orientée bilan de compétences.

## V1.2 - Standard d'entrée Clarté360

- Premier écran de reprise : import d'une sauvegarde JSON ou nouvelle session.
- Reprise directe si le JSON contient déjà un code généré/validé.
- Onglet RGPD et consentement obligatoire à la première connexion.
- Le mail de code rappelle le consentement, l'absence de stockage serveur Clarté360 et l'usage exclusif dans l'accompagnement.
- Le JSON trace : consentement, génération/régénération de code, sessions, durées, pages consultées, import JSON, informations techniques disponibles dont IP si Streamlit la fournit.
- Session bénéficiaire limitée à 15 minutes avec écran de sauvegarde JSON.
- Module Valeurs Énergie conservé avec code consultant : CLAENER360.

## Principe pédagogique

L'application ne recherche pas les valeurs à la place de l'accompagnateur. Elle sert à valider et coter les valeurs déjà repérées en entretien, à partir de deux points d'appui :

1. Vie professionnelle.
2. Engagements personnels / vie hors travail.

Le seul livrable attendu est la roue des valeurs, et éventuellement la roue des valeurs énergie si le consultant active ce module.

## Installation locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Secrets Streamlit

Prévoir la section `[email]` dans les Secrets Streamlit pour l'envoi du code et la transmission éventuelle du JSON au consultant.
