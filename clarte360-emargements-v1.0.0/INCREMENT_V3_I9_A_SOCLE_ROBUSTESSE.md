# CLARTÉ360 — Gestion des actions — I9-A

**Version : 3.0.0-I9-A**  
**Date : 12/09/2026**  
**Base : 3.0.0-I8 validée — `clarte360-gestion-actions-v3.0.0-I8-rebuild(1).zip`**

## Objet

Premier incrément I9 conforme au CDC I9 V2.0 : stabiliser le socle avant toute extension HUB.

## Modifications réalisées

### 1. Migration additive de session persistante
- Nouvelle table `auth_sessions` créée par `CREATE TABLE IF NOT EXISTS`.
- Aucun remplacement de table I8, aucune suppression de colonne, aucune migration destructive.
- Jeton navigateur aléatoire 256 bits ; seule son empreinte SHA-256 est stockée en base.
- Trois types de session séparés : `ADMIN`, `TRAINER`, `BENEFICIARY`.
- Expiration configurable (`[security].session_hours`, 12 h par défaut, bornée de 1 h à 30 jours).
- Révocation à la déconnexion et lors d'un changement/réinitialisation de mot de passe.
- Empreintes IP / user-agent optionnelles, jamais les valeurs brutes dans `auth_sessions`.

### 2. Reprise après rafraîchissement navigateur
- Cookie opaque distinct par profil : administrateur, intervenant, bénéficiaire.
- Cookie `SameSite=Strict`, `Secure` automatiquement en HTTPS.
- Aucun jeton de session ajouté à l'URL.
- À un nouveau chargement, la session est restaurée depuis le jeton serveur si celui-ci est valide et si l'identité est toujours active.

> La validation réelle F5 sur navigateur/VPS est volontairement reportée à la recette finale conformément à la décision du propriétaire du projet. La logique serveur et la migration sont couvertes par tests automatisés.

### 3. Correctif ReportLab `wrapOn`
- `_sig_image()` ne renvoie plus une chaîne vide lorsqu'une image de signature est absente.
- Le remplacement par un `Spacer` ReportLab garantit que les listes de Flowables placées dans les cellules de tableau ne contiennent plus de `str` susceptible de provoquer `AttributeError: 'str' object has no attribute 'wrapOn'`.
- Test de régression ajouté sur le PDF individuel avec contresignature sans image exploitable.

### 4. Robustesse / isolation des erreurs UI
- Nouveau module `ui_guard.py`.
- Journalisation des exceptions avec référence d'incident, contexte, type d'exception, message technique et traceback dans `audit_log`.
- Le message utilisateur reste métier et n'expose pas le traceback.
- Les principales pages administration ainsi que les routes publiques sont entourées d'un garde d'exécution ; une panne locale affiche un message métier au lieu d'une erreur Python brute.
- Les erreurs PDF visibles dans le portail bénéficiaire et dans l'administration ont été remplacées par des messages non techniques avec référence d'incident.
- Les erreurs d'envoi SMTP ne retombent plus sur le texte brut de l'exception dans l'interface.

## Fichiers principaux modifiés

- `app.py`
- `db.py`
- `pdf_utils.py`
- `branding.py`
- `tests/test_v2_candidate.py` (assertion de version uniquement)

## Nouveaux fichiers

- `persistent_session.py`
- `ui_guard.py`
- `tests/test_v3_i9a_foundation.py`
- `INCREMENT_V3_I9_A_SOCLE_ROBUSTESSE.md`
- `RAPPORT_TESTS_V3_I9_A.md`

## Non inclus dans I9-A

Restent volontairement pour les lots suivants :
- nouvelle règle de contresignature anticipée (I9-B) ;
- modalités contrôlées, import dates Excel et journal email (I9-B) ;
- UX Teams/Entra et présence Teams (I9-C) ;
- Hub/catalogue/prescriptions (I9-D et suivants).

## Compatibilité

- Le dossier de production reste `clarte360-emargements-v1.0.0`.
- Aucun secret n'est ajouté au code.
- Aucun fichier de données de production n'est inclus.
- Aucune modification VPS n'a été réalisée.
