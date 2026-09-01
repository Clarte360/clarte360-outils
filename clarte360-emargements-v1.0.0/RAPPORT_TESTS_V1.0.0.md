# Rapport de tests — Clarté360 Émargements V1.0.0

## Contrôles réalisés dans l'environnement de fabrication

- Compilation Python de tous les modules : OK.
- Tests unitaires coeur base/actions/participants/créneaux/export JSON : 1/1 OK.
- Lecture réelle du fichier projet `GESTION OF CLARTE360 EN COURS.xlsm` : OK sur l'action CLA0001.
- Détection réelle de l'intitulé, de la durée, du client, du formateur, du lieu et du participant : OK.
- Non-import du NIR : conforme au choix V1.
- Génération PDF collectif : OK, fichier PDF valide.
- Génération PDF individuel : OK, fichier PDF valide.
- Génération certificat de réalisation : OK, fichier PDF valide.
- Génération des échéances INITIAL / RELANCE_1 / RELANCE_2 : OK.
- Génération des liens de signature individuels : OK.

## Contrôles à effectuer sur le VPS

Ces tests nécessitent le vrai environnement Streamlit et les paramètres d'exploitation :

- rendu visuel complet de l'application dans Edge/Chrome ;
- signature tactile sur smartphone ;
- envoi SMTP réel depuis l'adresse Clarté360 ;
- fonctionnement du worker systemd 24/7 ;
- sous-domaine HTTPS et QR code ;
- test de charge léger avec plusieurs signatures simultanées.

Ces contrôles sont prévus lors de l'installation sur le VPS. Ils ne peuvent pas être validés sans les identifiants SMTP, le nom de domaine et l'environnement serveur final.
