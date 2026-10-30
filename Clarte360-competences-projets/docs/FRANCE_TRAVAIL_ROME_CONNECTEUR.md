# Connecteur France Travail — ROME et marché du travail (préparation GO-25)

État de la candidate locale au 24/10/2026 : les clients des quatre produits ROME sont séparés par scope. L’écran Accompagnateur peut charger une fiche à partir d’un code exact avec **ROME Fiches métiers** et l’enregistrer en snapshot. Les scopes et la réponse live doivent encore être vérifiés sur l’environnement de recette ; aucun appel réel n’est revendiqué ici.

## Ce qui est livré dans cette branche

- Client serveur OAuth `client_credentials` avec paire `client_id` / `client_secret` lue depuis la section centrale `france_travail`.
- La fiche utilisée par l’écran passe par le scope distinct `rome_fiches_metiers_scope` et la route GO-11 `ROME Fiches métiers /v1/fiches-rome/fiche-metier/{code}` ; le scope reste un paramètre de souscription non secret, jamais déduit ni inventé.
- Le client de diagnostic ROME Métiers utilise séparément `rome_scope` et la route `/v1/metiers/metier/{code}`.
- Le parcours de choix appelle les opérations officielles ROME Métiers `GET /v1/metiers/metier/requete` et `GET /v1/metiers/appellation/requete` pour la recherche textuelle (paramètres documentés `q` et les sélecteurs `champs` propres à chaque réponse). Les résultats d’appellation sont reliés au code et à l’intitulé du métier parent. Si l’API est indisponible ou ne renvoie aucun résultat, la recherche bascule sur l’index local daté. Le chargement API par code ROME exact passe par Fiches métiers, y compris si le code n’existe pas dans l’index. L’accompagnateur examine la réponse et valide le choix avec le bénéficiaire.
- L’accompagnateur lance la recherche avec un bouton, puis les résultats restent visibles pendant qu’il choisit le code. Les requêtes de recherche sont ainsi limitées aux recherches soumises; le client respecte également une cadence globale d’au plus un GET API par seconde.
- Validation du code, délai d'attente borné, cache du jeton en mémoire, contrôle du code retourné et remontée distincte des statuts 401, 403 et 429 sans corps de réponse ni secret dans les erreurs.
- Résultat daté avec provenance et éventuelle version / ETag ; le service `application/rome_catalog.py` enregistre un snapshot GO-09 lors du chargement par l’écran.
- Outil de diagnostic `tools/test_france_travail_rome.py` : affiche seulement le résultat, le code, l'intitulé, la date, la version et l'ETag. N'affiche ni identifiant, ni secret, ni jeton.

## Produits souscrits et usages prévus

La capture du portail du 23/10/2026 montre les sept produits suivants comme
souscrits dans l’application France Travail :

| Produit souscrit | Usage dans le bilan |
|---|---|
| ROME 4.0 — Métiers | Fiches et appellations de référence, activités, compétences et accès |
| ROME 4.0 — Compétences | Référentiel des compétences |
| ROME 4.0 — Contextes de travail | Conditions et environnements d'exercice |
| ROME 4.0 — Fiches métiers | Contenu complet d'une fiche ROME |
| Marché du travail | Données territoriales, offres enregistrées, métiers en tension, embauches et salaires |
| Accès à l’emploi des demandeurs d’emploi | Taux statistique d’accès à l’emploi à 6 mois selon le métier recherché et le territoire ; complément utile pour l’enquête métier du bénéficiaire |
| La Bonne Boîte v2 | Entreprises à potentiel à considérer pour une enquête métier |

L’API « Accès à l’emploi des demandeurs d’emploi » est un complément
fonctionnel au socle : elle répond directement à l’investigation du bénéficiaire
sur les perspectives d’un métier dans un territoire, prévue en phase 5 et utile
à la comparaison de phase 6. Elle ne remplace pas
l’API Marché du travail : elle apporte un indicateur différent, le taux d’accès
à l’emploi à 6 mois (emploi d’au moins un mois dans les six mois suivant
l’inscription, selon la définition France Travail). Ce taux décrit un groupe et
une période ; il ne prédit jamais la situation ni les chances individuelles du
bénéficiaire. L’affichage doit donc montrer la période, le territoire, le métier
et la définition de l’indicateur, et inviter à croiser le résultat avec les offres,
les enquêtes métier et les autres ressources.

