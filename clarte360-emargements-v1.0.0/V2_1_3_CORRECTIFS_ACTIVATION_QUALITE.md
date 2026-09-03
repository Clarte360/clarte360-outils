# Clarte360 Emargements - V2.1.3

Correctif prioritaire issu de la recette du 03/09/2026.

## Corrections

- Activation d'une action accessible directement depuis le calendrier lorsque celui-ci est coherent.
- Activation egalement accessible depuis l'onglet Envois & relances, en plus des Parametres action.
- L'activation passe l'action en ACTIVE, prepare les echeances, prepare les campagnes qualite activees et envoie le planning aux participants lorsque l'emargement est utilise.
- Une action ACTIVE reste modifiable.
- Le calendrier doit etre coherent avec la duree contractuelle avant activation lorsqu'un emargement est utilise.
- La date de reference qualite est desormais la fin reelle de la derniere seance planifiee, et non la date administrative de fin de l'action.
- Les seances se terminant apres minuit sont gerees correctement.
- Evaluation a chaud et retour intervenant : echeance a la fin reelle de la derniere seance.
- Evaluation a froid Formation : J+90 a partir de la fin reelle du calendrier.
- Evaluation a froid Bilan de competences : M+6 a partir de la fin reelle du calendrier.
- Toute modification du calendrier recalcule les campagnes qualite encore PENDING.
- Les campagnes deja SENT ou COMPLETED ne sont jamais deplacees silencieusement.
- Suppression des affichages parasites Streamlit DeltaGenerator apres ajout/envoi d'un participant.
- Les anciens messages conditionnels Streamlit susceptibles d'afficher des objets internes ont ete remplaces par des blocs explicites.

## Tests

47 tests automatises reussis sur 47.
