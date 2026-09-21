# Clarté360 - Moteurs professionnels

Application Streamlit propriétaire Clarté360 d'exploration des sources d'énergie professionnelle.

Version livrée : **v1.8.0-socle-clarte360**  
Socle Clarté360 : **1.8**

Cette version conserve intégralement la logique métier de Moteurs professionnels v1.7.0 et met à jour uniquement le socle commun : barre latérale, RGPD / traçabilité, retour application, sécurité du bouton de réinitialisation et charte PDF.

## Déploiement Streamlit Cloud

Fichier principal : `app.py`

Dépendances : voir `requirements.txt`.

## Secrets SMTP

Configurer les secrets Streamlit selon `.streamlit/secrets.example.toml`.


### Garde-fou de sortie — v1.8.2
La version VPS-ready protège le travail bénéficiaire contre un rafraîchissement, une fermeture d'onglet ou une navigation tant que l'état métier a évolué depuis le dernier JSON téléchargé. Après téléchargement, la protection est levée uniquement pour cet état précis et se réactive dès une nouvelle modification.
