# J6 RC2 — Intégration ACCOMPAGNEMENT et sécurité

Date : 02/10/2026
Version : 0.8.0-RC2

## Objet
Auditer et renforcer exclusivement le côté IPIP du contrat Gestion des Actions, sans modifier Gestion des Actions, GitHub ou le VPS.

## Renforcements réalisés
- suppression de l'ancien alias `rights` : seul `scopes` est accepté ;
- contrôle explicite de `IPIP_RESUME` lors de la reprise d'une prescription EN_COURS ;
- contrôle explicite de `IPIP_STATUS` avant publication de CONSULTE / EN_COURS / TERMINE ;
- contrôle explicite de `IPIP_RESULT_READ` pour une prescription TERMINE, le rapport et sa consultation ;
- validation anti-croisement beneficiary_id / action_id / participant_id / prescription_id également lors de la lecture du statut ;
- refus d'événements contenant des réponses brutes, y compris imbriquées ;
- renforcement du `report_ref` : report_id, prescription_id, passation_id, MIME, taille, SHA-256, version, date et référence de stockage relative ;
- refus d'un rapport situé hors de la racine persistante IPIP ;
- cohérence obligatoire entre la référence documentaire TERMINE et prescription/passation ;
- conservation de l'idempotence par event_id déterministe ;
- verrouillage TERMINE et obligation d'une nouvelle prescription pour une nouvelle passation maintenus.

## Correction de tests hérités découverte pendant J6
La campagne complète a révélé quatre assertions de tests J4/J5 devenues obsolètes par rapport au code J5 livré : apostrophe typographique de la vue d'ensemble, ancien paramètre `beneficiary_name`, ancien titre `Votre ressenti`, et assertion interdisant le mot « percentile » alors que le CDC exige précisément d'indiquer que le repère n'est PAS un percentile. Ces tests ont été remis en cohérence avec le comportement déjà validé ; aucun changement de scoring ou de référentiel n'en résulte.

## Interdictions respectées
- Gestion des Actions : non modifiée ;
- PIP RIASEC : non modifié ;
- GitHub : non touché ;
- VPS : non modifié ;
- secrets de production : non modifiés.
