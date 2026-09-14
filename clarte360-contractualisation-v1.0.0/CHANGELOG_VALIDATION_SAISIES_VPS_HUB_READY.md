# CHANGELOG — 1.2.2 VALIDATION-SAISIES-VPS-HUB-READY

- Ajout d'une couche métier centralisée `validation.py`.
- Ajout du contrat technique `hub_contract.py` réservé aux rôles administrateur.
- Ajout de l'identité applicative et de l'URL de production existante.
- Ajout de tests automatisés validation + Hub.
- Ajout de la documentation VPS/Hub et d'un exemple systemd non installé.
- Aucun changement du mécanisme XLSM lecture seule, de la macro locale, des modèles juridiques ou du moteur PDF.


## Correctif 1.2.2 — rôle Hub
- Accès Hub Contractualisation limité strictement au rôle `admin`.
- Suppression du rôle `intervenant` du contrat Hub, de l’identité applicative et de la documentation.
- Aucun accès bénéficiaire.
