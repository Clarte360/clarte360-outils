## Jalon E - 2026-09-18
- Rapport PDF professionnel Clarté360 PIP-RPT-1.0.
- Restitution PIP : classement, graphique, code Holland non forcé, descriptions dominantes et limites.
- Restitution O*NET séparée et comparaison descriptive des rangs si passation effectuée.
- Ressenti séparé du scoring.
- Téléchargement PDF final PUBLIC et ACCOMPAGNEMENT.
- Génération locale déterministe sans dépendance réseau.

## Jalon A1 — 18/09/2026
- Tableur maître actif porté en V0.6 avec trois onglets de travail visibles : `01_QUESTIONS_72`, `02_REPONSES_CONSIGNE`, `03_REVUE_HISTORIQUE`.
- Les onglets historiques et techniques sont conservés mais masqués par défaut.
- Les 72 items restent équilibrés : 12 par dimension R/I/A/S/E/C et 30 facettes couvertes.
- Formulations finales centrées sur l’intérêt pour une activité professionnelle, indépendamment du métier actuel et de la compétence perçue.
- Échelle PIP harmonisée : de « Je n’aimerais pas du tout faire cela » à « J’aimerais beaucoup faire cela ».
- Nouvelle banque `PIP-BANK-0.5`, `item_version=0.6`.
- Le tableur maître devient la source métier contrôlée ; `scripts/build_pip_runtime.py` génère le JSON runtime et `--check` détecte tout écart tableur/JSON.
- Aucun changement de formule de scoring.
- 121 tests automatisés réussis.

## Jalon A — 18/09/2026
- Banque PIP portée de 120 à 72 items (12 par dimension).
- 30 facettes conservées, au moins 2 items par facette.
- Questions concrétisées à partir de la revue de contextualisation V0.4 ; suppression des exemples séparés du runtime.
- Tableur maître V0.5 ajouté ; historique 120 conservé.
- Scoring inchangé.

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


## Jalon B — RGPD / navigation / sauvegarde / reprise / timeout — 2026-09-18
- Consentement RGPD reconnu par version de texte : une validation déjà enregistrée n'est plus redemandée tant que la version RGPD n'a pas changé.
- Parcours PUBLIC réordonné : information RGPD avant la saisie d'identité et la vérification e-mail.
- Consultation des pages Accueil et RGPD sans remise à zéro d'une passation existante.
- Conservation et restauration explicites de `rgpd_acceptance`, `study_consent`, du choix de parcours et du timing O*NET.
- Reprise protégée : une passation PIP déjà commencée n'est plus réinitialisée par le bouton de démarrage ; le parcours reprend au bon écran utile.
- Sauvegardes manuelles et sauvegardes timeout utilisent désormais la même logique de destination de reprise.
- Un snapshot créé sur l'écran timeout ne contient jamais `navigation_page=timeout` comme cible de reprise ; les anciens snapshots timeout sont réparés à l'import.
- Réinitialisation de l'horloge d'inactivité lors d'une restauration JSON.
- Message et bouton timeout alignés sur le CDC, avec rappel qu'un seul téléchargement suffit.
- Import + reprise JSON disponible également depuis l'écran timeout.
- Compatibilité de chargement préparée par `bank_version` afin de ne pas imposer une réinitialisation lorsqu'une banque runtime correspondante est disponible.
- Aucun changement du scoring RIASEC/Holland, de la banque active 72 items ni d'O*NET.

## Jalon C — séparation PUBLIC / ACCOMPAGNEMENT — 2026-09-18
- Le PIP sait désormais consommer quatre données d’affichage signées distinctes des identifiants techniques : prénom, nom, numéro d’action lisible et intitulé de l’action ; pendant la transition avec Gestion des Actions, leur absence reste rétrocompatible et déclenche des libellés neutres sans exposition d’ID.
- L’écran bénéficiaire n’affiche plus `beneficiary_id` ni `action_id` ; il affiche uniquement le nom lisible du bénéficiaire et le libellé lisible de l’action.
- Les identifiants techniques restent disponibles côté serveur pour sauvegarde, reprise et contrats Gestion des Actions, sans exposition à l’utilisateur.
- Suppression complète de la question « Souhaitez-vous approfondir certains éléments avec votre accompagnateur ? ».
- Le questionnaire de ressenti devient strictement neutre entre PUBLIC et ACCOMPAGNEMENT ; le mode est tracé dans l’enregistrement du ressenti.
- Aucun mécanisme marketing/public n’est ajouté au parcours ACCOMPAGNEMENT.
- Aucun changement du scoring RIASEC/Holland, de la banque active 72 items, du tableur maître V0.6, d’O*NET, du timeout ou de la reprise du Jalon B.


