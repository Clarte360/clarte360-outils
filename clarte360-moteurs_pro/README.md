# Clarté360 - Moteurs professionnels

Application Streamlit propriétaire Clarté360 d'exploration des sources d'énergie professionnelle.

Version livrée : **v1.8.4-reprise-json-compatible-vps-hub**  
Socle Clarté360 : **1.8**

Cette version repart intégralement de la version V1.8.3 effectivement présente dans le dépôt GitHub et déployée sur le VPS. Elle conserve le questionnaire, les curseurs, le scoring et le rapport enrichi.

## Correctif V1.8.4

- correction de la reprise d'une session par JSON : l'écran d'import reçoit désormais explicitement le référentiel des curseurs actifs ;
- maintien de la compatibilité avec les JSON V1.8.0 issus de Streamlit Cloud ;
- un JSON valide portant la preuve d'un accès antérieur permet la reprise sans demander un nouveau code ;
- conservation de l'historique de sessions, des réponses, des résultats et du consentement RGPD ;
- ajout d'un test de non-régression dédié à la reprise JSON ;
- fichier `config/app_identity.json` conservé et mis à jour ;
- exemple systemd aligné sur le déploiement VPS réel (`ubuntu`, dossier `clarte360-moteurs_pro`, port 8506).

## Déploiement VPS

URL cible : `https://moteurs-professionnels.clarte360.com`  
Service : `clarte360-moteurs-professionnels.service`  
Port interne : `8506`

## Secrets

Les secrets ne sont jamais inclus dans le ZIP. Le VPS utilise le mécanisme centralisé Clarté360 via le lien `.streamlit/secrets.toml`.
