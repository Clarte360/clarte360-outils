# Rapport de tests — Roue des valeurs V2.8.1

- Tests automatisés présents dans la V2.7 source : **0**.
- Tests automatisés V2.8 : **45**.
- Tests automatisés V2.8.1 : **50**.
- Résultat final : **50 passed**.
- Compilation : `app.py`, `validation.py`, `hub_contract.py`, `guard_state.py` OK.
- Contrôles couverts : noms internationaux, e-mails, téléphones, textes dangereux, cotes/limites, 5 domaines, règle cote >2 avec preuve, JSON invalide/surdimensionné, compatibilité JSON V2.7 conforme, valeurs énergies, identifiants et jetons HMAC Hub, rôles, scopes et expiration.
- Garde-fou : empreinte stable de l'état métier, modification après sauvegarde, absence de faux positif sur timestamps/traces techniques, modification bénéficiaire et Valeurs énergies.
