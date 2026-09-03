# Clarté360 Émargements & Qualité — V2.1.0

Correctif prioritaire issu de la recette du 03/09/2026.

## Fonctionnement métier

- Une action créée/importée reste `BROUILLON` : le worker n'envoie aucun email automatique d'émargement.
- Bouton explicite `VALIDER LE PLANNING ET ACTIVER L'ACTION`.
- L'activation contrôle participant(s), créneau(x) d'émargement et emails nécessaires.
- Une action `ACTIVE` reste modifiable. Les modifications de créneaux recalculent les échéances encore `PENDING`.
- Lors de l'activation, un email `Confirmation de votre planning` est envoyé à chaque participant avec tous les créneaux classés chronologiquement.
- Possibilité de renvoyer ensuite le planning actualisé depuis une action active.

## Email

- Priorité au secret `[MAIL]` existant Clarté360.
- Compatibilité maintenue avec `[mail]` puis l'ancien `[smtp]`.
- Plusieurs alias de clés sont acceptés (`host/server/smtp_server`, etc.).
- Les anciens `last_error` des événements `PENDING` sont effacés lorsqu'une échéance est recalculée.
- L'interface affiche une traduction plus lisible des principales erreurs email.
- Le worker d'émargement ne traite que les actions `ACTIVE` / `A_CLOTURER`.
- Les campagnes qualité sont bloquées pour `BROUILLON` / `PLANIFIEE`.

## Calendrier

- Affichage métier `Séance 1`, `Séance 2`, etc. au lieu des IDs SQLite.
- Zone `Ajouter une nouvelle séance` mise en avant avant la modification.
- Envoi initial paramétrable par libellé métier ; `Au début du créneau` calcule automatiquement le décalage selon la durée.
- Modification d'une séance déplacée dans un bloc explicite avec avertissement.
- Duplication : la date la plus récente est proposée comme source ; après duplication, la nouvelle date devient de fait la dernière source.
- La date cible proposée est J+7 par rapport à la source.

## Tests

- Suite historique : 35 tests conservés.
- 4 tests V2.1 ajoutés : priorité MAIL, validation email participant, activation/modifiabilité ACTIVE, nettoyage des anciens `last_error` PENDING.
- Total : 39 tests réussis.

## Déploiement

Le chemin historique reste impérativement :
`/opt/clarte360/clarte360-outils/clarte360-emargements-v1.0.0`

Aucun secret réel, aucune base de production et aucune signature ne sont inclus dans le ZIP.
