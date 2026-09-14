# PIP RIASEC / O*NET — Audit validation des saisies

Version auditée/corrigée : **1.0.8-l1-vps-hub-ready**  
Source : RC5 1.0.7-l1-vps  
Objectif : renforcer les entrées sans modifier questionnaire, banque, scoring, O*NET, parcours ni restitution.

## Entrées contrôlées

| Entrée | Source | Validation appliquée | Persistance/usage |
|---|---|---|---|
| Prénom / nom | PUBLIC | Unicode légitime, accents, apostrophes/tirets/espaces autorisés, chiffres/emoji/contrôles refusés, 100 car. max | lead public, e-mail code |
| Téléphone | PUBLIC | formats internationaux usuels, 7–15 chiffres, caractères usuels seulement, `+` uniquement en tête | lead public |
| E-mail | PUBLIC | adresse unique, longueur 254, CR/LF et multi-adresses refusés | lead public + SMTP |
| Fonction / entreprise | PUBLIC | texte court normalisé, 200 car., contrôles/CR-LF refusés | lead public |
| Autre intérêt | PUBLIC | texte libre limité 500 car., contrôles refusés | lead public |
| Code d’accès | PUBLIC | exactement 6 chiffres, expiration + limite d’essais conservées | session volatile |
| Réponses PIP | UI + reprise JSON | entier 1..5 ; reprise limitée à 120 réponses | snapshot / étude |
| Réponses O*NET | UI + reprise JSON | entier 1..5 ; identifiants 1..60 ; reprise limitée à 60 réponses | snapshot / étude |
| JSON de reprise | upload | UTF-8, objet JSON, 2 Mo max, schéma, IDs, parcours, structures et bornes | session |
| Paramètres URL | entrée | `PUBLIC` interdit tout ID dossier ; `ACCOMPAGNEMENT` n’accepte que `launch` signé | lancement |
| Jeton Hub | URL signée | HMAC, taille, iat/exp, durée max 7 j, IDs sûrs, scopes autorisés, tool_id et source Hub | contexte accompagné |
| IDs Hub | token + stockage | caractères sûrs, 160 max, traversal refusé | chemins / outbox |
| Événements outbox | service | type fermé, payload dict borné, IDs revalidés | JSONL persistant |
| URL applicative | config | HTTPS uniquement, pas de credentials | identité applicative |

## Non-survalidation

Sont explicitement acceptés : `O'Connor`, `Jean-Pierre`, `Élodie`, `Łukasz`, noms composés et numéros internationaux usuels.

## Hors périmètre inchangé

- banque PIP 120 items ;
- algorithme/scoring RIASEC ;
- calcul Holland ;
- contenu et ordre des questionnaires ;
- API/scoring O*NET ;
- consentements RGPD ;
- logique anti-influence PIP/O*NET.
