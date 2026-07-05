# Clarté360 - Roue des domaines de vie - mise à niveau socle

Version livrée : 1.4.1-socle-clarte360
Socle Clarté360 : 3.0

## Audit synthétique

A. Conforme
- Logique métier conservée : roue actuelle, débriefing, roue idéale sans contrainte, comparaison et actions.
- Exports JSON/PDF déjà présents.
- SMTP déjà protégé par gestion d'erreur.

B. Mis à jour
- Ajout écran d'accueil standard : importer JSON ou commencer une nouvelle session.
- Ajout consentement RGPD obligatoire avant code d'accès.
- Structuration JSON enrichie : version application, version socle, passation root id, session id, RGPD, historique code, sessions, sauvegardes.
- Barre latérale harmonisée : préparer JSON, quitter et télécharger JSON, contact, RGPD/mentions légales.
- Pages institutionnelles avec retour exact à l'application : RGPD, mentions légales, contact.
- Formulaire contact Clarté360 avec consentement spécifique et informations techniques/session.
- Protection navigateur beforeunload pour fermeture, rafraîchissement, changement d'URL, retour navigateur.
- Timeout bénéficiaire à 15 minutes avec JSON de sauvegarde.
- Rapport PDF enrichi avec logo centré en première page et pied de page institutionnel sur toutes les pages.

C. Points sensibles
- Les tests SMTP réels et l'alerte navigateur doivent être validés dans l'environnement Streamlit déployé, car ils dépendent du navigateur et des Secrets.
- Le timeout utilise streamlit-autorefresh ; dépendance ajoutée à requirements.txt.

D. Compatibilité
- Compatible Streamlit Cloud avec secrets.example.toml.
- Prépare la migration VPS par structuration JSON et traçabilité sessions.


## Correctif 1.4.1
- Correction du pied de page PDF : découpe institutionnelle en deux lignes, suppression du risque de texte tronqué sur les côtés, pagination conservée sur chaque page.
