# Rapport de tests - Jalon G - 18/09/2026

- Suite complète : **170 tests exécutés**
- Réussis : **170**
- Échecs : **0**
- Compilation Python des modules modifiés : OK

## Couverture ajoutée
- idempotence de l'outbox ;
- retry après indisponibilité Hub ;
- passage PENDING -> DELIVERED ;
- types PUBLIC CRM/rappel ;
- absence de scores/réponses dans le rappel ;
- émission TERMINE seulement après génération PDF ;
- intégrité/référence documentaire SHA-256 ;
- séparation dataset étude v2 / CRM ;
- pseudonymes d'étude indépendants ;
- signature HMAC serveur-à-serveur sans exposition du secret.

## Limites
Pas de test d'endpoint réel Gestion des Actions : conformément au CDC, ce fil ne modifie pas Gestion des Actions et aucun endpoint sortant définitif n'est inventé. Le mécanisme outbox/retry est testé localement.
