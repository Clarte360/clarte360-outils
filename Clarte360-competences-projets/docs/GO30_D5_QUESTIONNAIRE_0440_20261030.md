# GO30 — capacité d'analyse des sept pièces 0.4.40

## Blocage observé

Après la génération 0.4.39, les sept pièces étaient bien conservées, mais l'analyse s'arrêtait sur `Le volume cumulé des pièces dépasse la limite d’analyse`. Le plafond global (70 000 caractères) était inférieur à la somme possible des sept extraits autorisés à 18 000 caractères chacun.

## Correctif

- Le plafond cumulé est porté à 126 000 caractères, soit sept extraits de 18 000 caractères.
- Les sept documents vérifiés restent sélectionnés ensemble; aucun document n'a à être retiré ou rapproché à nouveau.
- Les limites par pièce et de sortie restent en place; seules les tailles d'entrée destinées à l'analyse changent.
- Après génération, le brouillon reste à relire et à publier manuellement.

## Contrôles

- `compileall` réussi.
- Scénario simulé avec sept extraits de 18 000 caractères : la limite cumulée est acceptée.
- Archive ZIP et syntaxe du script d'installation vérifiées.
