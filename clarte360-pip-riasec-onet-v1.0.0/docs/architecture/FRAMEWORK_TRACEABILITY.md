# Tracabilite Framework Clarte360 V4

| Exigence Framework | Implementation L1-A |
|---|---|
| FW-101/102 initialisation Streamlit | `app.py`, `.streamlit/config.toml` |
| FW-103 secrets | `clarte360_pip/framework/config.py`, `.streamlit/secrets.example.toml` |
| FW-104 organisation dossiers | arborescence racine Framework |
| FW-109 services | `clarte360_pip/framework/` avec responsabilites separees |
| FW-201/202/204 branding/CSS | `assets/site_icon.png`, `clarte360_pip/framework/branding.py` |
| FW-304 sidebar | `clarte360_pip/ui/sidebar.py` |
| FW-305 navigation | `clarte360_pip/framework/navigation.py` |
| FW-310 RGPD | `clarte360_pip/framework/rgpd.py` |
| FW-311 Contact | `clarte360_pip/framework/contact.py` |
| FW-401 session state | `clarte360_pip/framework/session.py` |
| FW-406 timeout | `clarte360_pip/framework/timeout.py` |
| FW-601 JSON | `clarte360_pip/framework/persistence.py` + schema v0 |
| FW-801 SMTP | `clarte360_pip/framework/smtp.py` |
| FW-906 VPS Linux | pathlib, aucun chemin Windows, README de deploiement futur |
| FW-912 versionnement | `clarte360_pip/version.py`, `CHANGELOG.md` |


## Extension VPS obligatoire à partir de v1.0.1
Le FRAMEWORK VPS CLARTÉ360 V1.0 complète désormais ce socle pour tout déploiement VPS. Voir `docs/FRAMEWORK_VPS_COMPLIANCE.md` et `docs/deployment/VPS_DEPLOYMENT.md`.
