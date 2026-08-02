# Rapport de tests - V2.1.3.9D préproduction

- Compilation : OK (`python -m py_compile app.py`)
- Tests automatisés : 71 réussis / 71

## Scénarios couverts
- Version et schéma 9D.
- Blocage du questionnaire spécifique pour une formulation de besoin, peur, émotion, état recherché ou objectif.
- Création et persistance d'une Piste à clarifier.
- Absence de choix « Pistes à clarifier » dans le Module 3.
- Présence conditionnelle de la troisième voie du Module 4.
- Verticalité renforcée avant la demande d'un mot.
- Conservation de la règle : hypothèse Module 4 vers panier Hypothèses uniquement.
- Non-régression des tests historiques 8B à 9C.

## Tests réels indispensables sur Streamlit
- « Sécurité financière » / « Peur d'être en manque financière » doit être bloquée avant le questionnaire spécifique.
- Envoi vers Pistes à clarifier, reprise dans la voie 3, puis disparition de la piste après issue du cycle.
- Qualité et non-répétition des trois à cinq relances verticales.
- Saisie vocale : un seul clic visible pour obtenir la transcription sur plusieurs navigateurs.
- Saisie écrite : comportement Ctrl+Entrée à contrôler dans le navigateur, car il dépend du composant Streamlit.
