# Clarté360 - Recherche de mes valeurs - V2.1.3.9D préproduction

## Module 3 - barrière de nature conceptuelle
- La définition personnelle prime désormais sur le seul libellé.
- Un besoin, une peur, une émotion, un état recherché ou un objectif ne peut plus poursuivre le questionnaire spécifique comme valeur.
- Dans ce cas, le questionnaire spécifique est bloqué avant toute validation.
- Le bénéficiaire peut : envoyer le sujet vers « Pistes à clarifier » du Module 4, le supprimer définitivement ou le placer « À revoir en séance ».
- Les « Pistes à clarifier » ne sont jamais proposées comme choix d'entrée dans le Module 3.

## Module 4 - troisième voie
- Ajout d'une voie conditionnelle « Explorer une piste à clarifier ».
- La voie n'est visible que lorsqu'une piste issue du Module 3 existe.
- Le terme initial, sa définition et les éléments déjà enregistrés sont repris sans demander au bénéficiaire de tout recommencer.
- La voie utilise le même moteur complet de questionnement vertical que les voies 1 et 2.
- Si une valeur plausible émerge, elle rejoint uniquement le panier Hypothèses.
- Si aucune valeur n'émerge, la piste disparaît des listes actives et reste seulement traçable dans l'historique.

## Questionnement vertical commun aux trois voies
- La question demandant un mot ne peut plus intervenir immédiatement après le récit initial.
- Le moteur recherche normalement trois à cinq relances utiles, avec un maximum de cinq.
- La question cible désormais « ce qui était le plus important » et non le seul ressenti.
- Une relance presque identique à une question déjà posée est interdite.
- Une idée explorée ne peut toujours produire qu'une seule hypothèse retenue.

## Données et compatibilité
- Ajout de `clarification_tracks` / `pistes_a_clarifier` dans l'état et le JSON de reprise.
- Compatibilité conservée avec les sauvegardes antérieures : la nouvelle liste est vide lorsqu'elle n'existe pas.
- Aucun transfert automatique du Module 4 vers le Module 3.

## Tests
- Compilation Python réussie.
- 71 tests automatisés réussis.
