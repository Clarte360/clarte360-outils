# Veille Qualité GO4 — contrat et recette hors production

Version de développement du 19 octobre 2026. Référentiel : CDC Qualité V1.0, chapitres 16–18 et cas R07, R20, R21, R22 et lien avec R23. Code : `quality_watch.py`. Preuves de ce lot : `tests/test_go4_watch.py` et journaux externes `evidence_go4/logs/watch_run01.*`, `watch_run02.*`, `watch_run03.*`.

## Résultat vérifié

Le groupe dédié contient **80 cas exécutés et réussis**, sur SQLite fictive, avec DNS et HTTP scriptés. Le premier passage de 65 cas a réussi en 11,70 s ; après renforcement de limites concrètes et ajout des cas correspondants, le passage de 77 cas a réussi en 15,25 s. Le passage final, enrichi du retrait effectif d’une action issue de veille, de la normalisation d’identité et du brouillon long, a réussi en 17,25 s (80 cas). Les journaux et rapports JUnit originaux restent séparés. Ces essais ne constituent ni un scan de sources réelles, ni une validation de production, ni la recette de première utilisation par le propriétaire.

Les tests interdisent les connexions et la résolution réseau réelles. La commande de recette a installé en plus un garde d’audit Python avant la collecte pytest ; les dépendances, la base et les identités sont fictives. Aucun courriel, mise à jour de code applicatif ou appel à une IA n’est effectué par le module de veille.

## Parcours et données

Chaque API applicative exige un administrateur existant, actif et un organisme actif, via `quality_service.require_admin`. La source, la technologie, l’information et la décision demandées sont recoupées avec ce contexte. Une modification de registre exige `expected_version` pour une fiche existante. La version exposée s’appelle `row_version`.

Le registre de technologies conserve le nom du service ou outil, sa famille, son éditeur, ses applications consommatrices, son environnement, sa version observée et sa date d’observation, son modèle éventuel, son responsable et sa criticité. Une technologie peut avoir plusieurs applications ; une source peut couvrir plusieurs technologies du même organisme. Les versions inconnues restent vides et doivent être présentées « À confirmer ». Aucune version réelle n’est déduite des plages de dépendances ou d’un secret.

Le registre de sources expose `active`, `configuration_validated`, `allowed_hosts`, `parser_config`, `technology_ids`, `row_version`, `point_zero`, `cursor_at`, `last_success_at`, `last_attempt_at`, `last_error`, `last_successful_month` et `running`. Les priorités et criticités sont `LOW`, `NORMAL`, `HIGH`, `CRITICAL`. Les familles sont un texte contrôlé en longueur. La validation administrative doit confirmer que la source est officielle et pertinente ; une URL seule ne prouve pas cette qualité.

Une source non validée est enregistrée inactive même si l’appel demande `active=True`. La méthode `MANUAL` n’est jamais activée pour une collecte automatique. Modifier une règle d’extraction après un premier succès force une nouvelle validation et remet le curseur à zéro, tout en conservant les exécutions et les versions précédentes. Le point zéro déjà enregistré reste fixe. Toute édition d’interface doit donc conserver son horodatage exact lorsqu’il n’est pas modifié.

Une source sans exécution peut être retirée avec motif ; une source possédant une exécution est archivée et désactivée. Ses informations et son historique demeurent consultables. Les informations de veille sont des versions immuables ; des contraintes SQLite bloquent leur modification et leur suppression directe.

## Collecte et reprise

`collect_source(engine, actor, source_id, trigger='MANUAL')` contrôle une seule source. `collect_due_sources(engine, actor)` applique le calendrier par organisme, le premier jour du mois à l’heure et dans le fuseau configurés, avec rattrapage si le service était arrêté. Le calendrier commence désactivé et requiert une validation. Ces fonctions ne créent aucun processus à l’import ; l’appel depuis le worker est raccordé et testé séparément par l’intégration GO4.

Chaque source a son propre curseur et sa réservation de collecte. Deux lancements concurrents ne déclenchent pas deux collectes de cette source. Une réservation expirée permet une reprise ; l’ancienne exécution devient `INTERRUPTED`. Un résultat tardif qui a perdu sa réservation ne peut modifier ni les informations ni le curseur de la nouvelle exécution.

Toutes les pages annoncées doivent réussir avant la transaction finale. Une erreur, une limite atteinte ou une pagination ambiguë produit une exécution `ERROR`, sans nouvelle information et sans avance du curseur. Le succès d’une autre source reste indépendant. Le curseur de succès correspond au début de l’exécution réussie ; une reprise recouvre par défaut les 14 jours précédents. Une collecte manuelle réussie devient le nouveau point de reprise commun au calendrier mensuel.

