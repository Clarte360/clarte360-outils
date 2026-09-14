# Rapport de tests — Contractualisation 1.2.2

- Tests automatisés existants dans l'archive source : **0**.
- Tests ajoutés : **16**.
- Résultat final : **16 passed**.
- Compilation : `app.py`, `contracts.py`, `session_export.py`, `xlsm_safe.py`, `validation.py`, `hub_contract.py` compilés sans erreur.

Couverture ajoutée : noms réels/incohérents, e-mails et CR/LF, téléphones internationaux, NO_CLAR/traversal, dates de naissance, chronologie contrat/action, horaires, montants/NaN/infini/bornes, injection de formule Excel, financements équilibrés et types autorisés, APS JSON, noms de fichiers, rôles Hub, HMAC, expiration, statuts Hub.

Réserve de recette réelle : le fonctionnement avec la vraie base `.xlsm`, la macro locale et le reverse proxy VPS n'a pas été exécuté dans cet environnement. Le mécanisme source XLSM reste inchangé et doit être vérifié en recette avec une copie de la base réelle avant déploiement.
