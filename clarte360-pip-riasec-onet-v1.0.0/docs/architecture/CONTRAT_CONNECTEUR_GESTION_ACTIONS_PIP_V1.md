# Contrat connecteur Gestion des actions -> PIP RIASEC — V1

## Objectif
Permettre à Gestion des actions d'ouvrir le PIP en mode `ACCOMPAGNEMENT` sans créer de compte PIP ni exposer des identifiants libres dans l'URL.

## Point d'entrée
`https://pip-riasec.clarte360.com/?mode=accompagnement&launch=<JETON>`

## Jeton
Format compact :
`base64url(JSON canonique).base64url(HMAC-SHA256(payload_part, LAUNCH_SIGNING_KEY))`

Champs obligatoires :
- `v` : version du contrat, actuellement `1` ;
- `iat` : epoch UTC de création ;
- `exp` : epoch UTC d'expiration ;
- `beneficiary_id` ;
- `action_id` ;
- `prescription_id`.

Champs optionnels :
- `participant_id` ;
- `rights` : liste de droits techniques, par exemple `PIP_RUN`.

Durée maximale acceptée par le PIP : 7 jours. Une durée plus courte est recommandée pour un lien de lancement.

## Secret
La clé réelle est commune aux deux applications et doit exister uniquement dans les secrets VPS :

```toml
[PIP_CONNECTOR]
LAUNCH_SIGNING_KEY = "<secret réel hors Git>"
```

Aucune clé n'est stockée dans GitHub, ZIP, test, log ou URL.

## Persistance côté PIP
Une passation accompagnée est sauvegardée automatiquement sous le `data/` persistant du PIP. Un index par `prescription_id` permet une reprise automatique de la dernière passation correspondant strictement au même bénéficiaire et à la même action.

## Événements
Le PIP écrit une outbox locale minimisée avec :
- `CONSULTE` ;
- `EN_COURS` ;
- `TERMINE`.

Le transport vers Gestion des actions reste à brancher dans l'incrément Gestion des actions dédié. Tant que ce transport n'existe pas, l'outbox conserve les événements sans couplage direct entre bases.

## Règles de sécurité
- PUBLIC refuse tout identifiant Clarté360 dans l'URL.
- ACCOMPAGNEMENT refuse les identifiants libres et exige un jeton valide.
- Signature invalide, jeton expiré ou IDs non conformes : accès refusé.
- Aucun compte/mot de passe PIP autonome.
