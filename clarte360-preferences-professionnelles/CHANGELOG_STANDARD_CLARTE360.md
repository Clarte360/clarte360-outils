# Journal des modifications - Clarté360 Compétences & Projets v1.3.0

## Harmonisation socle Clarté360
- Ajout de l'écran d'accueil standard : importer un JSON ou commencer une nouvelle session.
- Ajout du consentement RGPD versionné avant accès à l'outil.
- Ajout des pages institutionnelles : Protection des données, Mentions légales, Nous contacter.
- Ajout du bouton permanent Contacter Clarté360.
- Ajout des identifiants racine de passation et session.
- Ajout de l'historique des accès, des sessions et des sauvegardes dans le JSON.
- Ajout du calcul de temps de session et du temps cumulé.
- Ajout du timeout automatique avec watchdog Streamlit autorefresh.
- Ajout de l'alerte navigateur avant fermeture via beforeunload.
- Renommage des boutons JSON selon le standard Clarté360.
- Amélioration du rapport PDF : logo centré, précaution de lecture, pied de page institutionnel.
- Mise à jour des dépendances Streamlit Cloud.

## Logique métier
- Aucun changement volontaire des calculs, questions, scores, ROME, RIASEC, faisabilité, décision ou plan d'action.


## v1.3.1 - Contrôle timeout

- Correction du contrôle d’inactivité : l’autorefresh technique ne réinitialise plus le compteur d’activité utilisateur.
- Ajout d’un heartbeat technique séparé de l’activité réelle.
- Ajout d’une détection de changement des données utilisateur pour réinitialiser le compteur uniquement en cas d’action réelle.
- Conservation du timeout automatique à 15 minutes avec fermeture de session `timeout_inactivite` et téléchargement JSON.
