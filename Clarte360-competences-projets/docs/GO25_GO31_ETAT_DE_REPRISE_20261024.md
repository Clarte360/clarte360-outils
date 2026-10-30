# GO25 à GO31 — état technique de reprise

Date de contrôle : 24 octobre 2026  
Candidate locale : `0.4.29-go29-work`, schéma 13
Dernier jalon officiellement validé : GO21 RC2.

Ce relevé distingue le code construit, les tests locaux, les raccordements réellement exécutés et la recette métier. Aucun GO22–GO31 n'est déclaré validé par ce relevé.

| Jalon | Construit et vérifié dans la candidate | Condition restante avant clôture |
|---|---|---|
| GO25 API | Clients OAuth France Travail séparés par scope pour les quatre familles ROME Métiers, Compétences, Contextes de travail et Fiches métiers; cache de réponse 5 min avec actualisation explicite, snapshots API datés et signés, hash identique sans nouvelle version et revue requise lors d'un changement; un HTTP 404 est signalé sans inférer l’absence du métier ou de débouchés. Recherche textuelle prioritaire via les opérations officielles ROME Métiers `/v1/metiers/metier/requete` et `/v1/metiers/appellation/requete`; les appellations retrouvent le code et l’intitulé du métier. La recherche est soumise par bouton et les GET sont limités à un par seconde. Snapshot local v61 (1 911 fiches) en secours si l’API échoue ou ne retourne rien. Un code ROME direct peut charger la fiche API même s’il manque du snapshot. Jusqu’à trois métiers peuvent être proposés puis retenus explicitement en séance. Le diagnostic synthétique contrôle les quatre produits et la recherche textuelle. | Réconcilier le ZIP fourni avec les 1 923 fiches affichées par France Travail; contrôler les quatre scopes souscrits et exécuter le diagnostic réel sur environnement isolé. Le classeur RIASEC ne remplace pas le catalogue ROME. |
| GO26 IA | Appels Responses structurés pour C‑AV3, CV et rapprochement ROME; `store=false`, validation des références, limites et champs de sortie, revue humaine et refus de conclusions automatiques. L’analyse CV trace source/version/modèle/prompt/empreinte/durée/tokens disponibles sans stocker CV ou sortie dans le journal. Corpus synthétique ajouté. Tests simulés. Diagnostic live sur corpus fictif prêt pour les trois pipelines. | Exécuter les trois diagnostics dans l’environnement VPS et faire la revue humaine des propositions, références et incertitudes; aucun secret IA accessible ici. |
| GO27 GDA/Hub | Contrat CP_V1, sidecar, clients signés, revalidation de session et des affectations, gestion des documents et remises PDF préparés. La visibilité documentaire est évaluée selon le rôle : le bénéficiaire ne voit que les références publiées qui lui sont visibles; l’accompagnateur affecté peut examiner les documents publiés du dossier, sauf ADMIN_ONLY; l’administrateur reste en dépôt seul. Patch de lancement et registre vérifiés sur le dépôt GitHub `Clarte360/clarte360-outils/clarte360-emargements-v1.0.0`; activation réservée à une copie d'essai. | Le dépôt n'est pas cloné ici et aucune installation n'a été faite sur GDA; connecter une base d'essai, exécuter l'APS et les cinq sources, les trois rôles, les événements retour, les révocations et le contrôle d'absence de double saisie. |
| GO28 Documents | Les trois livrables finaux (plan convenu, résultats détaillés confirmés, synthèse finalisée) sont proposés en PDF et DOCX éditable à partir des mêmes sections; rendu DOCX synthétique contrôlé. Le retour automatique GDA reste PDF. | Revue métier des modèles, téléchargement/archivage réels via GDA et suivi à six mois à exécuter. |
| GO29 Campagne | Suite locale complète : 330 tests réussis; compilation Python réussie. Le test synthétique de sauvegarde/restauration SQLite vérifie maintenant la présence de l’enregistrement restauré, en plus de l’intégrité; droits GDA et connecteurs sont exercés avec réponses synthétiques. Smoke local Streamlit : santé HTTP OK, liens signés synthétiques accompagnateur/bénéficiaire en HTTP 200, plus 30 tests AppTest ciblés réussis. | Campagne réelle API/IA/GDA, persistance et restauration sur instance, navigateur desktop/mobile, isolation et rôles. |
| GO30 RC | Un paquet candidat est préparé pour essais humains isolés et accompagné d’une procédure d’installation/retour arrière; statut non validé. | La campagne réelle GO29, la revue des essais et la confirmation humaine restent à obtenir avant toute clôture GO30. Le paquet ne constitue pas un déploiement et GO21 RC2 reste le dernier jalon validé. |
| GO31 Métier | Non atteint. | Après GO30 : Dominique conduit le parcours accompagnateur puis bénéficiaire sur 3–4 séances simulées et contrôle la compréhension Qualiopi. |

