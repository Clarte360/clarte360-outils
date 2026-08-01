# Rapport de tests — Correctif normalisation V2.1.3.8E

## Objet
Empêcher le moteur de remplacer automatiquement une valeur exprimée par le bénéficiaire par une autre valeur jugée proche dans le référentiel.

## Cas critique corrigé
- Entrée : `Perfectionnisme`
- Ancien résultat incorrect : `Professionnalisme`
- Nouveau résultat attendu : `Perfectionnisme`

## Règle appliquée
La normalisation ne traite que la forme linguistique. Elle ne modifie jamais le sens du terme saisi. Une forme canonique du référentiel n'est adoptée qu'en cas d'équivalence stricte après retrait des articles, harmonisation de la casse, des accents et de la ponctuation.

## Contrôles exécutés
- compilation Python : réussie ;
- tests automatiques : 43 réussis sur 43 ;
- absence de rapprochement flou dans `_normalise_value_name` ;
- présence référentielle contrôlée par correspondance exacte normalisée.