## Jalon D — 18/09/2026
- Consolidation de l'intégration officielle O*NET Interest Profiler Short Form 60 via Web Services API v2.
- Validation stricte des 60 réponses 1–5 et envoi dans l'ordre officiel.
- Résultats O*NET conservés sur leur échelle officielle et présentés par score décroissant.
- Comparaison PIP/O*NET explicitement descriptive : aucun recalcul, aucune fusion, aucune moyenne des scores.
- Chronologie PRE_PIP / POST_PIP_RESULTS conservée dans l'état O*NET.
- Banque PIP, scoring PIP et tableur maître inchangés.

## 2026-09-18 - Jalon E1
- Séparation stricte des rapports PIP Clarté360 et O*NET.
- Rapport PIP PIP-RPT-1.1 : explication autonome RIASEC/PIP, hexagone-radar, lecture des 6 dimensions, 30 facettes Clarté360 avec indicateurs descriptifs et précautions, usage en accompagnement.
- Rapport O*NET ONET-RPT-1.0 autonome ; scores O*NET conservés sans conversion ni fusion avec PIP.
- Si les deux outils sont réalisés, deux téléchargements PDF distincts.

## Jalon E2 — interprétation PIP et rapport O*NET conforme (2026-09-18)
- PIP : ajout d'un moteur déterministe d'interprétation en français, sans IA à l'exécution.
- Lecture combinée du niveau absolu, du rang, des écarts et du relief du profil ; distinction explicite entre une première dimension basse et une dominante très élevée.
- Les seuils PIP sont des repères descriptifs Clarté360 ancrés dans l'échelle de réponse, jamais des normes de population ni des seuils d'aptitude.
- O*NET : passation maintenue sur les 60 activités anglaises fournies par O*NET Web Services, sans traduction ni reformulation.
- Rapport O*NET autonome en français : résultats officiels conservés sans conversion ; commentaires français explicitement identifiés comme lecture Clarté360.
- Ajout d'une section Source, droits et méthodologie et de l'attribution O*NET Web Services / USDOL-ETA.

## Jalon E3 — 18/09/2026
- Création du référentiel méthodologique autonome `REFERENTIEL_INTERPRETATION_PIP_RIASEC_CLARTE360_V1_0.xlsx`.
- Les seuils, règles de relief, écarts de tête, scénarios de synthèse, garde-fous et cas de recette ne sont plus enfermés dans `interpretation.py`.
- Nouveau runtime versionné `PIP-INT-1.0`, généré depuis le tableur par `scripts/build_interpretation_runtime.py`.
- Le moteur d'interprétation lit ce runtime ; toute modification du tableur doit régénérer le JSON et passer les tests de synchronisation.
- Rapport PIP : `PIP-RPT-1.3`. O*NET reste `ONET-RPT-1.1` et séparé de ces règles.

## Jalon F — 18/09/2026
- Activation du connecteur ROME/RIASEC à partir du référentiel projet daté juin 2026.
- Ajout du runtime versionné `ROME-RIASEC-2026-06` généré depuis le tableur source.
- Ajout des pistes ROME dans le rapport PIP, sur profil RIASEC à deux lettres non ambigu.
- Sélection limitée, déterministe et diversifiée ; aucun score de compatibilité ni recommandation automatique.
- Rapport PIP : `PIP-RPT-1.4`.

## Jalon G - 18/09/2026
- Contrat sortant Gestion des Actions version `PIP-GA-OUTBOUND-1.0`.
- Outbox durable par événement avec idempotence de contenu, suivi des tentatives et retry sans perte.
- Préparation HMAC SHA-256 pour transport serveur-à-serveur, secret hors URL/payload/logs.
- PUBLIC : `CONTACT_EMAIL_VERIFIED` immédiatement après validation e-mail ; support `CONTACT_UPDATED` ; `CALLBACK_REQUESTED` sans résultats.
- PUBLIC : intérêt `PIP-RIASEC` systématiquement présent dans l'événement CRM.
- ACCOMPAGNEMENT : `TERMINE` déplacé après ressenti + génération/persistance des PDF.
- ACCOMPAGNEMENT : synthèse finale versions/scores/rangs/ressenti + références PDF ; aucune réponse brute.
- Étude PUBLIC v2 : pseudonyme aléatoire indépendant, suppression des clés `participant_id`/`passation_id` du dataset étude.
- 170 tests automatisés réussis.

