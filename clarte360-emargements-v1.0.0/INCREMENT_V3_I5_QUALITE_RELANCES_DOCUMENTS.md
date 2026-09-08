# CLARTÉ360 — GESTION DES ACTIONS V3
## Incrément I5 — Qualité, relances manuelles et documents finaux

Version : **3.0.0-I5** — cumulative **I1 + I2 + I3 + I4 + I5**.

## Envois qualité
- HOT, COLD et retour intervenant : **un seul envoi automatique INITIAL**.
- Les anciens événements automatiques `REMINDER_1` / `REMINDER_2` encore PENDING sont neutralisés en `SKIPPED` sans suppression de preuve historique.
- Le worker n'exécute plus que les événements `INITIAL` et les relances explicitement manuelles `MANUAL_n`.

## Relances manuelles
- Une relance ne crée jamais une nouvelle campagne.
- Le même token et le même lien sont réutilisés.
- Chaque relance ajoute un événement `MANUAL_n`, incrémente le compteur et conserve auteur/date dans la campagne et dans l'audit.
- L'administration dispose d'un écran global **Relances** avec sélection groupée des questionnaires non revenus.
- Les émargements de séances terminées dont la situation reste indéterminée sont listés comme éléments à régulariser.

## Qualité métier
- Un écran Administration **Qualité** complète le tableau de bord.
- Les rubriques sont présentées avec des libellés métier et non uniquement des codes techniques.
- Sont visibles : taux de réponse, scores moyens par rubrique, points faibles, difficultés ouvertes et actions d'amélioration.
- Le calcul des moyennes par rubrique a été corrigé afin d'exploiter réellement les clés retournées par le moteur statistique.

## Multi-intervenants
- Si le module Retour intervenant est actif, une campagne TRAINER est préparée pour chaque intervenant actif rattaché à l'action, et non uniquement pour l'ancien `trainer_id` V2.

## Documents finaux
- Les questionnaires complétés restent générés en PDF professionnel.
- Ils sont désormais directement téléchargeables depuis l'onglet Documents de l'action.
- Le dossier final collectif conserve le format `AAMMJJ NO_ACTION DOCS STAGIAIRES.zip`, sans attendre l'évaluation à froid.
- La transmission client et l'envoi ultérieur d'un COLD restent séparés et protégés contre les doublons.

## Compatibilité
- Migration additive uniquement : trois colonnes de suivi des relances manuelles sont ajoutées à `quality_campaigns`.
- Aucune suppression des données V2/I1/I2/I3/I4.
- URL, chemin VPS, services systemd, dépôt et secrets inchangés.
- Teams reste hors périmètre jusqu'à I7.
