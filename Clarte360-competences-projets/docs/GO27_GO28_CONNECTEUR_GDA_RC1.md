# GO27–GO28 — Connecteur GDA CP_V1, état de construction

Date : 24 octobre 2026  
État historique de construction; état courant ajouté ci-dessous.  
État : client C&P, écrans de documents pour les trois parties prenantes, conservation des références sans binaire, liens manuels versionnés, remises PDF idempotentes et analyse CV après C‑AV3 ajoutés. Le patch de lancement et le service GDA sont préparés localement ; il reste à les installer dans la copie de travail GDA puis à exécuter les essais réels.

## Source maître et règles retenues

Gestion des Actions est la source de vérité pour les documents. C&P reçoit les octets à la demande, vérifie SHA-256 et taille en mémoire, puis ne conserve pas de binaire GDA dans son espace d'objets. Les documents déposés depuis C&P vont directement dans l'espace GDA, sans association à un besoin C&P. L'accompagnateur relie ensuite explicitement la référence à un besoin métier. Les noms de fichiers et le contenu ne servent jamais à inférer le type ou le besoin.

Le complément dans `integration/gda_patch/` comprend :

- `cp_launch.py` : lancement signé CP_V1 avec le rôle et l'identifiant de l'acteur connecté, sans identité civile dans le jeton ; affectation, bénéficiaire et prescription sont revérifiés au lancement.
- `cp_hub_api.py` : service HTTP local GDA, lié à `127.0.0.1:8765` par défaut, avec vérification du jeton, du contexte, des scopes, de l’état/échéance de prescription et des affectations GDA à chaque requête ; inventaire, lecture et dépôt de source non associée. La route `session/check` donne à C&P un contrôle live à chaque reprise d’écran.
- `clarte360_cp/connectors/gda_documents.py` : client C&P HTTPS, réponses bornées, erreurs lisibles, contrôle de taille et d'empreinte, et exclusion des rapports O*NET / PIP publics.

L'administrateur reçoit uniquement le scope `CP_SOURCE_ADMIN_PUT` par un jeton et un écran distincts `mode=upload_only`. Il peut déposer dans le dossier prescrit, mais ne peut ni ouvrir le cas C&P, ni lister ou lire les documents et les résultats individuels. Les scopes complets C&P restent réservés à l'accompagnateur affecté et au bénéficiaire du dossier.

## Contrat de transport codé

| Opération | Requête | Effet attendu |
|---|---|---|
| `POST /api/cp/v1/sources/list` | Jeton CP_V1, `tool_id` | Références publiées du seul bénéficiaire/action/prescription, sans octets |
| `POST /api/cp/v1/session/check` | Jeton CP_V1, `tool_id` | Revalidation live de la prescription, de l’affectation et de l’état actif de session |
| `POST /api/cp/v1/sources/get` | Jeton CP_V1, `source_ref` | Revalidation des droits puis octets base64 avec métadonnées et SHA-256 |
| `POST /api/cp/v1/sources/put` | Jeton CP_V1, nom/MIME/taille/SHA-256/octets, association `null` | Dépôt GDA lié au dossier, sans OCR ni affectation métier |
| `POST /api/cp/v1/deliverables/ready` | Jeton CP_V1, `event_id`, type final, empreinte et PDF base64 | Vérification de portée, remise dans GDA et reçu `ACCEPTED`/`REPLAYED`; conflit d'idempotence refusé |

Le lien initial expire après 15 minutes. C&P peut re-signer côté serveur le contexte de la session déjà authentifiée ; GDA revérifie prescription et affectation à chaque `session/check` et à chaque opération. La clé reste exclusivement dans les secrets serveur C&P/GDA et n’est jamais incluse dans le navigateur. Chaque requête ajoute une signature HMAC du corps, de la route et d’un horodatage court. L’inventaire, la lecture et les dépôts utilisent le transport signé ; le retour final PDF possède un reçu idempotent.

## Installation contrôlée côté GDA

Ces fichiers sont une préparation locale du dépôt Clarté360, pas une modification de GitHub. Avant d'activer les routes sur une installation réelle :

