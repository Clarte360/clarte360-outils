# Audit VPS — Livrable 1 v1.0.1

Conformité finale: OUI — FRAMEWORK CLARTÉ360 V4.0 + FRAMEWORK VPS CLARTÉ360 V1.0.

## Écarts constatés sur v1.0.0
1. Le dossier interne portait encore le suffixe d'incrément `l1a`, impropre comme dossier stable de production.
2. La banque runtime et le schéma applicatif étaient sous `data/`, alors que le `.gitignore` racine obligatoire ignore `**/data/`.
3. Les répertoires `reports/` et `temp/` étaient présents dans le livrable alors qu'ils relèvent de l'exécution locale.
4. Le `.gitignore` applicatif ne reprenait pas toutes les protections VPS transverses.
5. L'exemple de secrets contenait des paramètres SMTP concrets inutiles pour un exemple.
6. La configuration et la documentation ne formalisaient pas encore le dossier stable, le `.venv` propre, le lien vers les secrets centraux, la persistance hors Git et le service systemd.

## Corrections
- Dossier stable: `clarte360-pip-riasec-onet-v1.0.0`.
- Ressources versionnées: `resources/runtime/` et `resources/schemas/`.
- Données persistantes: `data/` hors Git, configurable par `CLARTE360_PIP_DATA_DIR`.
- Temporaire: `/tmp/clarte360-pip-riasec-onet` par défaut.
- Secrets: aucun secret réel; exemple neutralisé; `secrets.toml` reste hors Git.
- Streamlit: écoute locale `127.0.0.1`.
- Documentation: cycle GitHub -> VPS, tests, compilation, service systemd et retour arrière.
- Tests VPS supplémentaires ajoutés.

Aucun comportement métier PIP/RIASEC/O*NET n'a été changé.
