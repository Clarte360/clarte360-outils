# I9-G — Contacts / Prospects + préparation Contractualisation

## Base de départ
I9-F validée. Aucun moteur métier existant n'est remplacé.

## CRM léger
- `crm_contacts` conserve prénom, nom, téléphone, e-mail, fonction/entreprise facultatives et centres d'intérêt.
- Consentement marketing distinct du consentement recherche, horodaté et révocable.
- Statuts : `NOUVEAU`, `A_CONTACTER`, `CONTACTE`, `CONVERTI`, `SANS_SUITE`.
- `crm_events` trace création, changements de statut, consentements et conversion.
- Conversion vers bénéficiaire : date de naissance obligatoire au moment de la conversion pour le contrôle de doublon ; un bénéficiaire exact existant est réutilisé au lieu d'être dupliqué.

## Contractualisation — frontière I9-G
Le moteur Contractualisation V1.2.0-VPS-IMPORT-MACRO reste autonome. I9-G ne recopie ni `contracts.py`, ni le moteur PDF, ni la logique XLSM/macro.

Le contrat d'échange préparé est `CLARTE360_CONTRACTUALISATION_CONTEXT_V1` :
- action_id et NO_CLAR (`action_no`) ;
- beneficiary_id public + participant_id ;
- prestation/type de contractualisation ;
- identité strictement nécessaire ;
- calendrier métier de l'action ;
- référence APS et payload APS versionnable ;
- retour persistant : statut, référence externe, PDF, JSON, financements, avertissements.

Statuts préparés : `A_PREPARER`, `EN_COURS`, `GENEREE`, `SIGNEE`, `ANNULEE`.

L'intégration réseau/SSO directe avec `https://contractualisation.clarte360.com` n'est volontairement pas inventée en I9-G : le code V1.2.0 inspecté n'expose pas encore de contrat de lancement signé équivalent au PIP. I9-G prépare donc les données, la persistance et la traçabilité sans contourner l'application existante.
