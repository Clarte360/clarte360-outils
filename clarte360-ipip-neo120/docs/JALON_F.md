# Jalon F — Liaison Gestion des Actions

Référence : CDC V1.5 et architecture PIP RIASEC/O*NET ACCOMPAGNEMENT.

- lancement uniquement par jeton HMAC signé ; aucun identifiant libre dans l'URL ;
- scopes IPIP dédiés : IPIP_RUN, IPIP_RESUME, IPIP_STATUS, IPIP_RESULT_READ ;
- index serveur par prescription_id, avec contrôle beneficiary/action/participant ;
- une prescription = une passation : EN_COURS reprend la même passation ; TERMINE reste verrouillée ;
- nouvelle passation uniquement via nouvelle prescription ;
- événements CONSULTE, EN_COURS, TERMINE, ERREUR dans une outbox durable/idempotente ;
- transport indépendant de Streamlit et tolérant à l'indisponibilité de Gestion ;
- rapport TERMINE référencé par report_id, MIME, taille et SHA-256 ;
- aucun secret, aucune réponse brute et aucun identifiant sensible inutile dans les URLs.

Le déploiement VPS et la recette réelle Gestion -> IPIP -> Gestion relèvent du Jalon G.
