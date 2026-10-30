# GO23-3 — repère d’intérêt RIASEC pour les métiers ROME

Candidate : `0.4.6-go23-3-work`, schéma 9  
Statut officiel : GO22, GO23 et GO24 restent ouverts. GO21 RC2 reste le dernier jalon validé.

## Fonction réalisée

- L’application embarque un index hors ligne de 1 911 codes ROME et de leurs repères RIASEC normalisés. Il est dérivé du classeur ROME/RIASEC fourni et du corpus de fiches PDF daté de juin 2026. Le corpus ne marque aucune ligne « à vérifier ».
- Le repère apparaît auprès des métiers retenus dans les écrans accompagnateur et bénéficiaire, même si l’API France Travail n’est pas disponible.
- L’interface indique la source et précise qu’il s’agit d’un repère d’intérêt à mettre en regard du PIP avec l’accompagnateur. Il ne mesure ni compétence ni aptitude et ne produit aucun score de compatibilité.
- Aucun PDF source n’est recopié dans l’application. Seul l’index utile aux écrans est embarqué.

## Contrôles

- Contrôle des 1 911 lignes, des codes ROME uniques, des valeurs RIASEC et des repères M1203/M1501.
- AppTest de l’affichage côté bénéficiaire et du rappel « pas une compétence/aptitude ».
- Suite complète : 261 tests réussis; compilation Python réussie.

## Limites

- Le repère provient du corpus de PDF fourni, pas d’une réponse live de l’API France Travail.
- Un code manquant dans l’index n’empêche pas l’étude du métier.
- Le RIASEC ne sélectionne, ne classe et n’écarte aucun métier ni bénéficiaire.
- Ce jalon ne vaut pas recette métier ni validation GO23.
