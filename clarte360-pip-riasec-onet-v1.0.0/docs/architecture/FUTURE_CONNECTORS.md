# Points d'extension reserves

## Gestion des actions V3

L1-A definit seulement la frontiere `GestionActionsPort`. Le futur connecteur devra verifier un jeton de lancement signe, rattacher beneficiary/action/prescription, publier les etats/evenements et rester la seule voie d'acces au mode ACCOMPAGNEMENT en production.

## O*NET

`OnetPort` depend d'une configuration `OnetSettings` lue depuis `[ONET]`. Aucun appel API ni contenu O*NET n'est implemente en L1-A.

## ROME

`RomePort` reserve la frontiere de recherche par profil RIASEC equivalent. Aucune recommandation, classement ou score de compatibilite n'est implemente.
