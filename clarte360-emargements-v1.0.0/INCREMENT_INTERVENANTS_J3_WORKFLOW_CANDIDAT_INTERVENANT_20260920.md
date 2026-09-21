# CLARTE360 - Increment J3 - Workflow Candidat -> Intervenant
Date : 20/09/2026
Base : J2.1 NDA / Qualiopi

## Objet
Mettre en place le workflow humain de candidature sans modifier les fonctions operationnelles historiques de Gestion des Actions.

## Realise
- Etats de travail : NOUVEAU, INCOMPLET, EN_ETUDE, COMPLEMENT_DEMANDE, ENTRETIEN_A_PREVOIR, PRET_DECISION.
- Decisions humaines : VALIDER, REFUSER, ABANDONNER.
- Completeness visible et controlee avant PRET_DECISION / validation : identite, e-mail, type de collaboration, CV.
- Demandes de complements historisees, ouvertes puis resolues.
- Historique dedie du workflow et alimentation de professional_person_status_history / audit.
- Validation : le meme professional_person_id passe de CANDIDAT a INTERVENANT ; aucun doublon de personne.
- Creation du lien operationnel trainers uniquement lors de la validation humaine.
- Detection d'un e-mail deja utilise par un intervenant : blocage et rapprochement manuel requis, aucune fusion silencieuse.
- Refus/abandon : dossier conserve comme CANDIDAT non operationnel avec etat REFUSE/ABANDONNE.
- Onglet Candidature ajoute au dossier professionnel 360.

## Garde-fous
- Aucun candidat n'est affectable avant validation.
- PRET_DECISION interdit si le socle de completude n'est pas satisfait.
- VALIDE/REFUSE/ABANDONNE ne peuvent pas etre poses par un simple changement d'etat : passage obligatoire par la decision dediee.
- Aucun raccordement aux listes d'affectation Formation/Actions a ce jalon.
- IA non introduite a ce jalon.

## Correctif opportuniste J2
Correction de l'appel de validation d'e-mail dans update_professional_profile, revelee par les nouveaux tests J3.
