# Journal des modifications - Clarté360 Moteurs professionnels

## Version 1.5.0-standard-clarte360 - Correctif session et notification

### Anomalies détectées
- La génération du code d'accès envoyait le mail au bénéficiaire, mais ne notifiait pas `contact@clarte360.com` lors d'une première ouverture de session.
- La durée limite par défaut était restée à 90 minutes alors que le socle appliqué dans l'application Boussole des valeurs professionnelles est de 15 minutes.
- Le contrôle de durée dépendait principalement d'une interaction utilisateur ou d'un rerun Streamlit ; sans activité, l'écran pouvait ne pas se verrouiller immédiatement.

### Corrections apportées
- Ajout d'une notification administrateur à `contact@clarte360.com` à chaque génération de code, initiale ou régénérée, avec prénom, nom, email, consultant, code, date/heure, version application et rappel RGPD.
- Passage de la limite de session par défaut à 15 minutes.
- Ajout d'un watchdog Streamlit automatique via `st.fragment(run_every="10s")` afin de déclencher le contrôle de durée même sans clic utilisateur, sur le même principe fonctionnel attendu que l'application Boussole.
- Enregistrement dans l'historique JSON du résultat de l'envoi bénéficiaire et de la notification administrateur.

### Points à surveiller
- La notification email dépend toujours des Secrets Streamlit SMTP : `smtp_server`, `smtp_port`, `smtp_user`, `smtp_password`, `from_email`, `to_email`.
- Sur les anciennes versions de Streamlit ne disposant pas de `st.fragment`, le contrôle reste fonctionnel au prochain rerun utilisateur ; Streamlit Cloud récent est recommandé.
