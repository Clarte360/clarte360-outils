# Changelog V2.1.3.9E1-preproduction

## Correctifs bloquants issus de l’audit 9E

### Réponses écrites
- ajout d’un gestionnaire navigateur réel pour **Ctrl + Entrée** ;
- Ctrl + Entrée déclenche le bouton Streamlit « Préparer et comparer » ;
- le traitement reste identique au clic manuel et ne crée pas une seconde validation.

### Première comparaison texte
- utilisation immédiate de `_text_difference_kind` ;
- texte identique : une seule réponse affichée ;
- correction légère : une seule version corrigée affichée avec un message de correction de forme ;
- reformulation réelle : affichage comparatif des deux formulations.

### Première comparaison vocale
- application de la même classification dès la première transcription ;
- suppression des deux blocs artificiellement différents lorsqu’il ne s’agit que d’une correction légère.

### Documentation
- version courante corrigée en 9E1 ;
- suppression de l’ancienne règle 8F niant l’existence d’un Panier Hypothèses distinct.

### Tests
- ajout de tests exécutant réellement la fonction de classement des différences ;
- vérification structurelle du gestionnaire Ctrl + Entrée et de son branchement sur la première saisie.
