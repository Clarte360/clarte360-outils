# J2C RC6 — Outils / PIP 1.0.10 — 2026-09-18

## Correctifs
- Autorisation des outils par action sauvegardée automatiquement dès ajout/retrait dans le multiselect.
- Suppression du bouton intermédiaire qui pouvait laisser croire qu’une sélection était déjà persistée.
- Confirmation visuelle des outils ajoutés/retirés.
- Maintien de la règle V3.1 : aucun filtrage d’éligibilité selon le type de prestation ; tout outil actif et prescriptible peut être autorisé sur toute action.
- Métadonnées du PIP alignées sur la version réellement déployée : 1.0.10 ACCOMPAGNEMENT.
- Le champ historique `compatible_prestations` du PIP est vidé et reste non contraignant.

## Non-régression
- Les permissions par action restent le seul verrou métier avant prescription.
- Les outils autonomes restent autonomes.
- Le PIP conserve son lancement signé spécialisé.
