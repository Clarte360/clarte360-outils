# Rapport de tests — Jalon F

Date : 18/09/2026

## Contrôles fonctionnels ajoutés
- synchronisation tableur ROME → JSON runtime ;
- 1 911 fiches chargées ;
- contrôle d’un profil EC : 170 correspondances exactes ;
- sélection limitée à 6 fiches, déterministe et diversifiée ;
- absence de score de compatibilité métier ;
- absence de profil à deux lettres forcé en cas d’égalité ;
- génération du rapport PIP avec section ROME ;
- version `PIP-RPT-1.4`.

## Résultats
La suite complète a été exécutée après intégration du Jalon F.

Résultat : **162 tests réussis, 0 échec**.

Contrôles complémentaires :
- compilation Python : OK ;
- `scripts/build_rome_runtime.py --check` : OK ;
- génération PDF exemple : OK ;
- rendu visuel PDF : 9 pages contrôlées, aucune collision ou coupure de texte constatée.
