# CHECKLIST RECETTE — JALON 1 A+B — RC1

## A — Outils Clarté360
- [ ] ADMIN : sélectionner exactement 3 outils sur une action et enregistrer.
- [ ] F5 / retour dans l'action : les 3 mêmes outils sont sélectionnés.
- [ ] Espace intervenant autorisé : exactement les mêmes 3 outils sont disponibles.
- [ ] Intervenant sans droit de prescription : prescription refusée.
- [ ] Activer le droit : prescription possible.
- [ ] Refaire la même prescription active : refus clair de doublon.
- [ ] Créateur : annuler la prescription, puis vérifier qu'une nouvelle prescription devient possible.
- [ ] ADMIN : annuler en supervision une prescription créée par un autre utilisateur et vérifier le journal.

## A — Documents
- [ ] ADMIN : déposer simultanément un PDF et un JSON.
- [ ] Vérifier nom, catégorie, origine, date, SHA-256, auteur et téléchargement.
- [ ] INTERVENANT autorisé : déposer plusieurs documents en une fois.
- [ ] BÉNÉFICIAIRE : vérifier qu'un document individuel n'apparaît pas chez un autre bénéficiaire.
- [ ] Vérifier qu'une preuve marquée réglementaire/protégée ne peut pas être retirée par suppression standard.

## B — Affectations / Teams
- [ ] Créer une action avec 2 intervenants et 3 bénéficiaires.
- [ ] Affecter le second intervenant comme coanimateur sur un créneau.
- [ ] Vérifier la même affectation dans ADMIN, espace intervenant, Teams, communications et contresignatures.
- [ ] Ajouter/modifier le créneau et vérifier la synchronisation interne Teams.

## B — H-2 / H-15
- [ ] Action Teams active : vérifier un H-2 et un H-15 par bénéficiaire et par intervenant/coanimateur.
- [ ] Vérifier lien Teams et lien espace personnel.
- [ ] Bénéficiaire non activé : vérifier le rappel d'activation sans blocage du lien Teams.
- [ ] Modifier l'horaire avant envoi : vérifier le recalcul des rappels non envoyés.
- [ ] Annuler le créneau : vérifier qu'aucun rappel restant n'est envoyé.
- [ ] Vérifier l'absence de doublon d'envoi.

## B — Émargement / contresignature
- [ ] 1 signé + 1 présent non signé + 1 absent.
- [ ] Vérifier que la contresignature reste bloquée tant que les non-signés ne sont pas qualifiés.
- [ ] OUI présent : statut Présent à régulariser + possibilité de relance.
- [ ] NON : statut Absent.
- [ ] Vérifier une seule contresignature par intervenant/créneau.
- [ ] Vérifier qu'aucun créneau futur non finalisé n'apparaît comme contresignature attendue.

## B — Preuve Teams
- [ ] Un pseudo non rapproché reste visible comme trace technique.
- [ ] Vérifier la formulation `Rapprochement non établi` et l'absence de conclusion automatique d'absence.
- [ ] Vérifier que la preuve Teams ne remplace jamais l'émargement réglementaire.