« ROME 4.0 — Substitutions d’entités » et « ROME0 v2 » ne sont pas retenus
dans la souscription V1 faute de besoin fonctionnel établi.

L'API Offres d'emploi est prévue comme socle du parcours d'investigation,
notamment pour comparer les offres et leurs employeurs. Au 23/10/2026, France
Travail indique qu'elle n'est plus exposée dans le catalogue et demande de
solliciter l'accès par le formulaire de contact. Le lien direct de recherche
d'offres reste donc disponible dans l'espace bénéficiaire.

Les souscriptions sont visibles dans l’application France Travail existante.
Le scope exact, non secret, doit maintenant être relevé dans le portail et
configuré pour chaque API utilisée. Le secret client reste dans le coffre
central de production. Ne jamais enregistrer
les secrets réels dans Git, une archive ou la documentation.

## Test automatisé

Les tests du client remplacent le transport réseau par des réponses synthétiques. Ils vérifient l'échange OAuth, le GET ROME, l'absence d'appel sur code invalide, la configuration de scope et la non-exposition d'un secret dans un refus 403. Ils ne valent pas appel réel France Travail.

## Appel réel sur le VPS

Le client de diagnostic ROME Métiers peut être testé depuis la racine d'une copie VPS isolée :

```bash
sudo env PYTHONPATH=. /usr/bin/python3 tools/test_france_travail_rome.py --scope 'SCOPE_EXACT_DU_PORTAIL'
```

Le paramètre scope n'est pas un secret. Le script lit les identifiants lui-même dans `/opt/clarte360/secrets/secrets.toml` et ne les affiche pas. Le premier appel proposé utilise `M1203` et réalise au plus un appel OAuth puis un GET ROME. Pour la recette GO22 de l'écran, utiliser le produit et le scope **ROME Fiches métiers** ; le test de l'interface reste à effectuer sur la copie temporaire avec le parcours synthétique du seed.

### Diagnostic réel du produit utilisé par l’écran — ROME Fiches métiers

Un outil séparé teste maintenant le produit **ROME Fiches métiers** avec son scope dédié. Depuis la racine d’une copie de test sur le VPS, la commande effectue une authentification puis un seul GET `M1203`, force une actualisation et affiche seulement le code, l’intitulé, la date, la version et l’ETag reçus :

```bash
sudo env PYTHONPATH=. /usr/bin/python3 tools/test_france_travail_rome_fiches.py --scope 'SCOPE_EXACT_DU_PORTAIL'
```

Le scope n’est pas un secret. Les identifiants sont lus dans le coffre central et ne sont jamais affichés. Ce diagnostic n’a pas encore été exécuté sur le VPS; son existence ne vaut pas appel réel réussi.

## Limites

- Les scopes effectifs du compte ne figurent pas dans la capture ; aucun appel réel n’a donc été vérifié.
- La recherche par intitulé interroge `ROME 4.0 - Métiers /v1/metiers/metier/requete` avec `q` et `champs=code,libelle`; la recherche d’appellations appelle `/v1/metiers/appellation/requete` avec `q` et `champs=libelle,code,metier(code,libelle)` pour retrouver le code et l’intitulé du métier parent. Aucune valeur `qf`, `op` ou `fq` n’est supposée. Si la recherche échoue ou ne retourne rien, l’index local daté sert de secours. Un code saisi directement peut être chargé par **ROME Fiches métiers** même s’il ne figure pas dans l’index. Après sélection d’un résultat, l’écran appelle aussi l’API Fiches métiers avec le code ROME exact.
- Les quatre familles ROME ont des clients séparés par scope : Métiers, Compétences, Contextes de travail et Fiches métiers, sur les routes documentées. L’écran de sélection recherche d’abord via **Métiers**, puis actualise la fiche choisie avec **Fiches métiers**; il ne déclenche pas de requêtes par compétence ou contexte, car la fiche complète porte déjà les attendus nécessaires à la confrontation. Les scopes Compétences et Contextes doivent être repris exactement du portail, sans les déduire.
- Marché du travail, Accès à l’emploi et La Bonne Boîte restent à intégrer avec leurs routes, scopes et modèles documentés.
- Le chargement live ROME Fiches métiers, la confirmation des scopes exacts et la recette de l'interface restent à tester sur le VPS temporaire.
- Ne pas déclarer l'API raccordée à Clarté360 sur la seule base du test synthétique.

