# CLARTÉ360 — PIP RIASEC / O*NET — RAPPORT DE TESTS JALON B

Date : 18/09/2026

## Résultat automatisé

Commande : `PYTHONPATH=. pytest -q`

- Tests exécutés : 130
- Tests réussis : 130
- Échecs : 0
- Warnings pytest : 0 signalé

## Contrôles spécifiques B

- Consentement RGPD reconnu une seule fois par version du texte.
- Persistance et restauration de `rgpd_acceptance` et `study_consent`.
- JSON timeout ne restaure jamais sur l'écran timeout.
- Réparation d'un ancien snapshot timeout.
- Reprise d'un PIP existant sans remise à zéro.
- Conservation du parcours PIP/O*NET et du timing de choix.
- Réinitialisation de l'activité lors d'une restauration.
- Message et bouton timeout conformes au CDC.
- RGPD présenté avant l'identité en PUBLIC.
- Banque active toujours à 72 items.
- Compilation Python des composants modifiés réussie.
- Synchronisation tableur maître / JSON runtime : OK (`build_pip_runtime.py --check`).

## Limites

La recette navigateur réelle, la recette SMTP réelle, la recette serveur accompagnement et la recette VPS seront réalisées aux étapes prévues par le CDC. Aucun test externe réel n'a été simulé artificiellement.
