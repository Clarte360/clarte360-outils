# Clarté360 - Moteurs professionnels

Application Streamlit propriétaire Clarté360 destinée à explorer les moteurs professionnels déclarés d'un bénéficiaire.

## Version

`1.6.2-standard-clarte360`

Cette version est une référence candidate pour le socle commun Clarté360 :

- RGPD et mentions légales intégrés ;
- formulaire de contact Clarté360 ;
- notification par e-mail ;
- gestion du JSON bénéficiaire ;
- historique des sessions ;
- comptabilisation du temps actif ;
- sortie officielle par téléchargement JSON ;
- alerte navigateur avant fermeture sans sauvegarde ;
- pied de page institutionnel dans les PDF ;
- compatibilité Streamlit Cloud et préparation VPS.

## Déploiement

1. Déposer le contenu du ZIP dans GitHub.
2. Vérifier `requirements.txt`.
3. Définir les secrets Streamlit SMTP.
4. Lancer l'application sur Streamlit Cloud.

## Secrets attendus

Voir `.streamlit/secrets.example.toml`.

## Tests obligatoires avant validation

- Nouvelle session et réception du code bénéficiaire.
- Notification administrateur à `contact@clarte360.com`.
- Validation du code et démarrage réel de session.
- Sauvegarde JSON manuelle.
- Sortie par bouton JSON.
- Reprise depuis JSON.
- Timeout automatique à 15 minutes.
- Formulaire de contact.
- Génération PDF avec pied de page Clarté360.

## Socle Clarté360 1.0

Cette version introduit le socle commun Clarté360 : gestion des sessions, JSON, RGPD, mentions légales, formulaire d'assistance permanent, pied de page PDF, préparation Streamlit Cloud et migration VPS future.