### Diagnostic borné des quatre familles ROME

Le script `tools/test_france_travail_rome_all.py` vérifie séparément Métiers, Compétences, Contextes de travail et Fiches métiers avec l’exemple synthétique `M1203` et un code de compétence/contexte provenant du snapshot local. Il utilise les clés centralisées, ne lit aucun dossier bénéficiaire, n’écrit rien dans la base et limite l’affichage au code, libellé, version, date et ETag.

Les scopes non secrets doivent être configurés avec les valeurs exactes affichées dans le portail, dans la section centrale `[france_travail]` : `rome_scope`, `rome_competences_scope`, `rome_contextes_scope` et `rome_fiches_metiers_scope`. La commande sur une copie isolée VPS est `sudo env PYTHONPATH=. /usr/bin/python3 tools/test_france_travail_rome_all.py`. Elle respecte l’intervalle public de 1 appel/seconde entre les appels aux produits.

Le diagnostic n’a pas été exécuté ici : le coffre central et l’environnement VPS ne sont pas montés dans cette copie.

## Parcours de choix ROME (correction d’usage du 24/10/2026)

Le bénéficiaire n’effectue aucune recherche ROME externe pour choisir les métiers. L’accompagnateur recherche avec lui dans l’application et peut proposer jusqu’à trois métiers. La recherche est faite via **ROME Métiers**; le chargement d’une fiche complète passe par **ROME Fiches métiers** à partir du code exact. Le snapshot local v61, issu de `05-RefRomeXml.zip`, est un secours daté ; une API indisponible ne doit pas être présentée comme une preuve de fraîcheur ou d’exhaustivité. La proposition reste distincte d’un choix confirmé : l’accompagnateur enregistre la décision prise en séance avec le bénéficiaire.

Le fichier `07-rome_riasec_clarte360.xlsx` est un rapprochement ROME/RIASEC, pas le catalogue des fiches ni la source des compétences. Le XML `05-RefRomeXml.zip` a produit un snapshot v61 / 26M06 du 15/06/2026 avec 1 911 codes uniques. Ce snapshot est fidèle au ZIP fourni, mais il n’est pas prouvé complet par rapport au référentiel courant : la page officielle France Travail publiée le 19/10/2026 affiche 1 923 fiches et annonce une prochaine actualisation en mars 2027. Le classeur et le ZIP local ne remplacent donc pas l’API souscrite. Une mise à jour du référentiel déclenche une comparaison des codes/contenus et une revue des rapprochements dépendants.


## Correctif GO25 — scopes indépendants (24/10/2026)

La configuration a été corrigée pour respecter les produits souscrits séparément : l'écran ROME utilise « ROME Fiches métiers » et son propre scope. Il ne demande plus le scope du produit distinct « ROME Métiers ». Celui-ci reste nécessaire uniquement au client de diagnostic `fetch_metier` / à l'outil de test correspondant. Un mapping central peut donc configurer le scope Fiches métiers seul; chaque route refuse toujours l'appel si son propre scope manque. Tests locaux : appel synthétique fiche avec le seul scope Fiches métiers, refus propre de l'outil Métiers sans son scope, et non-régression ROME hors ligne. Aucun appel réel n'a été effectué.
