# CHANGELOG

## 1.1.3 - 03/09/2026
- Refonte complete du PDF APS selon le standard graphique Clarte360 : logo officiel, page de cadrage, en-tete sur les pages de contenu, pied de page institutionnel et pagination.
- Ajout de la partie 0 « Comprendre votre bilan de competences » dans l'application et dans le PDF.
- Presentation claire des trois phases reglementaires du bilan de competences.
- Presentation de la duree Clarte360 habituellement comprise entre 13 et 20 heures, avec distinction entre temps synchrones, temps individuel guide Clarte360 comptabilise et travail personnel complementaire non comptabilise.
- Rappel de la duree legale maximale de 24 heures et du suivi a six mois hors volume initial.
- Ajout d'un consentement explicite sur la comprehension de la duree et de l'organisation du parcours.
- Separation graphique renforcee des sections et suppression des mentions legales placees dans le corps du document : elles sont desormais structurees en pied de page.
- Validation visuelle du PDF sur un rendu A4 de test.

# Changelog

## 1.1.3 — 03/09/2026
- Correction du crash `StreamlitWidgetAlreadyInstantiatedError` sur les boutons Continuer : navigation différée `_next_nav` avant instanciation du widget.
- Rétablissement du parcours Framework Clarté360 : identification → information RGPD complète → consentement explicite → génération/envoi du code → validation du code → APS.
- Traçabilité RGPD : date, heure, version application, version texte, identifiant technique de session.
- Même contrôle RGPD lors d'une reprise JSON.
- Conservation de la configuration e-mail officielle `[email]`.

# CHANGELOG

## 1.1.0 – 2026-09-03

- Repositionnement complet en application 100 % beneficiaire.
- Suppression de l'acces consultant / administrateur et de la liste des dossiers.
- Introduction APS post-entretien.
- Mention explicite : formulaire non contractuel ; prix deja evoque ; contrat/convention distinct(e).
- Authentification par code personnel a 6 chiffres envoye par e-mail.
- Sauvegarde et reprise JSON selon la logique du Framework Clarte360.
- Refonte du cadre contractuel en simple collecte d'informations utiles a la future convention.
- Consentements directement formules a la premiere personne.
- Verification finale de completude.
- Generation du PDF APS complet.
- Envoi obligatoire PDF + JSON a contact@clarte360.com apres validation finale.
- Confirmation de transmission au beneficiaire.

## 1.1.1 - 03/09/2026
- Correction de la configuration e-mail pour respecter le Framework Clarte360.
- Suppression de la section `[smtp]` introduite par erreur.
- Lecture exclusive de la section `[email]` avec les cles officielles : `smtp_server`, `smtp_port`, `smtp_user`, `smtp_password`, `from_email`, `to_email`.
- Connexion SSL automatique sur le port 465, STARTTLS sur les autres ports.
- Le destinataire du PDF + JSON final est maintenant `[email].to_email`.
- Notification technique du code d'acces a `[email].to_email`, en plus de l'envoi au beneficiaire, selon le comportement des autres applications Clarte360.
