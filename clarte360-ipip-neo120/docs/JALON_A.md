# CLARTE360 IPIP-NEO-120 — JALON A

## Objet
Socle technique uniquement. Aucun scoring, rapport ou interprétation active dans l'interface à ce jalon.

## Référence
- CDC: `CDC_CLARTE360_IPIP_NEO120_V1_4.docx`
- Framework technique de référence: PIP RIASEC / O*NET Clarté360 V1.0.10 ACCOMPAGNEMENT.
- Référentiel questionnaire: `REFERENTIEL_MAITRE_IPIP_NEO120_FR_V1_0.json`.
- Référentiel interprétation: `REFERENTIEL_INTERPRETATION_CLARTE360_IPIP_NEO120_V1_0.json`.

## Identité VPS réservée
- tool_id: `ipip-neo120`
- URL: `https://ipip-neo120.clarte360.com`
- port interne: `8515`
- service: `clarte360-ipip-neo120.service`
- dossier stable: `/opt/clarte360/clarte360-outils/clarte360-ipip-neo120/`
- données: `/var/lib/clarte360/ipip-neo120/`

## Garde-fou déploiement
Le jalon A ne modifie pas le VPS. Avant toute installation, vérifier le registre VPS en vigueur, `ss -lntp`, Nginx, systemd, app_identity/tool_registry, le lien vers les secrets centraux et la persistance. Aucun correctif définitif ne doit exister uniquement sur le VPS.