1. Ajouter `integration/gda_patch/cp_launch.py` et `integration/gda_patch/cp_hub_api.py` au dépôt Gestion des Actions.
2. Vérifier puis appliquer le patch avec `git apply --check --recount integration/gda_patch/app.py.patch` puis `git apply --recount integration/gda_patch/app.py.patch`. Le patch ajoute le lancement de l'accompagnateur affecté même s'il n'a pas de droit de prescription, le lancement du bénéficiaire, plus l'écran administrateur limité au dépôt pour une prescription C&P. `--recount` est requis par les compteurs de lignes de ce diff.
3. Exécuter le sidecar sous un compte système limité, avec `CLARTE360_SECRET_FILE=/opt/clarte360/secrets/secrets.toml`, en écoute loopback uniquement. Le reverse proxy HTTPS GDA expose seulement `/api/cp/`; le port 8765 ne doit pas être ouvert sur Internet.
4. Déclarer la même clé CP_V1 dans le coffre central et dans les secrets C&P, sous `[COMPETENCES_PROJETS_CONNECTOR].LAUNCH_SIGNING_KEY`. Elle sert à signer les lancements et les requêtes serveur ; elle ne figure jamais dans le navigateur. L'adresse HTTPS du service est déclarée dans `[GESTION_ACTIONS_CONNECTOR].API_BASE_URL` côté C&P. Aucune valeur de clé n'est présente dans le code ou les documents de recette.
5. Rejouer les essais d'intégration sur base GDA isolée, puis effectuer la recette navigateur avec une prescription, un intervenant affecté et un bénéficiaire d'essai.

Le patch `tool_registry.json.patch` met à jour la version candidate mais garde `active=false`, `prescription_allowed=false` et le statut `CANDIDATE_NOT_VERIFIED`. Il ne peut donc pas encore lancer un nouvel essai GDA. L'overlay séparé `tool_registry.test_candidate_enable.patch` active les prescriptions uniquement sur une copie d'essai et marque le statut `CANDIDATE_TEST_ONLY` ; ne pas l'appliquer en production. Le constructeur d'un lien déjà prescrit ne dépend plus de `prescription_allowed` : ce droit contrôle la création d'une nouvelle prescription et ne doit pas couper un dossier existant. Les deux patches du registre et le patch de lancement ont été vérifiés avec `git apply --check --recount` sur les fichiers de `Clarte360/clarte360-outils/clarte360-emargements-v1.0.0` récupérés depuis `main`; les fichiers modifiés ont été compilés dans une copie temporaire. Aucune modification n'a été envoyée au dépôt GitHub. Le dépôt côté GDA bénéficie de son dédoublonnage de contenu ; les octets ne sont pas recopiés durablement dans C&P.

## État de reprise — candidate 0.4.16 (24/10/2026)

- Le pont CP_V1, le client documentaire et le patch demeurent uniquement dans cette candidate C&P. Le dépôt Gestion des Actions est accessible dans `Clarte360/clarte360-outils/clarte360-emargements-v1.0.0`, mais n'est pas cloné dans l'espace de travail. Les patches ont été vérifiés sur la source GitHub récupérée dans une copie temporaire ; aucun changement n'a été poussé.
- Les listes, lectures, dépôts par bénéficiaire/intervenant/administrateur, liens manuels, provenance du déposant, contrôles de droits et remises PDF ont été testés avec des transports simulés. Aucun appel réel à une prescription, au Hub ou à une base GDA n'a été exécuté.
- Le binaire reste dans l'espace commun GDA; C&P conserve uniquement la référence et les liens de besoin explicitement créés par l'accompagnateur. Aucun traitement automatique de contenu ni association inférée n'est effectué.
- GO27 et GO28 ne sont donc pas terminés. GO29 ne peut pas être déclaré complet avant l'installation/test du patch dans une copie GDA et la campagne navigateur/API/persistance/récupération.

## Blocages de sortie

Le patch GDA n'est pas encore appliqué ni exécuté contre la base GDA et le coffre secret. Trois PDF sont produits et proposés pour remise idempotente à GDA ; aucun format Word n'est produit. Le suivi externe et l'archivage/destruction effectifs dans GDA restent à faire. Les tests locaux ne remplacent pas l'installation du patch sur une copie GDA, les appels réels API ni les essais navigateur accompagnateur/bénéficiaire. GO27/GO28 et la recette finale restent ouverts.


## Mise à jour — candidate 0.4.28-go28-work, 24/10/2026

Le bloc « Blocages de sortie » ci-dessus décrit l’état historique au moment de la rédaction et est remplacé par ce relevé pour la candidate actuelle : les trois livrables finaux sont désormais proposés au téléchargement en PDF et DOCX éditable; seul le retour automatique dans GDA reste PDF. Le rendu DOCX a été contrôlé sur un exemple synthétique. Les tests locaux GDA vérifient les listes et ouvertures selon les rôles, mais aucune installation ni requête réelle à GDA n’a été exécutée. Le téléchargement et l’archivage réels, la revue métier des modèles et le suivi à six mois restent ouverts. GO27 et GO28 ne sont pas clos.
