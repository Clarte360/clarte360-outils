# Changelog V2.1.3.9E3-preproduction

## Correctif ciblé issu de l'audit 9E2

1. **Ctrl + Entrée rattaché au champ actif**
   - Chaque zone de réponse écrite reçoit un repère DOM unique.
   - Le gestionnaire identifie le repère correspondant à la zone de texte active.
   - La recherche du bouton est limitée au segment compris entre ce repère et celui du champ suivant.
   - Deux champs affichant le même libellé ne peuvent donc plus déclencher l'action l'un de l'autre.

2. **Aucune évolution métier supplémentaire**
   - Les règles de choix, de reformulation, de validation et de conservation de la formulation initiale de la 9E2 sont conservées.

3. **Tests**
   - Vérification de la présence d'un repère unique par widget de réponse.
   - Vérification du bornage de la recherche entre le champ actif et le champ suivant.
   - Vérification de l'abandon de la recherche globale du premier bouton par son seul libellé.
