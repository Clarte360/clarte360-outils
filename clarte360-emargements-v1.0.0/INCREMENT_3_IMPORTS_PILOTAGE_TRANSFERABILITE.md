# V2 — Incrément intermédiaire n°3 — Imports + pilotage + transférabilité

Date : 3 septembre 2026

## Positionnement
Ce ZIP repart strictement du jalon I2 Qualité (29/29 tests) redéposé par le donneur d'ordre. Il reste un jalon technique : aucune installation VPS ni recette humaine n'est demandée.

## Réalisé
- moteur d'import unifié Clarté360 / ADCA avec clés NO_CLAR / NO_ADCA ;
- règle métier explicite de source : INTRA -> STAGIAIRE ; INTER et INDIVIDUEL -> CONV ADM, avec repli contrôlé uniquement lorsque les données nominatives attendues manquent ;
- écran d'import ADCA séparé, avec prévisualisation et préparation des actions historiques ;
- possibilité métier de créer une action historique ADCA puis de conserver uniquement le module qualité à froid, sans émargement artificiel ;
- pilotage qualité global : campagnes prévues, taux de réponse, difficultés ouvertes et actions d'amélioration ouvertes ;
- statistiques stables par codes de rubrique/question, indépendantes du libellé affiché ;
- filtres de pilotage par organisme et type de prestation ;
- gestion manuelle structurée des difficultés, aléas, incidents et réclamations ;
- suivi de statut et responsable ;
- création d'actions d'amélioration reliées à une fiche, avec responsable et échéance ;
- clôture tracée des fiches et des actions d'amélioration ;
- version applicative portée à 2.0.0-dev-I3-pilotage ;
- validation sur les véritables classeurs ADCA et Clarté360 disponibles dans le projet, en plus des tests synthétiques.

## Limites volontairement réservées à la candidate V2
- finition visuelle et ergonomique de recette ;
- chasse finale aux derniers libellés de marque codés en dur dans les écrans historiques et certains PDF ;
- recette SMTP réelle et smartphone sur VPS ;
- checklist métier complète et procédure de migration finale ;
- tests de bout en bout sur une copie de la base VPS réelle.
