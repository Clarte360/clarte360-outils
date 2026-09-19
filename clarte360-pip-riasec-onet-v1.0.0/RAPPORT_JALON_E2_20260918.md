# CLARTÉ360 — PIP RIASEC / O*NET — Jalon E2
Date : 18/09/2026
Base : Jalon E1

## Objet
Enrichir les rapports sans IA à l'exécution : interprétation déterministe du PIP et sécurisation de la présentation O*NET.

## PIP
- Rapport `PIP-RPT-1.2`.
- Nouveau moteur `clarte360_pip/interpretation.py`.
- Lecture combinée : niveau absolu, rang, écart entre les premières dimensions, amplitude globale et relief du profil.
- Cas explicitement gérés : première dimension basse (ex. 31), double pôle élevé et proche (ex. 93/87), dominante élevée nettement détachée (ex. 93/52), profils homogènes ou contrastés.
- Les niveaux sont des repères descriptifs Clarté360 ancrés dans l'échelle PIP 1–5 transformée en 0–100 ; ils ne sont ni des normes de population, ni des seuils d'aptitude.
- Aucun appel IA n'est requis pour produire l'interprétation.

## O*NET
- Rapport `ONET-RPT-1.1` autonome.
- Les 60 activités restent en anglais et sont chargées depuis O*NET Web Services, sans traduction ni reformulation Clarté360.
- L'écran d'introduction explique pourquoi la passation reste en anglais.
- Le rapport est en français pour l'accompagnement, mais distingue explicitement :
  1. les résultats/données officiels O*NET conservés sans conversion ;
  2. la lecture pédagogique en français rédigée par Clarté360.
- Pas de catégories PIP appliquées aux scores O*NET, pas de score composite, pas de fusion PIP/O*NET.
- Ajout d'une section « Source, droits et méthodologie » et de l'attribution O*NET Web Services / USDOL-ETA.

## Vérification juridique/documentaire
Sources officielles vérifiées le 18/09/2026 :
- https://services.onetcenter.org/help/license_data
- https://www.onetcenter.org/license_tools.html
- https://www.onetcenter.org/license_toolsdev.html
- https://www.onetcenter.org/IP.html

Le Data License autorise les titulaires d'un compte Web Services en règle à publier les données obtenues via API, avec attribution et sans altération des données. Les outils O*NET peuvent être reproduits sans modification sous CC BY-ND 4.0 ; les adaptations relèvent de la Developer License. E2 conserve donc volontairement les 60 items anglais sans traduction.

## Inchangé
- Banque PIP : `PIP-BANK-0.5`.
- Tableur maître : V0.6.
- Scoring PIP : `PIP-SCORE-0.5`.
- Séparation PUBLIC / ACCOMPAGNEMENT.
- O*NET et PIP restent deux instruments et deux rapports distincts.
- Pas d'intégration ROME dans E2 ; elle reste prévue au Jalon F.
