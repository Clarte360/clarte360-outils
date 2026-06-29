# Clarté360 - Ligne de vie V3.0

Application Streamlit pour construire une ligne de vie dans un cadre coaching / bilan de compétences.

## V3.0

- Points de la ligne de vie reliés automatiquement.
- Placement intelligent des noms courts pour limiter les chevauchements.
- Les textes des points à +9/+10 sont placés sous le point pour éviter la coupure dans le PDF.
- Les textes des points à -9/-10 sont placés au-dessus du point.
- Marges graphiques élargies pour améliorer le rendu écran et PDF.
- Saisie des événements avec jour/mois/année : le jour `00` est accepté si le jour exact est inconnu.
- Mois et année obligatoires pour permettre le classement chronologique.
- Classement automatique des événements.
- Zone de projection optionnelle à 5 ou 10 ans.
- Exploration facultative des remontées avec trace écrite optionnelle.
- Les remontées enregistrées apparaissent maintenant dans le PDF.
- Export JSON, CSV, PDF et PNG.
- Logique RGPD : aucune sauvegarde serveur.

## Lancement local

```bash
pip install -r requirements.txt
streamlit run app.py
```
