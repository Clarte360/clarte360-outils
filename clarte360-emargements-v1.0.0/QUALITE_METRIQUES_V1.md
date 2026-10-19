# Qualité GO4 — Méthode des enquêtes et confidentialité Client

Référence fonctionnelle : CDC Qualité V1.0 du 18 octobre 2026, chapitres 10–13, R09–R12 et R16. Cette réalisation est une candidate hors production. Les paramètres et publications créés par les tests concernent uniquement leurs bases fictives.

## Ce que la méthode V1 mesure

Une ligne `quality_campaigns` est une invitation à un répondant. Une réponse à une question n’est pas une invitation supplémentaire. Le rapport affiche séparément invitations existantes, invitations futures, invitations ouvertes, envois attestés, brouillons et questionnaires finalisés. Le nombre théorique de personnes éligibles n’est pas inventé à partir des campagnes : `eligible_people` reste absent de mesure tant qu’une règle d’éligibilité indépendante et validée n’existe pas.

Le périmètre de période est la **date d’ouverture prévue du questionnaire** (`due_at`). Les envois et les retours utilisent cette même cohorte, même si l’envoi effectif a eu lieu un autre jour. Ce choix figure dans le rapport et l’export.

| Mesure | Définition V1 |
|---|---|
| Satisfaction globale /5 | Moyenne d’une seule globale valide par questionnaire finalisé. La question globale est explicitement désignée avant utilisation du modèle, ou identifiée par l’unique rubrique R10 de type SCALE_1_5 du référentiel. Absence ou ambiguïté : aucune globale calculée. |
| Satisfaction positive | Nombre de globales au moins égales au seuil positif / nombre de globales valides. Quatre sur cinq est la proposition initiale, affichée comme telle jusqu’à confirmation. |
| Taux de retour | Questionnaires finalisés **parmi les invitations réellement envoyées et ouvertes** / ces invitations envoyées. Annulations et invitations futures exclues. Une finalisation sans preuve d’envoi est comptée séparément et signalée ; elle n’est pas utilisée pour fabriquer un taux supérieur à 100 %. |
| Thème | Moyenne des moyennes individuelles sur un jeu d’items comparable. Effectifs de questionnaires et d’items affichés ; aucun arrondi intermédiaire. Les jeux d’items différents restent séparés. |
| NPS | Pourcentage des valeurs 9–10 moins pourcentage des valeurs 0–6, sur une unique question NPS explicite de chaque questionnaire finalisé. Le NPS ne contribue jamais à une note sur cinq. |

Les familles HOT, COLD, TRAINER, CLIENT, PRESCRIBER et OPCO restent distinctes. Aucune moyenne Client/Prescripteur implicite. Les réponses vides et N/A sont absentes, pas nulles au sens d’une note zéro. Les booléens, nombres hors plage, valeurs non finies, chaînes numériques et valeurs non entières sur les deux échelles sont rejetés des mesures et signalés. Les réponses textuelles restent hors calcul.

Avec quatre globales 5, 4, 3, 5, la note est **4,25/5** et la satisfaction positive **75 %** pour le seuil proposé de quatre. Quatre questionnaires finalisés parmi cinq invitations envoyées donnent **80 %** de retour. Ajouter une invitation future non envoyée ne modifie aucun de ces trois résultats.

## Version des questionnaires et reprise

L’initialisation ajoute des tables ; elle n’écrase aucune réponse ou table RC2. La création d’une campagne et son contrat sont enregistrés dans la même transaction. `quality_campaign_contracts` conserve les questions, leurs types, rubriques, textes, positions, caractère obligatoire, la mesure globale, le modèle et sa version. L’action, la famille et l’organisme sont également figés pour détecter une réaffectation silencieuse. Le contrat ne peut pas être modifié par une mise à jour SQL ordinaire.

La classification est explicite : `REAL`, `TEST`, `A_EXAMINER`. Le rapport V1 prend `REAL` par défaut. Un nom de fichier ou d’action contenant « TEST » ne permet pas de requalifier silencieusement le patrimoine. Une campagne historique sans contrat est `A_EXAMINER` tant que l’administration ne l’a pas qualifiée.

L’adoption explicite d’une campagne ayant déjà des réponses utilise leurs instantanés RC2 de rubrique, type et texte. La version exacte du modèle et son titre d’origine n’avaient pas été enregistrés : la V1 les marque **historiques non attestés**, plutôt que de leur attribuer les libellés actuels. Cette réserve reste visible et empêche une publication Client tant que la cohorte ne satisfait pas tous les contrôles. Les anciennes fonctions statistiques sont conservées avec la mention `RC2_ITEMS_LEGACY` pour leur compatibilité ; l’interface GO4 utilise la V1 et ne présente plus leurs moyennes d’items comme la satisfaction globale.

