# Clarté360 - Boussole des valeurs professionnelles

Application Streamlit propriétaire Clarté360.

Version : v1.6-socle-clarte360  
Socle : Clarté360 1.7, standardisé sur Moteurs Professionnels v1.7.0 référence.

## Fonctionnalités socle
- Accueil standard avec choix JSON / nouvelle session.
- Reprise JSON avec création d'une nouvelle session.
- Identification bénéficiaire et code d'accès par e-mail.
- RGPD obligatoire.
- Mentions légales Clarté360.
- Formulaire Contacter Clarté360.
- Sauvegarde JSON.
- Boutons de sortie et de reprise JSON.
- Protection avant fermeture navigateur.
- Timeout 15 minutes avec motif `timeout_inactivite`.

## Déploiement
Installer les dépendances :

```bash
pip install -r requirements.txt
streamlit run app.py
```

Configurer les secrets SMTP dans `.streamlit/secrets.toml` ou variables d'environnement.