## Éléments vérifiables

- Contrôle des sources ROME au 24/10/2026 : l’index embarqué est v61 / 26M06 (1 911 fiches, 15/06/2026). La page officielle France Travail publiée le 19/10 affiche 1 923 fiches; le ZIP local ne peut donc pas être décrit comme exhaustif pour la version courante. Il reste un secours daté. La saisie d’un code exact interroge maintenant l’API Fiches métiers, ce qui permet de charger un code absent du snapshot local.

- Le déroulé A3 joint conserve les trois phases réglementaires; les phases internes 0–11 de l’application restent un découpage fonctionnel. Le repère ROME/RIASEC embarqué a été comparé au classeur source : 1 911 codes uniques dans les deux fichiers, sans code absent/supplémentaire ni différence de libellé, de repère brut, de repère normalisé ou de PDF source.

- `tests/fixtures/go26_cv_regression_cases.json` contient quatre cas entièrement synthétiques : expérience sans diplôme, dates/périmètre incertains, instruction parasite dans un CV et CV pauvre.
- `clarte360_cp/application/cv_enrichment.py` journalise uniquement une trace minimale d'analyse CV acceptée; les textes du CV et la réponse IA ne sont pas copiés dans l'événement.
- `docs/GO27_GO28_CONNECTEUR_GDA_RC1.md` décrit le contrat CP_V1 et les tests d'intégration qui restent à exécuter.
- L'espace de travail n'a pas de dépôt Git C&P local. Le dépôt GitHub `Clarte360/clarte360-outils` est accessible en lecture; les patches GDA ont été vérifiés sur sa version `clarte360-emargements-v1.0.0`. Les commits et push restent gérés par Dominique.
- `/opt/clarte360/secrets/secrets.toml` est absent de l'environnement courant. Aucun secret n'a été lu ou copié.

L'API Offres d'emploi France Travail est actuellement signalée comme non exposée publiquement durant une analyse. Cette indisponibilité n'empêche pas les missions d'investigation, leur questionnaire de retour ni le débrief : les liens ressources présents dans l'application restent disponibles. Cela ne dispense pas de l'appel live ROME Fiches métiers requis pour caractériser le connecteur ROME de GO25.

## Correctif de sélection métier ROME et veille de données — 24/10/2026

- Le bénéficiaire ne fait pas de recherche externe pour sélectionner les métiers. L'accompagnateur et lui recherchent dans l'application et y valident de 1 à 3 propositions.
- Les résultats par intitulé interrogent `ROME Métiers /v1/metiers/metier/requete`; les appellations interrogent `/v1/metiers/appellation/requete` et sont reliées au métier parent. Paramètres validés dans la documentation officielle : `q`, `champs=code,libelle` pour les métiers et `champs=libelle,code,metier(code,libelle)` pour les appellations. En cas d’indisponibilité ou de résultat vide, l’application bascule sur le snapshot local explicitement daté. Un champ code direct interroge l’API Fiches métiers et accepte les codes absents du snapshot.
- `07-rome_riasec_clarte360.xlsx` est un rapprochement ROME/RIASEC. Le snapshot de savoirs/compétences dérivé de `05-RefRomeXml.zip`, version 61 / 26M06, a 1 911 codes uniques; il est fidèle au ZIP fourni mais n’est pas complet au regard des 1 923 fiches publiées par France Travail en octobre.
- L’index a été renommé `rome_catalog.json`; l’écran lit dynamiquement sa version, sa date et son nombre de codes.
- Un constructeur générique et un outil de comparaison reconstruisent un export candidat puis détaillent les codes ajoutés, retirés et modifiés. Aucun remplacement du catalogue courant n’est automatique. Le test de reproductibilité de l’export fourni v61 donne 1 911 → 1 911, sans ajout, retrait ni fiche modifiée.
- La procédure de veille est décrite dans `docs/VEILLE_ET_MISE_A_JOUR_REFERENTIEL_ROME.md`.
- Version de travail 0.4.27-go27-work, schéma 13. La suite complète de la candidate précédente avait 327 réussis; pour ce changement GDA, compileall/AST passent, mais pytest ne peut pas être relancé dans l’environnement actuel car le paquet manque et le cache hors ligne est vide. Les clients ROME Métiers, Compétences, Contextes et Fiches métiers utilisent des scopes indépendants et les codes reçus sont contrôlés. La recherche textuelle API interroge maintenant les opérations officielles métiers et appellations, relie les appellations à leur métier parent et conserve le snapshot local comme secours daté. Côté IA, les validateurs C‑AV3 et ROME rejettent maintenant les champs imprévus, références non autorisées et sorties hors limites. Les tests ciblés et la suite complète passent. Les diagnostics réels France Travail et IA restent à exécuter dans l’environnement VPS. GO25, GO26 et GO27 restent ouverts; aucun jalon n'est déclaré validé.


