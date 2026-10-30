# GO22 RC3E — correction C-AV2 « à affiner »

Date : 23 octobre 2026. Candidate technique non validée. GO21 RC2 reste le dernier jalon validé.

## Correction

Le modèle de réponses autorisait déjà les états `AUCUN_CRITERE_IDENTIFIE` et `A_AFFINER`, mais les contrôles C-AV2 n'affichaient que l'absence de priorité. Les sections Valeurs, Moteurs et Préférences exposent maintenant les deux réponses distinctement, avec ou sans résultats de rapports structurés.

Les choix de priorités et une réponse d'absence sont exclusifs. Le plafond de trois choix existant reste appliqué. Aucun résultat n'est déduit du rapport pour cocher les choix.

## Contrôles

- Tests dédiés : affichage et persistance de `A_AFFINER` pour les trois blocs avec rapports et sans rapport.
- Régression AppTest : 39 scénarios C-AV1/C-AV2/R1/R2 réussis après correction.
- Suite complète : 212 tests réussis.
- `python -m compileall -q .` : réussite.

## Limites conservées

L'import Hub/GDA n'est pas raccordé. Les références et résultats saisis manuellement par l'accompagnateur ne valent pas une provenance vérifiée; les rapports synthétiques restent explicitement fictifs. Aucun appel IA réel, appel France Travail réel, essai VPS ou validation métier n'est revendiqué. Le raccordement du client IA commun reste conditionné au contrat GO-26 et à l'accès au module partagé existant; aucune clé ou section de secret n'a été créée.

