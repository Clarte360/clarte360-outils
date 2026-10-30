# GO26 — diagnostic live des connecteurs IA sur données fictives

Le script `tools/test_openai_live_synthetic.py` appelle un seul connecteur par exécution avec un jeu intégré entièrement fictif : C‑AV3, enrichissement CV ou rapprochement ROME. Il lit la même configuration OpenAI que l’application via `Cav3AISettings.from_streamlit_secrets()`; aucune clé ne doit être passée en argument ou copiée dans la commande. Le diagnostic ROME France Travail complémentaire `tools/test_france_travail_rome_all.py` vérifie les quatre fiches de référence et la recherche d’intitulés/appellations; les appels GET respectent la limite officielle d’un appel par seconde.

Depuis la racine de la candidate, dans l’environnement où les secrets Streamlit habituels sont montés :

```bash
python tools/test_openai_live_synthetic.py --pipeline cav3
python tools/test_openai_live_synthetic.py --pipeline cv
python tools/test_openai_live_synthetic.py --pipeline rome
```

Chaque exécution ne produit qu’un résultat structuré, son modèle et ses métadonnées de contrôle. Le script n’ouvre aucun dossier, CV ou document GDA réel et ne modifie pas de dossier C&P. Le texte fictif de sortie est affiché afin de permettre sa revue humaine; aucun verdict n’est écrit en base. En cas d’erreur, seul un message expurgé est retourné, jamais le corps HTTP ni un secret.

Les validateurs locaux imposent également les références autorisées, les champs attendus et les longueurs maximales avant d’accepter les sorties C‑AV3 et ROME. Un statut `OK` prouve seulement qu’un appel synthétique a abouti dans cet environnement. GO26 reste ouvert jusqu’à l’exécution VPS et la revue de pertinence, de références, d’incertitudes et d’abstention pour les trois pipelines. Un test simulé ou l’existence du script ne vaut pas essai live.
