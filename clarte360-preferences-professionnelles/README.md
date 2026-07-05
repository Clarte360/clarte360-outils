# Clarté360 — Préférences professionnelles

Version : 1.10.1-socle-clarte360  
Socle Clarté360 : 1.8

Application Streamlit propriétaire Clarté360 destinée à l'exploration des préférences professionnelles dans le cadre du bilan de compétences, du coaching professionnel et de l'accompagnement des transitions.

## Contenu

- `app.py` : application Streamlit complète.
- `data/questions_preferences_professionnelles_v1.xlsx` : questionnaire source.
- `data/questions_preferences_professionnelles_v1.json` : données questionnaire.
- `assets/site_icon.png` : logo / icône Clarté360.
- `.streamlit/secrets.example.toml` : modèle de configuration SMTP.
- `requirements.txt` : dépendances Streamlit Cloud.

## Points harmonisés avec le socle Clarté360

- écran d'accueil avec import JSON ou nouvelle session ;
- consentement RGPD obligatoire ;
- code d'accès par e-mail ;
- notification administrateur non bloquante ;
- barre latérale conforme à la logique socle : navigation métier, session, JSON, contact, RGPD, versions ;
- suppression de l'affichage du temps de session dans la barre latérale ;
- suppression de la réinitialisation dans le cœur de l'application ;
- sauvegarde JSON de reprise ;
- sortie JSON avec fermeture propre de session ;
- traçabilité RGPD / sessions / sauvegardes ;
- protection navigateur `beforeunload` ;
- watchdog timeout via `streamlit-autorefresh` ;
- rapport PDF institutionnel avec logo et coordonnées Clarté360.

## Logique métier conservée

Aucune modification n'a été apportée aux 60 questions, aux 10 dimensions, aux réponses, aux scores, aux calculs, aux graphiques métier ou à la philosophie pédagogique de l'outil.

## Tests restant à valider après déploiement

- envoi SMTP réel avec les secrets Streamlit ;
- réception du code bénéficiaire ;
- notification administrateur ;
- formulaire contact ;
- test réel d'attente de 15 minutes pour confirmer l'écran de timeout sans clic utilisateur ;
- alerte navigateur avant fermeture selon navigateur utilisé.
