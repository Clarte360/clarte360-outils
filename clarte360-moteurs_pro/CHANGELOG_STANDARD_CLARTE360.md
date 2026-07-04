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

## Version 1.6.0-standard-clarte360 - Socle temps et sortie JSON renforcé

### Anomalies détectées
- Le temps indiqué dans le JSON n'était pas suffisamment exploitable pour l'administrateur : il pouvait refléter une session technique, sans distinguer clairement l'heure réelle de validation du code et le temps actif conservé.
- La barre latérale affichait des informations de temps visibles au bénéficiaire, alors que le besoin est un suivi administrateur discret dans le JSON.
- La sauvegarde ou la sortie ne forçaient pas un rituel clair de conservation du JSON avant fermeture.

### Corrections apportées
- Ajout de `code_verified_at` au JSON : l'heure de saisie/validation du code devient le point de départ réel de l'utilisation.
- Renforcement de l'historique `sessions` avec `validation_code_at`, `duree_active_secondes`, `dernier_battement`, `sauvegardes`, `motif_fermeture` et `temps_total_cumule_minutes`.
- Remplacement du simple calcul début/fin par un suivi par battements Streamlit, plafonné pour éviter de compter des heures après fermeture brutale, veille ou suspension du navigateur.
- Suppression de l'affichage du temps dans la barre latérale.
- Ajout en barre latérale de deux actions : préparation d'un JSON de reprise et sortie via JSON.
- La sortie volontaire passe par `Quitter et préparer mon JSON`, puis téléchargement du JSON préparé.
- Ajout d'une alerte navigateur `beforeunload` lorsque le bénéficiaire tente de quitter sans téléchargement JSON. Cette alerte reste dépendante des limites imposées par les navigateurs.

### Points à surveiller
- Aucun navigateur ne permet de bloquer totalement la croix de fermeture d'un onglet ou d'une fenêtre ; l'alerte de fermeture est donc une protection complémentaire et non une garantie absolue.
- Le comportement doit être repris dans le futur socle commun Clarté360 afin d'être identique sur toutes les applications.
