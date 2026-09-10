# Conformité FRAMEWORK VPS CLARTÉ360 V1.0

Version auditée: L1-D 1.0.0-l1. Version corrigée: 1.0.1-l1-vps.

Corrections structurantes:
- dossier de production stable renommé `clarte360-pip-riasec-onet-v1.0.0` ;
- ressources métier versionnées déplacées de `data/` vers `resources/` pour rester compatibles avec le `.gitignore` racine qui ignore `**/data/` ;
- `data/` réservé aux données persistantes locales hors Git ;
- temporaire déplacé par défaut sous `/tmp/clarte360-pip-riasec-onet` ;
- `.gitignore` applicatif aligné avec les protections du monorepo ;
- exemple de secrets neutralisé ;
- configuration Streamlit liée à `127.0.0.1` ;
- documentation du `.venv`, du lien vers les secrets centraux, du cycle GitHub -> VPS -> tests -> compilation -> restart et du service systemd ;
- tests techniques supplémentaires de conformité VPS.

Aucune règle métier PIP, RIASEC, O*NET, scoring, parcours ou ergonomie fonctionnelle n'a été modifiée.