## Mise à jour — GO28/GO29, contrôles locaux du 24/10/2026

- Candidate locale : `0.4.29-go29-work`, schéma 13. GO21 RC2 reste le dernier jalon officiellement validé; GO22–GO31 ne sont pas déclarés validés.
- Relance de la suite complète : 330 tests collectés et réussis. `compileall` sur l’application, les outils et le patch GDA réussit.
- Renforcement du test de restauration : après sauvegarde SQLite et restauration dans un fichier cible isolé, le test vérifie l’intégrité et la présence du dossier synthétique restauré. Ce contrôle ne constitue pas une restauration réelle de l’instance ni un test navigateur/VPS.
- Les versions PDF/DOCX des trois livrables finaux sont construites et le rendu DOCX a été contrôlé sur un exemple synthétique. Le flux GDA reste à tester en réel.
- Aucun appel live France Travail/OpenAI/GDA, aucune installation GDA, aucun parcours navigateur/VPS, commit, push ou déploiement n’a été effectué. GO25–GO29 restent ouverts jusqu’aux conditions de recette correspondantes; aucun GO22–GO31 n’est validé. Le ZIP GO30 candidat est préparé pour la recette humaine isolée décrite dans `docs/GO30_RECETTE_HUMAINE.md`; il ne vaut pas validation du GO30.


## Complément GO29 — démarrage local et vues multi-rôles

- L’application Streamlit a démarré sur un port local avec une base SQLite temporaire, un secret synthétique et des identifiants de test fictifs. Le contrôle `/_stcore/health` a répondu `ok`; les liens signés des rôles accompagnateur et bénéficiaire ont répondu HTTP 200. Les données et secrets temporaires sont restés hors de la candidate.
- Les tests ciblés `test_go22_rc3c_session_access.py`, `test_go24_beneficiary_ui.py` et `test_intersession_ui.py` passent : 30 tests.
- Ce smoke test ne constitue pas une recette visuelle par navigateur : le navigateur distant n’accède pas au port loopback isolé de l’environnement. Il ne valide ni le VPS, ni le GDA réel, ni les appels API réels, ni la persistance/restauration d’une instance. GO28 reste ouvert; GO29 n’est pas déclaré validé.


## Mise à jour — candidate de recette humaine GO30 préparée

- Version du paquet : `0.4.29-go29-work`, schéma 13. Archive candidate humaine : `CLARTE360_COMPETENCES_PROJETS_GO30_RECETTE_HUMAINE_CANDIDATE_0.4.29_20261024.zip`.
- Le paquet contient l’application, tests et ressources, un guide de recette humaine, et un lanceur Windows qui utilise uniquement une base, des identifiants et une clé fictifs temporaires pour la prévisualisation locale. Le protocole précise le retour arrière et les essais live restant à faire dans une copie de recette.
- Les contrôles automatisés de candidate et de lanceur restent locaux; GO29 réel (API/IA/GDA, VPS, navigateur complet, restauration de l’instance) n’est pas exécuté ici. La revue humaine est attendue avant toute clôture.
- GO21 RC2 reste le seul jalon officiellement validé. Aucun commit, push, déploiement, activation GDA production ni test avec données réelles n’a été effectué.
