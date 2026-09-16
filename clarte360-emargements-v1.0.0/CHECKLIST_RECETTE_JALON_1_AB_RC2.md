# CHECKLIST RECETTE JALON 1 A+B RC2

## Outils
- [ ] CLA0004 : sélectionner PIP RIASEC + Boussole.
- [ ] Cliquer ENREGISTRER LES OUTILS DE L'ACTION.
- [ ] Vérifier « Outils autorisés = 2 ».
- [ ] Faire F5 : les deux outils restent sélectionnés.
- [ ] Retirer Boussole et enregistrer.
- [ ] Faire F5 : PIP reste seul autorisé.
- [ ] Vérifier que les prescriptions historiques Boussole restent visibles.
- [ ] Vérifier la colonne « Prescrit par » avec identité + rôle.
- [ ] Vérifier qu'un doublon actif même outil/bénéficiaire/action est refusé quel que soit le créateur.

## Suppression action
- [ ] La suppression définitive apparaît uniquement dans Actions.
- [ ] Action sans signature : n° action + mot de passe ADMIN requis.
- [ ] Action avec signature : suppression bloquée par défaut.
- [ ] Action signée d'essai : Oui « action d'essai » + Oui « essais terminés » + n° action + mot de passe.
- [ ] Après suppression : action absente de toutes les vues et données propres supprimées.
- [ ] Les identités permanentes bénéficiaire/intervenant partagées restent présentes.
- [ ] Si Teams distante existe : réunion distante supprimée avant purge locale ; échec Graph = purge locale bloquée.
