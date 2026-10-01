# Jalon C - Scoring

Version 0.3.0. Le moteur est local, déterministe et sans IA.

- item direct : score corrigé = réponse 1..5 ;
- item inversé : score corrigé = 6 - réponse ;
- facette : moyenne des 4 items corrigés ;
- domaine : moyenne des 24 items corrigés, contrôlée comme égale à la moyenne des 6 facettes ;
- indice interne 0-100 : `(moyenne - 1) / 4 * 100`, explicitement non percentile ;
- 30 facettes et 5 domaines obligatoires ;
- scoring refusé tant que les 120 réponses ne sont pas présentes.

Aucune interprétation narrative n'est introduite au Jalon C. Elle appartient au Jalon D.
