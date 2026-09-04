# Clarte360 Emargements - V2.2 Lot 3 - Fin d'action + qualite

## Base
Construit exclusivement a partir du ZIP V2.2 Lot 2 fourni. Le dossier de deploiement reste `clarte360-emargements-v1.0.0`.

## Fonctions ajoutees
- planification automatique du dossier final quelques heures apres cloture ; worker capable de generer les dossiers arrives a echeance ;
- ZIP collectif nomme `AAMMJJ NO_ACTION DOCS STAGIAIRES.zip`, avec sous-dossier par stagiaire ;
- dossier stagiaire : feuille individuelle, certificat definitif, evaluation a chaud PDF si completee, documents rattaches a l'action ;
- contacts client structures et import Excel : responsable qualite, email qualite, contact mise en place, email et telephone ;
- parametrage de transmission du dossier final : activation, responsable qualite, contact mise en place, autre personne ;
- file/journal technique `client_transmissions` pour les transmissions client ;
- evaluation a froid conservee comme campagne independante du premier dossier ;
- PDF qualite existant conserve et integre aux documents de fin ;
- pilotage qualite direction enrichi : taux de reponse, NPS, rubriques agregees, difficultes et ameliorations ;
- fonctions de fin de vie du portail : detection apres 12 mois et purge du portail sans suppression des archives internes ;
- migrations additives uniquement.

## Non-regression
La suite complete passe a 69 tests automatises reussis.

## Point de recette finale
Les envois SMTP reels des dossiers finaux et PDF COLD devront etre valides sur le VPS avec la configuration email reelle. La structure de destinataires, la file de transmission et la journalisation sont presentes dans ce lot.
