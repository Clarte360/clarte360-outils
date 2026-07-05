# Changelog Clarté360 — Boucle auto-validante

## v2.0.3-socle-clarte360
- Correction définitive de la page RGPD : ajout du texte RGPD manquant, suppression du NameError, traçabilité visible.
- Harmonisation de la page Contact avec le socle visuel : logo, en-tête, retour application, formulaire en colonnes et consentement spécifique.
- Remplacement du bouton « Modifier l'adresse e-mail » par « Je n'ai pas reçu mon code / Renvoyer un code ».
- Renvoi du code sans quitter l'écran d'accès bénéficiaire.

# Changelog Clarté360 — Boucle auto-validante

## v2.0.2-socle-clarte360
- Correction de la navigation : le bouton **Contacter Clarté360** ouvre désormais la page Contact et non la page RGPD.
- Alignement de la page RGPD / Mentions légales / Contact sur le comportement de l'application de référence **Roue des domaines de vie**.
- Correction du parcours code d'accès : la demande et la validation restent dans le même écran d'accès bénéficiaire.
- Alignement SMTP sur les Secrets Streamlit validés du socle : section `[email]` avec `smtp_server`, `smtp_port`, `smtp_user`, `smtp_password`, `from_email`, `to_email`.
- Suppression de l'affichage du code de test lorsque le SMTP n'est pas configuré : l'application signale l'erreur au lieu de contourner l'envoi réel.

## v2.0.1-socle-clarte360
- Alignement visuel de l'écran d'accueil sur Roue des domaines de vie.
- Favicon/logo Clarté360.

## v2.0.0-socle-clarte360
- Transformation en application bénéficiaire.
- Suppression du fonctionnement accompagnateur et des codes utilisateurs historiques.
