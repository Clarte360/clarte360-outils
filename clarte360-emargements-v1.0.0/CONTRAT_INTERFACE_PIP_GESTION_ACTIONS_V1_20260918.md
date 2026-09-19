# CONTRAT D’INTERFACE PIP RIASEC / GESTION DES ACTIONS — V1

Date : 18/09/2026  
Base Gestion des Actions : Jalon G -> H  
Base PIP observée : `CLARTE360_PIP_RIASEC_ONET_JALON_E1_20260918.zip`

## 1. Lancement ACCOMPAGNEMENT
Jeton HMAC-SHA256 compact existant conservé. Le payload contient les IDs techniques, les champs lisibles `beneficiary_first_name`, `beneficiary_last_name`, `action_number`, `action_title`, et transmet simultanément le vocabulaire historique `rights` et le vocabulaire Hub `scopes`.

Valeurs figées : `tool_id=pip-riasec-onet`, `hub_source=GESTION_ACTIONS_I9_H1`, `return_mode=OUTBOX`. Scopes : `PIP_RUN`, `PIP_RESUME`, `PIP_STATUS`, `PIP_RESULT_READ`.

## 2. Enveloppe événement signée cible
```json
{
  "event_id": "identifiant-stable-emetteur",
  "event_type": "CONTACT_EMAIL_VERIFIED | CONTACT_UPDATED | CALLBACK_REQUESTED | CONSULTE | EN_COURS | TERMINE | ERREUR",
  "timestamp": "ISO-8601 UTC",
  "payload": {},
  "signature": "sha256=<HMAC-SHA256 hex du JSON canonique sans signature>"
}
```
La même clé HMAC PIP existante est utilisée ; aucun secret n’est placé dans l’URL ou les logs.

## 3. PUBLIC
`CONTACT_EMAIL_VERIFIED` et `CONTACT_UPDATED` transportent uniquement les données CRM nécessaires : prénom, nom, e-mail, téléphone, fonction, entreprise, consentement marketing, version RGPD, centres d’intérêt et horodatage de vérification. `PIP-RIASEC` est ajouté côté CRM sans écraser l’existant.

`CALLBACK_REQUESTED` transporte l’e-mail et l’horodatage de la demande. Aucun résultat, score, code Holland, réponse, rapport, pseudonyme ou identifiant d’étude n’est accepté.

## 4. ACCOMPAGNEMENT
Le format E1 existant `CONSULTE / EN_COURS / TERMINE` est conservé. `TERMINE` peut contenir `result_summary`. Gestion des Actions normalise et rejette récursivement les réponses brutes et données interdites. Les événements E1 historiques sans `event_id` restent rejouables via une empreinte déterministe pour compatibilité.

## 5. Rapports
Le système documentaire existant accepte un `PIP_REPORT` et, si O*NET est réalisé et transmis séparément par le PIP E1, un `ONET_REPORT`. Chaque type est unique par prescription et dédupliqué par SHA-256. Le transport de bytes/référence sécurisée doit être assuré par le chantier PIP ; Gestion des Actions ne dépend jamais d’un clic du bénéficiaire.

## 6. Étude PUBLIC
Gestion des Actions lit uniquement le dataset pseudonymisé sous `<PERSISTENT_DATA_DIR>/public/study`. Le CRM ne contient aucune clé permettant de relier ce dataset à une identité.

## 7. Écart PIP E1 encore externe à ce chantier
La version PIP E1 auditée écrit déjà les événements ACCOMPAGNEMENT dans `connector_outbox/gestion_actions_events.jsonl` et les études dans `public/study`. À cette date, son code PUBLIC conserve encore les leads localement et n’émet pas encore les trois événements CRM signés ci-dessus. Cette émission doit être réalisée dans le chantier PIP parallèle ; aucune modification du programme PIP n’est faite dans le présent chantier.
