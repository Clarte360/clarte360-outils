# Rapport de tests V2.1.3.9E préproduction

## Tests automatisés
- Compilation Python de `app.py` : réussie.
- Suite Pytest complète : **78 tests réussis, 0 échec**.
- Ajout de tests spécifiques 9E sur :
  - ouverture volontaire d’une hypothèse depuis le Module 3 ;
  - mini-fil vertical visible ;
  - non-répétition et limite de cinq questions ;
  - synchronisation atomique des pistes à clarifier ;
  - intitulés du menu ;
  - reformulations identiques ou légèrement corrigées.

## Contrôles statiques réalisés
- Version déclarée : `2.1.3.9E-preproduction`.
- Aucun environnement virtuel inclus.
- Aucun cache Pytest, `__pycache__` ou fichier `.pyc` inclus dans la livraison.

## Tests réels restant à effectuer sous Streamlit
1. Parcours complet « Sécurité financière » vers « Autonomie » avec une vraie API.
2. Vérification visuelle du fil conversationnel sur écran ordinateur et mobile.
3. Test vocal dans les Modules 1 à 4 avec plusieurs navigateurs et autorisations micro.
4. Reprise de deux sauvegardes réelles : un JSON 8F et le JSON final 9D du test précédent.
5. Vérification manuelle des quatre cas de reformulation : identique, correction légère, correction importante, reformulation réellement différente.
6. Contrôle d’un abandon ou d’une fermeture de session pendant l’examen d’une hypothèse afin de confirmer sa restauration dans le panier.
