# Clarté360 – Outil 5 V1.1 opérationnelle

Application Streamlit pour l'analyse des compétences transférables et l'aide au choix du projet professionnel.

## Fonctionnalités V1.1

- Code d'accès obligatoire avec envoi email si SMTP configuré.
- Reprise possible par import d'une sauvegarde JSON.
- Chargement local du référentiel ROME XML.
- Table RIASEC Clarté360 intégrée.
- Recherche métier par code ROME, intitulé ou appellation.
- Shortlist de 1 à 3 métiers.
- Analyse compétence par compétence : Acquis / En cours d'acquisition / Non acquis / Non applicable.
- Justification obligatoire attendue pour Acquis et ECA : Quand ? Où ? Comment ?
- Plan d'acquisition attendu pour ECA et NA.
- Croisement avec valeurs, préférences, motivations, RIASEC, contraintes, mobilité, formation, marché.
- Aide à la décision optionnelle via indice Clarté360 non prescriptif.
- Choix final manuel du bénéficiaire avec confirmation du libre arbitre.
- Export JSON intermédiaire et final.
- Export PDF final.
- Envoi du dossier final à contact@clarte360.com si SMTP configuré.
- Journal de sessions début / clôture.

## Déploiement Streamlit Cloud

1. Déposer le contenu du dossier dans GitHub.
2. Pointer Streamlit Cloud sur `app.py`.
3. Ajouter les secrets SMTP si l'envoi email doit être actif.

## Secrets Streamlit recommandés

```toml
SMTP_HOST = "ssl0.ovh.net"
SMTP_PORT = "587"
SMTP_USER = "contact@clarte360.com"
SMTP_PASSWORD = "mot_de_passe_ovh"
SMTP_FROM = "contact@clarte360.com"
ADMIN_EMAIL = "contact@clarte360.com"
MASTER_CODE = "code_admin_de_secours"
```

Sans SMTP, l'application fonctionne en mode test : le code s'affiche à l'écran et les exports sont téléchargeables.

## Fichiers de données nécessaires

- `data/RefRomeXml.zip`
- `data/rome_riasec_clarte360.xlsx`
- `data/site_icon.png`
