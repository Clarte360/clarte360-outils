# Clarte360 - Moteurs professionnels v1.7.0 Reference

Application Streamlit Clarte360 destinee a l'exploration des moteurs professionnels.

## Version
- Application : 1.7.0-reference-clarte360
- Socle Clarte360 : 1.0

## Installation locale
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Test prioritaire
1. Demarrer une session.
2. Repondre a quelques questions.
3. Ne plus toucher a l'application pendant plus de 15 minutes.
4. L'application doit afficher l'ecran de timeout et proposer le telechargement du JSON.
5. Le JSON doit contenir `motif_fermeture: timeout_inactivite`.

## Notes techniques
Le timeout utilise en priorite `streamlit-autorefresh` pour forcer un rerun regulier sur Streamlit Cloud.
Les battements automatiques ne sont pas consideres comme une activite utilisateur.
