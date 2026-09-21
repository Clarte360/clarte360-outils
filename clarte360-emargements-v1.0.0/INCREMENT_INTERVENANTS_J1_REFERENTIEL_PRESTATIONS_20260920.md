# CLARTÉ360 — Gestion des Intervenants / Partenaires
## J1 — Référentiel des prestations Clarté360
Date : 20/09/2026
Socle : J0 — `clarte360-gestion-actions-v3.0.0-INTERVENANTS-J0-SOCLE-DONNEES.zip`

## Objet
Créer le référentiel métier administrable des prestations Clarté360 sans coder les prestations dans l'interface et sans créer de qualification intervenant à ce stade.

## Réalisé
- Table maître `service_catalog` avec code stable, nom, famille, description, portée individuel/collectif/mixte, types d'action, statut actif/inactif, source et version courante.
- Historique immuable `service_versions` à chaque création ou modification.
- Table `service_competency_criteria` avec les 5 catégories prévues par le CDC : métier/technique, pédagogique, accompagnement/coaching, comportemental, réglementaire.
- Pour chaque critère : obligatoire/souhaitable, pondération optionnelle, niveau minimal 0–4, preuves acceptables, durée de validité, actif/inactif et version.
- Historique `service_criterion_versions` pour chaque modification de critère.
- Initialisation idempotente des 13 prestations de départ prévues dans le CDC V1.2.
- Aucun critère de compétence n'est inventé au démarrage : les critères restent vides tant qu'ils ne sont pas explicitement définis et validés.
- API métier de lecture/création/modification/inactivation et consultation des versions.
- Interface d'administration intégrée dans `Paramètres > Intervenants & partenaires`, avec deux sous-onglets : `Intervenants` et `Prestations`.
- Tableau des prestations affiché directement à l'ouverture de l'onglet Prestations ; gestion des critères et historique sans refonte graphique globale.

## Règles respectées
- Catalogue indépendant du code métier : les nouvelles prestations sont persistées en base.
- Pas de suppression physique des prestations : l'inactivation est la voie normale.
- Aucune qualification d'une personne n'est créée ou déduite en J1.
- J1 ne raccorde pas encore le catalogue aux affectations de Gestion des Formations / Actions.
- Aucun appel IA en J1.

## Non-régression
La suite complète passe à 369/369 tests :
- 362 tests du RC2 ;
- 3 tests J0 ;
- 4 tests J1.

## GO / NO GO J1
GO technique : schéma, services, versionnage, interface d'administration et tests sont validés.
Le jalon suivant peut partir exclusivement de ce package J1.
