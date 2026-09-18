# Changelog

## 1.0.5-l1-vps — RC3
- Corrige les tests de sécurité VPS afin qu'ils n'ouvrent jamais `.streamlit/secrets.toml` lorsqu'il s'agit du lien symbolique vers le coffre central `/opt/clarte360/secrets/secrets.toml`.
- Le contrôle continue d'inspecter tous les fichiers réellement versionnés du projet.
- Aucun changement fonctionnel, méthodologique, RIASEC, O*NET ou de scoring.
- Ajout d'un test de non-régression sur le comportement attendu avec un lien symbolique de secrets.

## 1.0.1-l1-vps — 2026-09-10
- Mise en conformité technique avec le FRAMEWORK VPS CLARTÉ360 V1.0.
- Aucun changement fonctionnel ou méthodologique PIP/RIASEC/O*NET.
- Dossier de production stable documenté: `clarte360-pip-riasec-onet-v1.0.0`.
- Ressources runtime versionnées déplacées de `data/` vers `resources/`.
- `data/` réservé aux données persistantes hors Git; temporaire par défaut sous `/tmp`.
- `.gitignore`, secrets d'exemple et configuration Streamlit renforcés.
- Documentation VPS/systemd et tests techniques de conformité ajoutés.


## 0.2.0-l1b — 2026-09-10
- Pipeline contrôlé tableur maître -> ressource runtime JSON versionnée.
- Intégration des 120 items pilotes sans réécriture.
- Validation automatique banque, IDs, dimensions, facettes, blocs et échelle.
- Moteur de questionnaire déterministe par session, mélange RIASEC dans les blocs.
- Interface de passation 1–5, navigation précédent/suivant, aucun feedback intermédiaire.
- Tests L1-B ajoutés.

## 0.1.0-l1a
- Socle et architecture initiale Clarté360.

## 0.3.0-l1c — L1-C
- Scoring déterministe RIASEC (moyennes, indices 0–100, égalités exactes, préparation code Holland).
- Complétude obligatoire avant résultat final.
- Sauvegarde/reprise métier schema `clarte360.pip.run.v1`.
- Parcours PIP seul / PIP puis O*NET 60 et verrou anti-influence.
- Structure versionnée du questionnaire fermé de ressenti.
- Tests L1-C scoring, parcours, persistance et non-régression.

## 1.0.0-l1 — L1-D — 2026-09-10
- Consolidation finale du Livrable 1 cumulatif A+B+C+D.
- Version applicative et libellés d'interface alignés sur L1-D.
- Audit banque runtime, parcours, verrou anti-influence, sauvegarde/reprise et absence de secrets.
- Ajout des tests de consolidation L1-D.
- Ajout de la checklist de recette utilisateur du Livrable 1.

## 1.0.3-l1-vps — 2026-09-10 — correctif recette réelle L1
- Branding Clarté360 visible avec logo officiel de l'application Gestion des actions.
- Sauvegarde JSON accessible pendant toute la passation et reprise depuis l'accueil.
- Fin de parcours PIP seul : restitution minimale des six indices, code Holland seulement si non ambigu, questionnaire fermé de ressenti, sauvegarde finale.
- Ajout d'un exemple concret séparé pour chacun des 120 items, issu du tableur maître V0.4 de contextualisation ; formulations source et scoring inchangés.
- Le mode accompagné reste préparé mais son authentification/prescription doit être fournie par le connecteur Gestion des actions ; aucun second compte PIP n'est créé.

## 1.0.4-l1-vps — 2026-09-10 — RC2 seconde partie
- Préparation réelle du mode ACCOMPAGNEMENT sans créer de compte PIP parallèle.
- Suppression du scaffold par identifiants URL libres : l'entrée accompagnée exige désormais un jeton HMAC signé et expirant.
- Ajout du contrat de jeton commun Gestion des actions ↔ PIP, sans dépendance externe.
- Ajout d'une persistance serveur atomique des passations accompagnées sous `data/accompanied_runs/`.
- Ajout d'une outbox locale d'événements minimisés `CONSULTE / EN_COURS / TERMINE`, prête pour le transport futur vers Gestion des actions.
- Le mode PUBLIC reste étanche et refuse tout identifiant Clarté360 injecté dans l'URL.
- Export JSON public renforcé : aucun scoring intermédiaire n'est exporté avant complétude du PIP.
- Sauvegarde JSON visible uniquement en PUBLIC ; en ACCOMPAGNEMENT la sauvegarde est automatique côté serveur.

