# GO30 — Moteur de préparation du questionnaire 0.4.38

## Diagnostic du blocage 0.4.37

La version 0.4.37 enregistrait les sept associations GDA, mais transmettait seulement leurs références au générateur. Celui-ci créait les idées à partir d’une liste `idea_list` qui n’était jamais alimentée par l’APS. Les rapports n’avaient pas non plus de `result_summary`. Le questionnaire pouvait donc être enregistré avec zéro piste, des repères vides et des questions génériques. Les associations 7/7 ne prouvaient pas que le contenu avait été lu.

## Comportement candidat 0.4.38

- Les pièces retenues sont récupérées temporairement par leur référence GDA. Le binaire n’est pas copié dans le stockage métier C&P.
- Une seule confirmation de consentement intervient avant l’envoi des textes extraits au service IA configuré. La décision est inscrite dans l’audit avec les références des pièces, le fournisseur et `store=false`; le contenu documentaire n’est pas écrit dans l’audit.
- Le CV aide à formuler la question de contexte d’une piste APS. Le CV ne devient pas une idée de métier. Une observation privée facultative de l’intervenant peut orienter cette question comme hypothèse à vérifier; elle n’est pas présentée comme une parole du bénéficiaire.
- Les pistes doivent être rattachées à une citation exacte de l’APS. Les lignes de résultats des rapports doivent comporter une citation littérale; libellés, scores et pôles de préférence sont contrôlés contre cette citation avant l’enregistrement.
- Les résumés validés sont insérés dans la structure existante des repères personnels. Aucun choix ni score manquant n’est inventé. Un résultat sans donnée exploitable reste vide et est signalé comme tel.
- Une nouvelle génération crée une nouvelle version immuable du questionnaire. Un brouillon vide issu de la 0.4.37 peut être repris depuis les pièces déjà validées, sans nouvelle sélection et sans RAZ.
- La publication reste manuelle après relecture; aucun courriel automatique n’est envoyé.
- Fermer l’aperçu modal ne relance plus toute la page, afin de préserver la position dans la liste des documents.

## Limites

- Les PDF image sans couche texte ne sont pas analysés. Le système doit afficher l’erreur et ne pas enregistrer un brouillon vide.
- L’analyse fournit des propositions à examiner par l’intervenant; elle ne remplace ni la lecture des sources ni l’échange avec le bénéficiaire.
- Le VPS doit disposer de la configuration IA déjà utilisée par C&P. Aucune nouvelle clé ou aucun secret n’est ajouté.

## Vérification locale

`compileall` et un scénario manuel avec client IA factice ont vérifié l’extraction structurée, la validation des citations, le rattachement CV/APS, les repères de rapports et la validation finale du questionnaire. La suite pytest n’a pas pu être exécutée dans l’environnement de travail, où `pytest`, `SQLAlchemy` et `Streamlit` ne sont pas installés.
