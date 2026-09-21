# Rapport de tests — Intervenants J5

Date : 20/09/2026

## Résultat global
**393 tests réussis — 0 échec — 0 régression.**

Baseline J4 : 389 tests.
Nouveaux tests J5 : 4.

## Tests J5 ajoutés
1. Gateway IA et réponse structurée JSON schema.
2. Proposition IA incapable d'écraser une validation humaine verrouillée.
3. Réanalyse IA : seule la partie `ai_*` évolue, historique conservé.
4. Minimisation du payload : e-mail et téléphone exclus de l'analyse métier.

## Contrôles complémentaires
- Compilation Python de `qualification_ai.py`, `db.py`, `services.py`, `app.py` : OK.
- Aucun secret/API key ajouté au package.
- Le test local utilise un faux client IA ; aucune clé réelle n'est nécessaire au test automatique.

## Limite de validation
L'appel réseau réel à OpenAI n'a pas été exécuté dans l'environnement local de construction, qui n'expose pas les secrets VPS. La recette d'appel réel sera effectuée au stade VPS avec le secret central existant, sans afficher ni journaliser la clé.
