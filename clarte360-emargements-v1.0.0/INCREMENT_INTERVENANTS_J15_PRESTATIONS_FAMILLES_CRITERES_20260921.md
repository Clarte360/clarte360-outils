# CLARTÉ360 — Intervenants J15
## Prestations, familles et critères de compétences
Date : 21/09/2026

## Objectif
Transformer le référentiel des prestations en véritable donnée métier administrable et construire dès maintenant les grilles de critères de compétences utilisables pour l’instruction humaine des qualifications.

## Réalisé
- Création d’un référentiel maître `service_families` versionné.
- 5 familles initiales : Bilan de compétences, Formations, Coaching, Conseil, Accompagnements.
- Migration additive : `service_catalog.family_id`, tout en conservant `family` comme projection lisible de compatibilité.
- Ajout, modification, activation/inactivation, ordre d’affichage et suppression/fusion des familles.
- Une suppression de famille utilisée exige une famille de destination ; les prestations sont réaffectées avant suppression.
- Réaffectation en masse de plusieurs prestations à une famille.
- Plus aucune famille libre dans l’interface de création/modification d’une prestation.
- Filtres Prestations : recherche, famille, actif/inactif.
- Construction d’un référentiel initial de 152 critères sur les 26 prestations V1.
- Chaque critère porte : catégorie, caractère obligatoire, niveau minimal, preuves acceptables, origine/référence, version et état actif.
- Origine du seed J15 : `ADAPTATION_CLARTE360`, avec référence explicite au CDC correctif V1.1 et à l’adaptation métier Clarté360. Cela ne constitue pas une validation scientifique ni une qualification automatique.
- Bilan de compétences : 8 critères initiaux spécifiques.
- Formations : 6 critères par prestation, combinant expertise du domaine, conception, animation, évaluation, posture et traçabilité. La structuration reprend notamment les besoins opérationnels observés dans le document fourni « Critères Compétences Formateurs TFP » sans le recopier comme norme générale.
- Coaching : 6 critères par prestation orientés cadre, écoute/questionnement, processus, autonomie, contexte et déontologie.
- Conseil : 5 critères par prestation.
- Accompagnements : 5 critères par prestation.
- Dans l’écran Qualification, les critères sont désormais présentés comme une grille à cocher et valider humainement, plutôt qu’une succession de niveaux à saisir critère par critère.

## Garde-fous
- Le seed des critères ne crée aucune qualification humaine.
- La présence d’un critère ne prouve pas sa maîtrise.
- L’IA ne valide aucun critère automatiquement dans J15.
- La pré-sélection IA des critères, les preuves proposées et leur validation humaine détaillée relèvent de J16.
- Les familles et critères sont administrables sans modification du code après initialisation.

## Compatibilité
Migration additive et rétrocompatible. Les colonnes et relations historiques `family`, services, qualifications, preuves et actions sont conservées.