## Personnes distinctes et Espace Client

Deux questionnaires d’un même bénéficiaire sur deux formations sont deux questionnaires et une seule personne distincte. Le comptage s’appuie sur l’identité centrale bénéficiaire, intervenant ou contact externe. Une participation isolée ou une adresse électronique ne suffit pas à attester une nouvelle personne. Une identité non fiabilisée contribue aux réponses administratives mais interdit la publication Client de sa cohorte.

Le calendrier d’une **formation** est autorisé par un grant actif d’action, y compris avec un inscrit. Son accès ne dépend pas d’un seuil statistique. Les calendriers et contenus individuels de bilan de compétences/coaching restent protégés. Les droits documentaires existants n’ont pas été élargis. Les comptes inactifs, contacts archivés, courriels CRM incohérents et grants révoqués sont revérifiés à chaque lecture et export.

La satisfaction Client repose sur une publication volontaire **fixe** par formation clôturée et par famille HOT ou COLD. Aucun filtre libre de dates, personnes, thèmes ou sous-groupes n’est proposé au Client. La politique doit d’abord être confirmée et activée ; rien n’est publié par défaut. Le seuil initial de cinq personnes distinctes est un choix interne proposé, pas une obligation universelle Qualiopi.

La publication exige au moins le seuil de répondants distincts, des identités connues et aucun petit groupe complémentaire identifiable. Ce contrôle considère aussi les participants inscrits qui n’auraient reçu aucune invitation. Les brouillons, invitations futures ou anomalies de la cohorte bloquent la publication. Le NPS possède son propre seuil et son propre contrôle de complément : cinq globales valides ne rendent pas communicable un NPS donné par une seule personne. Un NPS protégé n’expose pas son petit effectif exact.

Une deuxième publication identique est idempotente. Une publication modifiée sur le même périmètre est refusée pour empêcher la déduction d’une réponse ajoutée ou corrigée par différence entre deux versions. L’ancienne publication conserve sa date et ses valeurs de référence. Elle peut être retirée ; un retrait ne prétend pas effacer une information déjà consultée. Toute évolution de cette stratégie nécessite une règle de publication explicitement validée.

## API et contrôles

Les entrées administratives suivantes demandent un `QualityActor` actif et le bon organisme :

- `survey_dashboard(engine, actor, ...)` et `export_survey_csv(engine, actor, ...)` : mêmes filtres et même source autorisée ; timestamp, méthode et classification présents ; aucun nom, commentaire individuel ou jeton exporté.
- `configure_template_measure(engine, actor, template_id, global_question_id)` : uniquement avant la première utilisation d’un modèle ; ensuite une nouvelle version est requise.
- `classify_campaign(engine, actor, campaign_id, classification)` : qualification explicite et auditée du patrimoine ou des essais.
- `metric_policy` et `configure_metric_policy` : seuil positif, seuil Client et confirmation, par organisme.
- `publish_client_satisfaction` et `revoke_client_satisfaction` : publication fixe volontaire ou retrait, sans email.

L’Espace Client passe exclusivement par `client_quality_satisfaction(engine, account_id, action_id, campaign_kind)` et `export_client_quality_csv(...)`, qui recontrôlent le grant et restituent uniquement le même agrégat publié. Le tableau de bord personnel utilise le nombre de lignes canoniques autorisées du plan Qualité pour ses demandes ; les contacts d’une même entreprise n’obtiennent aucun partage implicite.

Les hooks `_snapshot_campaign_tx` et les lectures de questions figées sont des interfaces internes appelées par le parcours d’enquête déjà lié à son jeton. Ils ne remplacent pas l’authentification du portail ou les contrôles d’un endpoint.

## Vérification et limites

Les scénarios automatisés sont dans `tests/test_go4_metrics.py`. Ils couvrent notamment les valeurs R09, les futurs/TEST/invalides, l’absence de globale, les versions historiques, la moyenne individuelle des thèmes, les familles et le NPS séparés, les exports et identifiants non autorisés, les personnes distinctes, le calendrier d’un inscrit et les protections Client par complément et publication fixe. Les résultats chiffrés de recette figurent dans le rapport de livraison, pas dans ce document de méthode.

Ces contrôles techniques ne constituent pas une affirmation générale de conformité juridique, ni une validation de la méthode par le propriétaire en production. Les identités centrales doivent être fiables. La recette de première utilisation prévue par le CDC et l’approbation des paramètres réels restent des étapes explicites de la livraison.
