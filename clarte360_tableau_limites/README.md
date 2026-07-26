# Clarté360 – Tableau des limites

Application Streamlit conforme au socle Clarté360 pour identifier et traiter plusieurs limites limitantes d'un bénéficiaire.

## Fonctions
- identification et code d'accès par email ;
- consentement RGPD tracé ;
- création, modification et suppression de plusieurs limites ;
- tableau : limite, cause, conséquences, actions, date de réalisation ;
- sauvegarde/reprise par JSON ;
- rapport PDF ;
- historique des sessions et temps cumulé ;
- timeout d'inactivité ;
- envoi du JSON final à Clarté360.

## Lancement
```bash
pip install -r requirements.txt
streamlit run app.py
```
