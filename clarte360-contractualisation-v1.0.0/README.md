# Clarté360 – Contractualisation V1.1.1 VPS / base locale

Cette version est destinée à être exécutée sur le VPS Clarté360, mais **la base Excel Clarté360 reste sur l'ordinateur de l'administrateur**.

## Principe
1. Charger ponctuellement la base `.xlsm` locale dans l'application.
2. Charger une APS JSON ou reprendre une action existante.
3. Compléter les informations contractuelles manquantes.
4. L'application injecte les données dans `CONV ADM` et les financeurs dans `FINANCEMENTS` sur la copie en mémoire.
5. Le contrat PDF et le JSON contractuel sont générés.
6. Télécharger la base `.xlsm` mise à jour et remplacer la base locale après contrôle.

Aucune base Excel Clarté360 n'est conservée de façon persistante sur le VPS.

## Règles BC particulier bipartite actuellement actives
- `NO_CLAR` : prochain numéro libre.
- Données bénéficiaire : APS JSON vers `CONV ADM`.
- Particulier : `NOM_ENT`, `ADRESSE`, `CODE_POST`, `VILLE` reprennent le bénéficiaire.
- `SPEC_BPF` : `Autres`.
- Prix : seul `INTRA_HT` reçoit le montant total HT saisi.
- `CALENDRIER` : texte exactement saisi dans le masque.
- Dates : vraies dates Excel avec format porté par la colonne existante.
- Contacts de mise en place : laissés vides pour un particulier bipartite.
- Financeurs : plusieurs lignes possibles dans `FINANCEMENTS`, reliées par `NO_CLAR`.
- `FACTURE_A_ETABLIR_A` : reprend les destinataires renseignés dans les lignes de financement.

Le moteur PDF actif en V1 concerne le contrat de prestation de bilan de compétences particulier bipartite.
