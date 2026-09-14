# CLARTÉ360 — RAPPORT DE TESTS V3 I9-D

Date : 12/09/2026

## Résultat
- Suite complète : **155 tests réussis / 155**.
- Compilation Python modules principaux : **OK**.

## Couverture I9-D ajoutée
- migrations additives catalogue/prescriptions/tokens/événements ;
- droit intervenant de prescription par action ;
- PIP RC5 pré-référencé sans contournement du futur lancement signé ;
- ajout d’un outil générique non-PIP ;
- prescription admin vers bénéficiaire permanent/action ;
- filtrage par compatibilité prestation ;
- jeton de lancement temporaire, hashé et à usage unique ;
- transition `CONSULTE` lors de la résolution Hub ;
- événements de statut et idempotence par `event_id` ;
- portail bénéficiaire métier sans identifiants techniques de connecteur.

## Limite volontaire
Le connecteur signé PIP RC5, sa clé HMAC, la consommation de son outbox et les retours CONSULTÉ/EN_COURS/TERMINÉ appartiennent à I9-E. Ils ne sont pas simulés comme s’ils étaient déjà opérationnels dans I9-D.

## Test de version
Le test historique `test_candidate_version_is_rc` attendait encore `3.0.0-I9-A` alors que les lots B/C avaient conservé ce marqueur. I9-D aligne désormais explicitement `APP_VERSION` et ce test sur `3.0.0-I9-D`. Cette modification ne change aucune règle métier ; elle corrige uniquement le marqueur de version de la candidate courante.
