# Changelog V2.1.3.9E préproduction

Base technique exclusive : V2.1.3.9D préproduction jointe.

## Module 3
- Ajout de l’entrée **Examiner une hypothèse conservée**.
- Affichage du nom, de la définition Clarté360 et du contexte utile issu du Module 4.
- Trois décisions explicites : commencer l’examen, conserver pour plus tard, supprimer définitivement.
- Le retrait du Panier Hypothèses n’intervient qu’au démarrage volontaire de l’examen.
- En cas d’annulation du travail, l’hypothèse est restaurée dans son panier d’origine.

## Module 4
- Ajout d’un mini-fil conversationnel repliable affichant tous les couples questions-réponses validés du cycle.
- Barrière déterministe contre les questions identiques ou quasi identiques.
- Traitement spécifique de « Je ne sais pas », « aucune idée », « rien ne me vient », etc. : la question du mot n’est pas reposée et l’autorisation de proposer des hypothèses est demandée.
- Limite absolue de cinq questions sur un même axe, avec convergence obligatoire.
- Synchronisation atomique d’une piste à clarifier : suppression des listes actives, conservation historique, ajout éventuel de la nouvelle hypothèse.
- Déduplication du Panier Hypothèses.
- Conservation du contexte d’origine et des échanges dans chaque hypothèse.

## Interface
- Intitulés latéraux normalisés : MODULE 1 à MODULE 5 avec leur titre.
- Panneau de suivi enrichi avec une section **À explorer — Module 4**.
- Gestion des reformulations identiques ou presque identiques : message adapté et suppression des doubles blocs artificiels.

## Compatibilité et données
- Chargement explicite des paniers vides ou remplis lors de la reprise JSON.
- Conservation des structures historiques 8F, 9C et 9D déjà prises en charge par la migration existante.
- Aucun transfert automatique d’une hypothèse du Module 4 vers le Module 3.
