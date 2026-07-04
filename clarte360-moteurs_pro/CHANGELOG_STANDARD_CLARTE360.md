# Journal des modifications - Clarté360 Moteurs professionnels

## v1.6.1-standard-clarte360 - 04/07/2026

Version de référence candidate pour le socle Clarté360.

### Harmonisations ajoutées
- Ajout d'une rubrique commune **RGPD et mentions légales**.
- Ajout des coordonnées officielles Clarté360 issues du papier à en-tête : adresse, téléphone, e-mail, site, RCS, SIRET, NAF, TVA.
- Ajout d'un formulaire **Contacter Clarté360** intégré à l'application.
- Envoi des demandes de contact à `contact@clarte360.com`.
- Ajout d'un consentement spécifique pour le traitement des demandes de support et le rappel téléphonique facultatif.
- Ajout d'informations techniques au message support : application, version, session, passation, durée de session, durée totale.
- Ajout d'un pied de page institutionnel Clarté360 sur les rapports PDF.
- Ajout du temps total cumulé lisible dans le JSON.
- Maintien du bouton officiel de sortie avec téléchargement JSON.
- Conservation de l'alerte navigateur avant fermeture sans JSON téléchargé.

### Corrections / robustesse
- Structuration plus claire des fonctions liées aux informations légales et au support.
- Préparation renforcée à la future migration VPS par centralisation des constantes institutionnelles.
- Les champs navigateur, OS et résolution sont prévus dans le JSON de support, mais indiqués comme non disponibles sous Streamlit sans composant dédié.

### Points à tester
- Envoi SMTP du formulaire de contact sur Streamlit Cloud avec les vrais secrets.
- Téléchargement du JSON à la sortie volontaire.
- Déconnexion automatique 15 minutes.
- Affichage du pied de page dans le PDF.
- Reprise depuis JSON et conservation de l'historique de session.

## v1.6.2-standard-clarte360 - 04/07/2026

Version candidate **Socle Clarté360 1.0**.

### Harmonisations ajoutées
- Ajout de la constante `SOCLE_CLARTE360_VERSION = "1.0"`.
- Ajout de la version du socle dans le JSON, le contexte technique et la barre latérale.
- Ajout d'un bouton permanent **💬 Contacter Clarté360** dans la barre latérale.
- Le formulaire d'assistance est désormais accessible pendant l'utilisation de l'application, sans passer par la rubrique RGPD.
- Conservation du même formulaire dans **Informations légales et RGPD**.
- Clarification du rôle du formulaire : questions administratives, problèmes techniques et suggestions, sans aide à l'interprétation des questions ou exercices.
- Ajout d'un identifiant support unique `SUP-...` dans chaque demande envoyée à Clarté360.
- Ajout de l'identifiant support dans l'objet du mail et dans le message de confirmation affiché à l'utilisateur.

### Points à tester
- Bouton permanent de contact depuis la barre latérale pendant une passation.
- Envoi SMTP réel de la demande d'assistance.
- Présence de l'identifiant support dans le mail reçu.
- Conservation du formulaire dans l'onglet Informations légales et RGPD.
- Absence de régression sur JSON, timeout 15 min, reprise JSON et PDF.

## v1.6.3-reference-clarte360
- Correction majeure du timeout : ajout d'un watchdog autonome par `streamlit-autorefresh`.
- Distinction entre heartbeat technique et activité utilisateur réelle.
- Fermeture automatique après 15 minutes sans activité utilisateur avec motif `timeout_inactivite`.
- Version proposée comme référence du Socle Clarté360 1.0 après test.
