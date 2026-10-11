# CLARTE360 - P5-RC2 J3 - PILOTAGE QUALITE - 10/10/2026

BASE FIABLE: ZIP J2 (df6ba635e60d39a0f7acfe98cbd671ffa43c243e405b14d72739507eeadb0343).
GO autorise J3 : COR-004, COR-010, AME-010. Aucun acces GitHub/VPS ni migration de production.

## Calculs
- SCORE 1-5 : valider des entiers 1-5 et N/A ; ni NPS 0-10 ni texte/numerique hors echelle ne participent a une moyenne /5.
- NPS : calcule a part en pourcentage de promoteurs moins detracteurs, et jamais exprime sur 5.
- Calculs par rubrique ponderes par le nombre de notes valides ; filtrage organisme, prestation, action, HOT/COLD.
- L'espace intervenant restitue uniquement les notes HOT/COLD des beneficiaires avec moyenne ponderee ; exclusion du retour intervenant.

## Pilotage administratif
- Qualite generale + Qualite dans l'action : trois vues (« A traiter », « Enquetes et indicateurs », « Historique »).
- Campagnes HOT/COLD + TRAINER/CLIENT/PRESCRIBER/OPCO : suivi des invitations, statut de reponse, echeances, envoi initial reel, relances en attente ou envoyees et PDF.
- Notes faibles <=3/5 : traitement court motive (prise en compte, precision, classement, CAPA) : evenement unique, trace chronologique et reference vers la question.
- Remarques R12/I06 : traitement court sur l'evenement canonique J2, projection du statut sur anciennes sources.
- Les fiches historiques sans action restent accessibles en Qualite generale sans recherche de filiation automatique.

## Limites explicites
- AUCUN nouveau canal de notification : J4.
- Aucun parcours navigateur multi-roles ou migration de donnees VPS : J10/J11.
- Les anciennes sources non reliees ne sont pas fusionnees.
- Registre COR/AME officiel edition 0.9 : NE PAS MODIFIER.
- GitHub : exclusivite du proprietaire lors de l'unique ZIP final P5-RC2 ; VPS uniquement sur GO distinct.

## Non-regression
Suite complete : 727 passed. Tests J3 : 27 nouveaux. Les 700 tests J2 demeurent.
