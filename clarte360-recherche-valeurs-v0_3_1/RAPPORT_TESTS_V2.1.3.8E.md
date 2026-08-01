# Rapport de tests — V2.1.3.8E

## Contrôles automatisés

- Compilation Python : réussie.
- Suite Pytest : **40 tests réussis sur 40**.
- Contrôle AST et imports : réussi.
- Contrôle du référentiel : 241 valeurs chargées ; `Clarté` identifiée sous `RVC360-241`.
- Contrôle de la structure JSON de reprise : réussi.
- Contrôle de la source centrale des rapports : réussi.
- Contrôle d’absence de secrets réels dans les fichiers livrés : réussi.

## Contrôles dynamiques complémentaires

- `L’autonomie.` devient `Autonomie`.
- `L'honnêteté` devient `Honnêteté`.
- `La securité financier` devient `Sécurité financière`.
- `PLAISIR` devient `Plaisir`.
- Une phrase telle que « J'aime faire plaisir aux autres personnes » est détectée comme n’étant pas un nom de valeur.
- Une valeur validée est retirée de la liste « À examiner ».
- Les quatre décisions métier sont présentes et obligatoires.
- Les questions complémentaires et leurs réponses sont conservées dans la fiche de la valeur.

## Limites des tests locaux

Les parcours OpenAI, transcription audio et SMTP dépendent des secrets et du réseau de l’environnement Streamlit. Le code et les branches de traitement ont été contrôlés statiquement et par tests unitaires ; les essais réels restent à effectuer sur l’instance Streamlit avec les secrets provisoires.
