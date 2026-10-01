# Jalon G — Recette intégrée / RC1

Version : 0.7.0-rc1 — 20 septembre 2026
Références : CDC IPIP-NEO-120 V1.5 ; Framework Clarté360 V4.1+ ; Framework VPS V1.3+ ; PIP RIASEC/O*NET ACCOMPAGNEMENT comme référence technique.

## Objet

Le Jalon G ne crée plus de nouvelle fonction métier. Il transforme le Jalon F en **RC1** et vérifie le parcours complet, les verrouillages et la robustesse de la liaison Gestion des Actions.

## Parcours de recette couvert

1. Jeton Gestion valide -> création d'une unique passation liée à la prescription.
2. Publication CONSULTE.
3. Démarrage -> sauvegarde automatique serveur et EN_COURS.
4. Interruption simulée -> nouvelle session -> reprise de la même passation et des mêmes réponses.
5. Réponses 120/120 -> scoring 30 facettes + 5 domaines -> interprétation.
6. Ressenti final obligatoire et sans effet sur le scoring.
7. Génération PDF -> SHA-256 -> marqueur TERMINE -> événement TERMINE contenant la référence documentaire.
8. Reconnexion après TERMINE -> même passation, consultation seule.
9. Toute écriture serveur sur réponses, score ou ressenti après TERMINE est refusée.
10. Nouvelle passation uniquement avec une nouvelle prescription.

## Sécurité / robustesse vérifiées

- HMAC invalide, jeton expiré, tool_id incorrect et scopes insuffisants refusés.
- Anti-croisement beneficiary/action/participant/prescription.
- Aucun JSON de sauvegarde ou identifiant de reprise présenté au bénéficiaire.
- Outbox persistante et idempotente ; événement non perdu si le transport est indisponible.
- Rapport PDF contrôlé par type, taille et SHA-256.
- Les réponses brutes ne sont pas envoyées dans les événements Hub.
- Le verrou TERMINE est désormais appliqué au niveau des fonctions de persistance serveur, pas uniquement dans l'interface Streamlit.

## Limite de cette RC1

Cette recette automatisée reproduit le contrat Gestion <-> IPIP et les redémarrages de processus par rechargement depuis le stockage persistant. Le déploiement effectif sur le VPS, le vhost Nginx, le service systemd réel et l'import du PDF dans une instance de production Gestion des Actions doivent être vérifiés lors de la recette d'installation avant RCF.
