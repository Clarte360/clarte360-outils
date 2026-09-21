# CLARTÉ360 — Intervenants J3.1 — Création administrative directe d'un intervenant

Date : 20/09/2026
Socle : J3 — Workflow Candidat -> Intervenant

## Objet
Ajouter une seconde porte d'entrée administrative vers le même Dossier professionnel 360° : création directe d'un INTERVENANT lorsqu'une décision humaine d'intégration est déjà prise, sans parcours artificiel de candidature.

## Réalisation
- ajout du service `create_professional_intervenant` ;
- création simultanée et cohérente de la personne professionnelle et de son lien opérationnel `trainers` ;
- `principal_status=INTERVENANT`, `candidate_work_status=VALIDE`, actif ;
- origine explicite `ADMIN_DIRECT_INTERVENANT` ;
- historique de statut et audit dédiés ;
- aucune ligne dans `candidate_workflow_events` ni `candidate_decisions` pour une création directe ;
- garde anti-doublon sur l'e-mail contre dossiers professionnels et intervenants existants ;
- interface : deux portes d'entrée visibles, « Créer un candidat manuellement » et « Ajouter directement un intervenant » ;
- message explicite : l'adéquation compétences / prestations devra être réalisée ensuite ;
- l'onglet Candidature indique qu'aucun parcours artificiel n'a été créé pour les intervenants saisis directement.

## Invariant métier
Quel que soit le mode d'entrée, une seule personne professionnelle et un seul `professional_person_id` existent. L'adéquation compétences ↔ prestations est obligatoire pour tout intervenant et sera traitée au jalon J4, avec saisie humaine directe possible ; l'IA restera facultative et assistante.
