# Rapport de tests - V2.1.3.8F-preproduction

## Contrôles exécutés

- Compilation Python de `app.py` : réussie.
- Suite automatisée pytest : **46 tests réussis sur 46**.
- Chargement dynamique du référentiel enrichi : contrôlé, 318 entrées détectées.
- Présence de `Perfectionnisme` dans le référentiel livré : contrôlée.
- Normalisation contextuelle :
  - `L'optimisme, je répète, l'optimisme.` -> proposition `Optimisme` ;
  - `Loopisme` -> proposition prudente `Optimisme`.
- Non-substitution sémantique : `Perfectionnisme` n'est pas transformé en `Professionnalisme`.
- Pagination PDF : styles `keepWithNext` et garde-fous `CondPageBreak` présents.
- Version applicative : `2.1.3.8F-preproduction`.
- Version schéma JSON : `2.1.3.8F`.

## Limite du contrôle automatisé

Les appels réels aux services OpenAI, le microphone du navigateur et le rendu Streamlit sur le serveur de production nécessitent un test fonctionnel après déploiement. Les chemins de traitement et les garde-fous associés sont couverts statiquement et par tests unitaires.
