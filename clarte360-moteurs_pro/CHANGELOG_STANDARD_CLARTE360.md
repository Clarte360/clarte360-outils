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