L’initialisation lit le flux déclaré sans filtre de reprise. Elle retient les références explicitement repérées, les annonces à effet futur même si publiées avant le point zéro, les publications ou mises à jour depuis ce point et les informations sans date à examiner. Elle ne fabrique pas un historique annuel d’exploitation. Le filtre `since_param` n’est utilisé qu’après un succès et prend le curseur diminué du recouvrement.

La déduplication combine identifiant stable, empreinte du contenu normalisé et numéro de version. Le contenu identique déjà recueilli est inchangé. Une correction différente devient une version reliée, à examiner. Si une seule collecte fournit deux contenus contradictoires pour le même identifiant, elle échoue, sauf si des dates de modification distinctes permettent de retenir la version explicitement la plus récente.

Les résultats exposent `status`, `pages`, `bytes_read`, `items_seen`, `new_items`, `new_versions`, `unchanged`, `ignored_before_zero`, `pages_detail`, `period_start_at`, `period_end_at` et `error`. L’interface doit lire **`new_versions`** pour le nombre de versions modifiées. `bytes_read` compte les corps HTTP reçus complètement, y compris les redirections ; `pages_detail` décrit les pages de contenu effectivement analysées. Les réponses rejetées avant lecture complète peuvent ne pas être intégralement comptabilisées dans ce journal.

La couverture déclarée est `PAGES_PUBLIEES_PAR_LA_SOURCE`. Un succès démontre le parcours des pages que cette source a effectivement annoncées pendant l’exécution. Il ne prouve pas l’exhaustivité historique ou réglementaire, ni la présence d’une publication retirée du flux, ni la détection d’une publication tardive située hors de la fenêtre déclarée par une API. Une source HTML ne renvoyant plus aucune entrée reconnue est une erreur à examiner, pas « aucun changement ».

## Méthodes prises en charge

| Méthode | Contrat |
| --- | --- |
| RSS | Identifiant `guid` ou lien stable, titre, publication RSS ; liens `rel=next` ou en-tête HTTP de pagination. |
| ATOM | Identifiant `id` ou lien stable, titre, publication et mise à jour ; liens `rel=next`. |
| JSON | Liste et champs explicitement configurés ; URL suivante, en-tête HTTP ou curseur opaque de pagination. |
| HTML | Grammaire explicite de balises et attributs, texte UTF-8 ; liens `rel=next`. Aucun navigateur ni JavaScript. |
| MANUAL | Source enregistrée pour contrôle humain. Pas de requête automatique. |

PDF, pages authentifiées, avis privés de tenant, JavaScript nécessaire, protections antibot et formats non pris en charge restent à contrôler manuellement ou à configurer dans une évolution explicitement testée. Aucun contournement ni connecteur réputé fonctionnel n’est créé automatiquement.

### JSON standard

L’objet par défaut attend `items`, `next` et les champs `id`, `title`, `summary`, `url`, `published_at`, `updated_at`, `effective_at`, `is_reference`. Une date sans heure est conservée à minuit UTC. Une date avec heure doit comporter son fuseau ; les dates RSS normalisées sont prises en charge.

Exemple de configuration avec clés imbriquées et curseur :

```json
{
  "items_path": "data.notices",
  "next_path": "",
  "next_cursor_path": "pagination.cursor",
  "cursor_param": "after",
  "fields": {
    "id": "uid",
    "title": "title",
    "summary": "description",
    "url": "official_url",
    "published_at": "published",
    "updated_at": "modified",
    "effective_at": "effective",
    "is_reference": "reference"
  }
}
```

Les chemins sont de simples clés séparées par des points. Aucune expression, fonction ou instruction à exécuter n’est acceptée. `reference_document=true` marque explicitement toutes les entrées d’une source sélectionnée comme documents de référence ; ce réglage doit correspondre à son contenu réel.

### HTML explicite

```json
{
  "item_tag": "article",
  "item_class": "notice",
  "id_attribute": "id",
  "title_tag": "h2",
  "summary_tag": "p",
  "link_tag": "a",
  "link_attribute": "href",
  "published_attribute": "data-published",
  "effective_attribute": "data-effective",
  "reference_attribute": "data-reference"
}
```

