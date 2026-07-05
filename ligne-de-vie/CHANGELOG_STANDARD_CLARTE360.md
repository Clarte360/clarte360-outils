# CHANGELOG - Standard Clarté360

## v3.3.0 - alignement socle Clarté360 v1.8.2

- Ajout d'un écran de reprise JSON dès l'accès initial.
- Ajout des pages institutionnelles : RGPD, mentions légales, contact Clarté360.
- Ajout des boutons permanents de barre latérale : informations légales, contact, préparation JSON, sortie JSON, réinitialisation.
- Ajout d'une alerte navigateur `beforeunload` pour fermeture, rafraîchissement, changement d'URL ou retour navigateur.
- Ajout des identifiants racine/session et enrichissement de la structure JSON.
- Ajout du consentement RGPD daté dans le JSON.
- Ajout du consultant/accompagnateur dans le JSON.
- Harmonisation du pied de page PDF avec les coordonnées légales Clarté360, centré sur toutes les pages.
- Conservation de la logique métier Ligne de vie : événements, courbe, remontées, exports PDF/PNG/CSV/JSON.

## Points à valider après déploiement

- Test SMTP réel avec les secrets Streamlit de production.
- Contrôle de l'alerte navigateur dans Chrome/Edge/Safari/Firefox.
- Parcours bénéficiaire complet avec génération du PDF et reprise JSON.
