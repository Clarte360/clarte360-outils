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
