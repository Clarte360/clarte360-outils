# Boussole Valeurs Pro v1.8.2 - Socle Clarte360 v3.0

# Clarté360 - Boussole des valeurs professionnelles

Application Streamlit propriétaire Clarté360.

Version : v1.8.2-socle-clarte360  
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

## V1.8.3 — Validation / VPS / Hub ready
Cette version prépare la Boussole au VPS Clarté360 et au lancement signé depuis Gestion des Actions I9-H1, sans modifier ses règles métier. URL cible prévue : `https://boussole-valeurs.clarte360.com`. Voir `docs/`.


## Garde-fou anti-perte de travail — v1.8.4
Le bénéficiaire est averti s’il tente d’actualiser, fermer ou quitter l’application avec des modifications non sauvegardées. Le téléchargement du JSON correspondant à l’état courant lève l’alerte ; toute modification ultérieure la réactive automatiquement. Les traces techniques et changements de page seuls ne rendent pas le travail artificiellement « non sauvegardé ».
