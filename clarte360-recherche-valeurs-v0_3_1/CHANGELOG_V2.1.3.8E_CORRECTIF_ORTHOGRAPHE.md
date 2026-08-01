# Correctif V2.1.3.8E - correction linguistique obligatoire

## Objet
Le moteur ne doit plus conclure qu'une réponse est « suffisamment claire » lorsqu'elle contient une faute d'orthographe, d'accord, de conjugaison, de ponctuation ou de typographie.

## Modification
- correction linguistique systématique avant toute éventuelle reformulation stylistique ;
- conservation stricte du sens et de la première personne ;
- une correction très proche de l'original reste proposée lorsqu'elle corrige une faute réelle ;
- suppression du filtre de similarité qui rejetait les corrections mineures ;
- `AUCUNE_REFORMULATION` n'est accepté que lorsque le texte est déjà correct et ne nécessite aucune modification.

## Exemple attendu
Entrée : `Mon amour des choses toujours bien faite et sans défaut`

Proposition : `Mon amour des choses toujours bien faites et sans défaut.`