## Jalon H - recette finale locale - 18/09/2026
- Recette finale consolidée à partir du Jalon G officiel OneDrive.
- Métadonnées de build : `JALON_ID=H`, `BUILD_INCREMENT=L1-H-RECETTE-FINALE`.
- Rapport PIP `PIP-RPT-1.5` : ajout des mentions finales distinctes PUBLIC / ACCOMPAGNEMENT prévues par le CDC.
- PUBLIC : rappel explicite qu'il s'agit d'un support d'exploration, ni diagnostic, ni prescription d'orientation, ni validation de compétences.
- ACCOMPAGNEMENT : insertion de la mention méthodologique obligatoire du CDC sur la mise en perspective du profil dans le processus Clarté360.
- 174 tests automatisés réussis ; synchronisation banque/interprétation/ROME et compilation contrôlées.
- Contrôle visuel final des PDF PIP PUBLIC, PIP ACCOMPAGNEMENT et O*NET.
- Aucun déploiement VPS effectué à ce stade : la recette VPS reste à exécuter après le push GitHub Desktop validé par l'utilisateur.

## H1 - 2026-09-18 - Différenciation rapport PUBLIC / ACCOMPAGNEMENT
- Rapport PUBLIC reconstruit en synthèse autonome de 5 pages.
- Rapport ACCOMPAGNEMENT complet conservé à 9 pages.
- PUBLIC : modèle RIASEC synthétique, profil global, interprétation niveau/relief, 3 dimensions principales, 6 facettes descriptives saillantes, 4 pistes ROME maximum et conclusion d'exploration.
- Suppression du PUBLIC des 30 facettes exhaustives et des formulations propres à l'accompagnement.
- Aucun changement du scoring, de la banque PIP, du référentiel d'interprétation, du moteur ROME ou du rapport O*NET.
- Rapport PIP : PIP-RPT-1.6. Build : L1-H1-RAPPORT-PUBLIC-SYNTHESE.

## H2 - 2026-09-19 - Ressenti après restitution
- Prévisualisation intégrée du rapport PIP avant le questionnaire de ressenti.
- Ouverture à partir de la page 3 et confirmation explicite de consultation avant poursuite.
- Aucun changement du rapport PUBLIC PIP-RPT-1.6, de la banque, du scoring, du ROME ou d'O*NET.

## H3 - 2026-09-19 - Correctif recette réelle PUBLIC / liaison Gestion des Actions
- Suppression de `participant_id` des événements CRM PUBLIC et ajout d'un garde-fou central récursif contre toute clé de jonction/recherche interdite.
- `CONTACT_EMAIL_VERIFIED`, `CONTACT_UPDATED` et `CALLBACK_REQUESTED` respectent désormais la séparation stricte CRM identifié / étude pseudonymisée.
- Dataset étude aligné sur le contrat réel Gestion : `schema=clarte360.pip.public-study.v1`, `study_id` aléatoire indépendant et non vide.
- Ajout d'un garde-fou récursif empêchant toute identité ou clé CRM/passation dans le dataset étude.
- Aucun dataset étude créé sans consentement recherche.
- Outbox active conservée : `data/connector_outbox/gestion_actions/events.jsonl`.
- Correction H2 rapport avant ressenti conservée sans modification.
- 190 tests réussis.

## H3.1 - 2026-09-19 - Reprise JSON PUBLIC / idempotence étude
- Base exclusive : H3.
- Persistance de `public_study_id` dans le JSON de sauvegarde PUBLIC.
- Restauration de `public_study_id` lors d'une reprise JSON.
- Le rechargement répété du même JSON H3.1 conserve le même `study_id` et réécrit le même fichier d'étude au lieu d'en créer plusieurs.
- Aucune migration rétroactive complexe des JSON H1/H2 : les bases d'essai seront vidées avant recette réelle.
- Séparation CRM / étude H3 inchangée ; aucun `study_id` exporté vers le CRM.
- Aucun changement banque 72 items, scoring, ROME, O*NET, rapports ou ACCOMPAGNEMENT.
