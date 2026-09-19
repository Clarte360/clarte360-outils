# Clarté360 — Gestion des Actions — CRM0 RC2

Version : `3.0.0-I9-J2C-PIP-LIAISON-I-CRM0-RC2`

## Base
RC2 est construite à partir de CRM0-RC1 validée, complétée avec le `app.py` corrigé actuellement présent sur la branche `main`.

## Périmètre
- suppression sécurisée d’une fiche CRM ;
- préservation stricte des actions, bénéficiaires et études PIP/O*NET ;
- fiche contact réellement modifiable ;
- interface CRM plus compacte ;
- notes ajoutables et supprimables ;
- tâches ajoutables, modifiables, passables à FAIT et supprimables ;
- liaisons actions ajoutables et retirables sans supprimer l’action ;
- création d’une action depuis la fiche corrigée (navigation Streamlit différée) ;
- recherche client CRM depuis Nouvelle action conservée ;
- correctifs RC1 PIP PUBLIC conservés.

## Hors périmètre
Aucune modification du moteur PIP/O*NET, des études pseudonymisées, des bénéficiaires, de l’émargement, Teams, qualité, contractualisation ou facturation.
