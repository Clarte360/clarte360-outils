# Contrat PIP — données d’affichage ACCOMPAGNEMENT — Jalon C

Date : 18/09/2026

## Objet

Le PIP distingue désormais strictement les identifiants techniques utilisés pour la sécurité, la sauvegarde et les échanges serveur des données lisibles destinées à l’interface bénéficiaire.

## Champs techniques existants

- `beneficiary_id`
- `action_id`
- `participant_id` (optionnel selon contrat)
- `prescription_id`

Ces champs restent signés et utilisés côté serveur. Ils ne doivent jamais être affichés au bénéficiaire.

## Nouvelles données d’affichage signées côté PIP

Le jeton peut désormais porter :

- `beneficiary_first_name`
- `beneficiary_last_name`
- `action_number`
- `action_title`

Quand elles sont présentes, le PIP affiche :

- `Prénom NOM` / nom lisible du bénéficiaire ;
- `numéro d’action — intitulé de l’action`.

## Transition avec Gestion des Actions

Le Jalon C ne modifie pas Gestion des Actions.

Pour éviter une régression immédiate avec les jetons déjà émis, les quatre nouveaux champs d’affichage sont acceptés mais ne sont pas encore obligatoires côté PIP pendant la transition. Si un ancien jeton ne les contient pas, l’interface affiche des libellés neutres :

- `Bénéficiaire Clarté360`
- `Action Clarté360`

Elle n’affiche jamais les IDs techniques en remplacement.

Le chantier Gestion des Actions devra ensuite ajouter ces quatre champs au payload signé. Une fois les deux côtés déployés et validés, leur caractère obligatoire pourra être activé sans modifier la logique d’affichage du PIP.

## Séparation PUBLIC / ACCOMPAGNEMENT

- Le mode PUBLIC ne peut porter ni IDs de dossier ni données d’affichage de dossier Clarté360.
- Le mode ACCOMPAGNEMENT conserve sauvegarde serveur et contrat Gestion des Actions.
- La question « Souhaitez-vous approfondir certains éléments avec votre accompagnateur ? » est supprimée du PIP.
- Le ressenti est désormais neutre et identique sur les items méthodologiques ; le mode de passation est tracé dans l’enregistrement.
- Aucun mécanisme marketing ou commercial PUBLIC n’est introduit dans le parcours ACCOMPAGNEMENT.