Le producteur doit publier une structure correspondant à cette règle. Une source réelle nécessite des exemples représentatifs pour valider cette extraction. Les scripts et styles sont ignorés ; le texte source n’autorise aucune opération.

## Réseau, limites et données externes

La collecte accepte HTTPS sur le port 443, sans identifiant, mot de passe, cookie, proxy hérité ni jeton. La liste d’hôtes est exacte ; les sous-domaines doivent être explicitement ajoutés. Centre Inffo et veilleformation.com restent exclus. Les schémas locaux, hôtes internes, adresses privées, réservées, multicast, IPv6 de transition et réponses DNS mêlant adresses publiques et privées sont refusés.

Chaque destination, y compris chaque redirection et page suivante, est revalidée. La résolution DNS est bornée ; une adresse publique validée est épinglée pour la connexion TCP. TLS vérifie le nom d’hôte d’origine. Il n’y a pas de seconde résolution entre validation et connexion. Le changement de DNS lors d’une redirection ne donne donc pas accès à une destination privée.

| Limite | Valeur par défaut | Maximum configurable |
| --- | ---: | ---: |
| Corps d’une réponse | 1 Mio | 5 Mio |
| Corps reçus sur toute l’exécution | 10 Mio | 20 Mio |
| Délai d’une requête HTTPS | 10 s | 30 s |
| Délai total de collecte | 45 s | 60 s |
| Pages | 20 | 100 |
| Informations parcourues | 2 000 | 10 000 |
| Redirections d’une requête | 3 | 5 |

Le délai DNS est au plus de 5 secondes, compris dans le délai total. Un résolveur système encore bloqué peut finir dans son thread démon après le délai, sans connexion HTTP autorisée pour cette tentative. La taille totale inclut les corps des redirections. Les corps compressés, les réponses tronquées, les tailles incohérentes, les boucles et les formats inattendus sont refusés. Les DTD et entités XML sont interdites, y compris dans un document UTF-16. Le module ne lit aucun fichier de secrets et ne contient aucun branchement IA, interpréteur d’instructions ou outil de mutation autonome.

## Décisions humaines et plan unique

`decide_item(..., decision='NO_ACTION', reason=..., command_id=...)` enregistre une décision close et motivée. Il ne crée aucune ligne `quality_events`, aucune tâche et aucun succès de réalisation. `list_decisions(..., decision='NO_ACTION')` fournit ces décisions pour un bloc séparé du plan. Les compteurs d’actions ne doivent pas les ajouter.

`decide_item(..., decision='ACTION', command_id=...)` crée l’action via `quality_service._create_action_tx` dans **la même transaction** que le lien et la décision. L’information source reste intacte. Deux validations simultanées ou successives réutilisent une seule action. Une version corrigée de la source doit être examinée et peut être rattachée à l’action déjà créée ; elle ne crée pas une nouvelle tâche automatiquement.

La même commande ne peut pas être réutilisée pour une décision différente. Le réexamen d’une décision exige `reconsider=True` et un motif. Un changement « sans action » vers « action » conserve la décision antérieure dans l’historique. Une information déjà liée à une action se suit dans le plan ; elle n’est pas transformée rétroactivement en faux « sans action ». Une action retirée n’est jamais recréée par une relance de collecte, une conversion d’une nouvelle version ou une ancienne commande rejouée. La décision et le lien-tombeau demeurent ; une reconversion renvoie un conflit explicite. Le test R23 exerce effectivement `quality_service.delete_action` sur une base fictive et contrôle la conservation des deux versions de source après une nouvelle collecte.

Le brouillon créé par défaut respecte les limites canoniques de 250 caractères pour le titre et 10 000 pour le contexte, en conservant la référence de source et les dates. Un extrait trop long est signalé par une ellipse. La version originale reste complète et immuable. Un titre ou contexte fourni explicitement doit respecter ces limites.

## API d’intégration

- Sources : `list_sources`, `save_source`, `remove_source`.
- Parc : `list_technologies`, `save_technology`.
- Calendrier : `get_schedule`, `save_schedule`.
- Collecte : `collect_source`, `collect_due_sources`, `list_runs`.
- Informations et décisions : `list_items`, `decide_item`, `list_decisions`.
- Migration additive : `init_watch_schema(conn)`, appelée par `db.init_db` sur sa transaction.

Les paramètres facultatifs `transport`, `resolver` et `now` sont des points d’injection Python pour tests et intégration contrôlée. Ils ne font pas partie des paramètres JSON d’une source. Leur utilisation dans la recette ne valide aucun accès externe réel.
