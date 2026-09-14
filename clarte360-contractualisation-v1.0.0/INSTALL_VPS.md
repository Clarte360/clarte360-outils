# Installation VPS – Clarté360 Contractualisation

Le programme est installé sur le VPS. **Aucune base Excel persistante n'est à déposer sur le VPS.**

Dossier cible recommandé :
`/opt/clarte360/clarte360-outils/clarte360-contractualisation-v1.0.0`

La seule configuration obligatoire dans les secrets est le mot de passe administrateur :

```toml
[security]
admin_password = "..."
```

Les anciennes clés `[contractualisation].db_path`, `backup_dir` et `documents_dir` ne sont pas utilisées par cette version.

La base `.xlsm` est chargée depuis le navigateur à chaque session et traitée en mémoire. Le fichier mis à jour est ensuite téléchargé vers le poste de l'administrateur.

## Complément 1.2.1 — Validation / Hub Ready

L'application est déjà publiée à `https://contractualisation.clarte360.com`; ce livrable ne déploie rien.

Configuration Hub future, uniquement si le lancement depuis Gestion des Actions est activé :

```toml
[hub]
hmac_secret = "CHANGE_ME_ON_VPS_ONLY"
```

Ce secret ne doit jamais être versionné. Contractualisation reste un outil de gestion interne : seul le rôle `admin` peut être autorisé depuis le Hub. Le bénéficiaire est uniquement le sujet du dossier et ne reçoit jamais d'accès à cette application.

Le service exemple est fourni dans `deploy/clarte360-contractualisation.service.example`. Le port 8502 y est une proposition documentaire à vérifier contre la cartographie VPS avant installation.
