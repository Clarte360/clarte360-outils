# RAPPORT TESTS — INTERVENANTS J2.1 — 20/09/2026

## Objet
Ajout du suivi structuré NDA et certification Qualiopi dans le dossier professionnel 360°.

## Contrôles réalisés
- compilation Python de `db.py`, `services.py`, `app.py` ;
- tests historiques complets et tests Intervenants J0/J1R/J2 ;
- 3 tests nouveaux J2.1 : NDA structuré, obligation du numéro si NDA=Oui, périmètre Qualiopi obligatoire si Qualiopi=Oui + catégorie documentaire certificat.

## Résultat
**376 tests réussis — 0 échec — 0 régression.**

## Règles métier couvertes
- NDA distinct de la qualification Clarté360 ;
- Qualiopi distinct de la qualification Clarté360 ;
- périmètre Qualiopi détaillé par catégorie d’actions ;
- justificatifs NDA / certificat Qualiopi stockables dans le dossier professionnel ;
- distinction `PERSONAL_ACTIVITY` / `SUPPLIER_PROJECTION` afin de préparer la frontière avec Gestion Clients.
