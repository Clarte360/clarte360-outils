# INCREMENT — INTERVENANTS RC2-2-1 — 01/10/2026

Version cible : `3.0.0-INTERVENANTS-RC2-2-1`

## Objet
Consolidation de RC2-2 avec les modifications GitHub/VPS apparues après la photographie RC2-1 : intégration IPIP-NEO-120 et correction d'accès PIP RIASEC.

## Contenu
- intégralité du chantier RC2-2 conservée ;
- IPIP_NEO120 ajouté au registre versionné ;
- lancement IPIP signé dans l'espace bénéficiaire et `tool_launch_page` ;
- fonctions IPIP services : signature, événements, outbox, archivage PDF, contrôle SHA-256/taille, statut connecteur ;
- worker IPIP intégré avant la sortie anticipée SMTP ;
- correction PIP : suppression de l'expiration métier arbitraire dans `build_pip_prescription_launch()` et blocage uniquement lorsque la prescription est `TERMINE` (ou annulée) ;
- IPIP aligné : même prescription bloquée à `TERMINE` ;
- nouvelle prescription PIP/IPIP autorisée après une prescription antérieure `TERMINE` ;
- garde-fou `launch_type` adapté : seuls PIP et IPIP sont spécialisés `EXTERNAL_SIGNED`, un outil arbitraire reste `HUB_REDIRECT` ;
- test historique RC7 adapté sans être supprimé ;
- aucun document professionnel, signature, base runtime ou secret issu de RC2-1_1 n'est repris.

## Références
Voir :
- `AUDIT_FUSION_RC2_2_RC2_1_1_20261001.md`
- `RAPPORT_TESTS_INTERVENANTS_RC2_2_1_20261001.md`
- `CHECKLIST_RECETTE_INTERVENANTS_RC2_2_1_20261001.md`
