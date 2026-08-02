# Rapport de tests – V2.1.3.9-preproduction

## Contrôles réalisés

- Compilation Python (`py_compile`) : **conforme**.
- Analyse syntaxique AST : **conforme**.
- Version applicative et schéma JSON : **2.1.3.9**.
- Présence de 8 micro-exercices : **conforme**.
- Garde de non-rejeu après achèvement : **conforme**.
- Absence de score, profil et conclusion dans le parcours : **conforme**.
- Possibilité d'ignorer chaque question : **conforme**.
- Conservation de la réponse, des propositions, de la version, de la date et du statut : **conforme**.
- Export dans le JSON de reprise : **conforme**.
- Panier Hypothèses séparé de `values_to_examine` : **préparé et conforme**.
- Référentiel Excel de justification : **8 lignes, conforme**.
- Compatibilité ascendante : les nouvelles clés sont ajoutées par `init_state` aux anciennes sauvegardes.

## Limite du contrôle dans cet environnement

Le serveur Streamlit n'a pas pu être lancé ici, la commande Streamlit n'étant pas installée dans l'environnement d'exécution. Le paquet contient toutefois la dépendance requise dans `requirements.txt`. Un test réel d'interface reste obligatoire avant de poursuivre vers la voie 1 et la voie 2.