## 1.0.6-l1-vps — RC4 Accès public professionnel
- Nouvelle landing page RIASEC orientée découverte et compréhension du résultat.
- Accès public avec identité complète et vérification e-mail par code temporaire.
- Consentement marketing facultatif et séparé du traitement nécessaire à la passation.
- Consentement étude PIP/O*NET séparé ; stockage de recherche pseudonymisé distinct des coordonnées.
- Préparation maintenue de l'accès bénéficiaire par prescription signée Gestion des actions (I9 à venir).
- Aucune modification des 120 formulations, exemples concrets, scoring ou verrou anti-influence O*NET.

## 1.0.7-l1-vps — RC5
- Branding Clarté360 permanent dans la barre latérale : logo compact + www.clarte360.com ; suppression du grand logo répété dans les écrans métier.
- Reprise JSON publique déplacée dans la barre latérale pour rester immédiatement visible.
- Accès public : seuls prénom, nom, téléphone et e-mail sont obligatoires ; fonction et entreprise deviennent facultatives.
- Ajout de centres d’intérêt facultatifs : bilan de compétences, coaching professionnel, formation individuelle sur mesure, solutions collectives entreprise, autre.
- Consentement marketing maintenu séparé et facultatif ; texte RGPD enrichi pour identité, intérêts, étude et O*NET.
- O*NET Interest Profiler 60 réellement intégré via O*NET Web Services API v2 (`X-API-Key`) : questions officielles anglaises, réponses 1–5, scoring officiel API.
- O*NET peut être choisi avant le PIP (verrou anti-influence conservé) ou après consultation du résultat PIP ; le timing `PRE_PIP` / `POST_PIP_RESULTS` est enregistré pour les études.
- Résultats PIP et O*NET restent séparés ; affichage côte à côte descriptif sans fusion ni prescription automatique.

## 1.0.8-l1-vps-hub-ready — VALIDATION-SAISIES-VPS-HUB-READY
- Ajout d’une couche centralisée de validation métier des entrées publiques, IDs, scores, URL, codes et fichiers JSON.
- Validation renforcée des noms, e-mails, téléphones et textes courts sans survalidation des noms internationaux légitimes.
- Import/reprise JSON limité à 2 Mo et contrôlé (schéma, types, bornes, IDs, parcours).
- Connecteur Gestion des Actions conservé et étendu de façon rétrocompatible aux champs communs I9-H1 `tool_id`, `hub_source`, `scopes` et `return_mode`.
- Validation des scopes et de la cible outil avant création du contexte accompagné.
- Outbox renforcée et événement `ERREUR` réservé.
- Ajout de `config/app_identity.json` avec URL Clarté360 et identité technique versionnée, sans secret.
- Documentation VPS/Hub et matrice de validation ajoutées.
- Aucune modification du questionnaire, de la banque PIP, du scoring RIASEC/Holland ni du fonctionnement O*NET.


## 1.0.9-l1-vps-hub-ready-guard — GARDE-FOU SORTIE / RAFRAÎCHISSEMENT
- Ajout d’un garde-fou navigateur `beforeunload` pour le parcours PUBLIC lorsqu’un travail a commencé et n’a pas été sauvegardé en JSON.
- Le garde-fou est levé après téléchargement du JSON correspondant à l’état courant puis se réactive automatiquement dès qu’une nouvelle réponse modifie le travail.
- Le mode ACCOMPAGNEMENT n’est pas soumis à ce garde-fou : sa progression reste sauvegardée automatiquement côté serveur.
- Ajout d’une sauvegarde JSON pendant la séquence O*NET publique et prise en compte immédiate de la réponse O*NET courante.
- Une reprise depuis un JSON conforme est considérée comme un état sauvegardé.
- Aucun changement du questionnaire PIP, du scoring RIASEC/Holland, des 120 items ou de l’algorithme O*NET.
## 1.0.10-l1-vps-hub-ready-guard-accompagnement — ACCOMPAGNEMENT / SYNTHÈSE RIASEC
- Base technique strictement issue de la 1.0.9 `GARDE-FOU SORTIE / RAFRAÎCHISSEMENT`.
- Conservation intégrale des validations de saisie, garde-fous navigateur, accès public, O*NET, sécurité Hub et persistance accompagnée de la 1.0.9.
- En mode ACCOMPAGNEMENT uniquement, l'événement `TERMINE` publié vers l'outbox Gestion des Actions contient désormais un `result_summary` minimal exploitable en séance : code Holland, indices RIASEC, ordre, égalités exactes et version d'algorithme.
- Les réponses item par item du PIP ne sont jamais publiées dans ce résumé.
- Si O*NET a été réalisé, son état terminé et ses résultats descriptifs sont ajoutés au résumé ; sinon la section reste absente.
- Aucun changement du questionnaire PIP, des 120 items, du scoring RIASEC/Holland, du mode PUBLIC ou du mécanisme de reprise serveur.

