# Rapport de tests — RC2-2-2 P5 — 02/10/2026

- 506 tests collectés dans 89 fichiers.
- Tests P5 + J11/J17 ciblés : 13/13 verts.
- Campagne exhaustive exécutée par lots/fichiers en raison de la limite de durée d'une commande unique dans l'environnement : tous les 89 fichiers ont été exécutés, aucun échec observé.
- Compilation : `PYTHONPATH=. python -m compileall -q .` OK.
- Test ajouté : `tests/test_intervenants_rc2_2_2_p5_actions.py` (3 scénarios).

Scénarios P5 spécifiques : recalcul immédiat après validation humaine, maintien du blocage si niveau insuffisant, exception d'affectation distincte et obligatoirement motivée.
