# Point de reprise — Compétences & Projets

## Recadrage prioritaire — cœur ROME et continuité des investigations

- Le cœur métier reste la confrontation, métier ROME par métier ROME, des savoirs et compétences attendus avec les éléments étayés du parcours (expériences, études même sans diplôme, formations et apprentissages personnels), revue en séance par l'accompagnateur et le bénéficiaire.
- Les API d'offres, de marché, d'accès à l'emploi et d'entreprises servent uniquement à enrichir une investigation ciblée. Leur indisponibilité ne bloque ni la mission d'action, ni le questionnaire de retour bénéficiaire, ni le débrief : les liens externes remis dans l'application restent le recours prévu.
- Avant la comparaison, une action ciblée doit être reliée à chaque métier ROME retenu et son retour doit être débriefé. Le questionnaire conserve source, date, apprentissage et effet sur le projet. Les liens de ressources et API à consulter sont choisis selon la question ; aucune ressource ni API précise n’est imposée.
- Ce recadrage ne déclare aucun GO validé et ne modifie pas la séquence des jalons. La référence ROME exploitable reste nécessaire au rapprochement du métier et de ses attendus ; les API d'investigation ne sont pas une dépendance bloquante.
- L’A3 reste la trame des objectifs et de l’ordre du bilan. Pour la confrontation ROME, la décision métier plus récente prévaut sur sa formulation de travail asynchrone : sélection, preuves et niveaux sont examinés en séance sur écran partagé avec l’accompagnateur. La décision de ne pas utiliser DIAGORIENTE prévaut également ; le repère RIASEC/ROME local sert de support d’exploration sans score ni décision d’aptitude.
- Régression vérifiée le 24/10/2026 : La suite complète et la tranche ciblée ROME/investigation ont été exécutées après les évolutions de niveau par attendu et de consigne d’investigation ; tous les tests passent.

Date : 24 octobre 2026  
Candidate de travail : `0.4.18-go22-go28-work`, schéma 13 (étiquette technique provisoire ; ne signifie pas que les jalons sont atteints)  
Dernier jalon validé : GO21 RC2. GO22 reste ouvert et non validé.

## GO22 — niveau discuté pour chaque attendu ROME

- Chaque savoir ou compétence ROME rapproché dispose désormais de son propre niveau d’exercice discuté (1 pratique encadrée/contribution, 2 maîtrise autonome, 3 pilotage/expertise/transmission). Il n’est pas inféré du poste, du diplôme ou de l’IA.
- Un statut « acquis étayé » exige à la fois une preuve de parcours reliée et un niveau discuté. Les autres statuts peuvent conserver un niveau « à préciser ».
- Le niveau est conservé dans le modèle relationnel, la revue versionnée et la vue bénéficiaire. Le schéma 11 ajoute ce champ de façon additive aux bases existantes ; les lignes historiques restent à « niveau à préciser ». À la réouverture, les sélections, statuts, preuves, niveaux et précisions de la dernière revue humaine sont préremplis ; les changements produisent une nouvelle version.
- Aide de séance ajoutée à l’atelier ; statut, preuve et niveau par attendu sont explicités. La progression distingue l’action requise par métier des liens/API consultés, qui restent facultatifs. Cadrage local vérifié par les tests ROME et migration ; GO22 demeure ouvert, aucun GO validé.

## Reprise du développement

L'objectif est d'avancer dans l'ordre des GO sans livrer le GO31 avant les jalons intermédiaires. La feuille de route officielle reste inchangée : terminer GO22, puis GO23 (phases 5–7), puis GO24 (phases 8–11), GO25 API, GO26 IA, GO27 Gestion des Actions/Hub, GO28 documents, GO29 campagne technique, GO30 candidate installable, puis GO31–GO39 recette et mise en production.

La mention précédente « je continue vers GO24 » était erronée : une première tranche de code du plan d'action GO24 a été commencée avant la fin des jalons précédents. C'est du travail exploratoire, pas un changement d'étape, pas une validation de GO23 et pas une autorisation à sauter GO22. GO23 reste un jalon nécessaire pour les investigations terrain, la comparaison des pistes et la décision de projet prioritaire/alternative.

## Tranche de travail GO23–GO24 construite localement

- GO23, phases 5–7 : investigation ciblée avec retour/débrief; comparaison qualitative complète par métier et critères; partage explicite; choix prioritaire et alternative distincte partagés au bénéficiaire. La progression exige une revue complète et publiée.
- GO24, phases 8–11 : résultats détaillés et conditions; plan d'action; synthèse soumise à relecture et finalisée après confirmation du bénéficiaire; clôture et échéance de suivi à six mois. L’ordre visible respecte le déroulé A3, sans renuméroter les identifiants internes de phases 8 et 9. Cette tranche est construite mais ne signifie pas que GO23 est terminé ni que GO24 est validé.
- Aucun score, total ou classement automatique. Le diplôme ou titre obligatoire est documenté à partir d'une source officielle et datée ; l'incertitude reste explicite.
- Les actions sont contrôlées par rôle et dossier et les écritures produisent des événements d'audit.
- Les apports de séance peuvent enregistrer le niveau d’exercice discuté pour l’expérience : 1 pratique encadrée/contribution, 2 maîtrise autonome, 3 pilotage/expertise/transmission. Il ne se déduit pas du titre du poste ; une proposition IA reste un repère à examiner, jamais une preuve ni un verdict.
- L’écran Sources et CV a un client GDA et une file de liaison manuelle ; l’API n’est disponible qu’après installation du patch local côté GDA.

## Travail GO22 phase 0 ajouté dans RC4

- La phase 0 permet maintenant d’ajouter un apport de parcours en séance avant la sélection ROME et de compléter une carte existante : contexte, activités/contenus étudiés, autonomie, réalisations, outils et savoirs mobilisés.
- La nature « études » accepte explicitement les études sans diplôme ; « apprentissage personnel/autodidacte » reste une nature distincte.
- Le niveau d’exercice 1/2/3 peut être noté pour l’expérience concernée. La relecture par le bénéficiaire est cochée explicitement ; sans cela, la carte reste « à confirmer ».
- La phase 0 bloque sa validation tant qu’une carte active n’a pas été explicitement relue avec le bénéficiaire.
- Les modifications sont historisées via les versions de parcours et déclenchent la revue des rapprochements ROME devenus potentiellement obsolètes.
- Le bénéficiaire ne voit pas les cartes brouillon : elles ne sont projetées qu'après validation de la phase 0. Si le parcours validé change, les phases de rapprochement/conclusion concernées sont rouvertes et le détail du parcours redevient caché jusqu'à la nouvelle validation. Après partage, le bénéficiaire voit les cartes détaillées en lecture seule.
- L’écran précise que cette saisie de faits ne sélectionne, ne lit et ne duplique aucun fichier GDA. Le connecteur GDA reste un blocage distinct à traiter dans les GO27/28 selon le contrat existant.

## Travail GO22 phase 0 — réponse après partage (RC3J)

- Après partage de la phase 0, le bénéficiaire peut confirmer le parcours ou demander une correction avec une remarque obligatoire.
- L'accompagnateur voit la décision et la remarque dans la phase 0. Une demande de correction rouvre la phase, remet le parcours à confirmer et masque l'ancienne version partagée jusqu'à sa reprise et sa revalidation.
- Les réponses en double ou portant sur une version périmée sont refusées. La validation suivante résout le signalement de correction.
- Contrôles ciblés : 4 tests dédiés. Suite complète RC4 : **256 tests réussis**.
- Détails : `GO22_RC3J_RETOUR_BENEFICIAIRE_PARCOURS_20261024.md`.

## GO23-1 — investigations reliées aux métiers

- Chaque mission peut être reliée à un métier ROME actif par son identifiant, et le bénéficiaire voit le métier concerné avec l'action à réaliser.
- La phase 5 reste bloquée tant que chaque métier ROME actif n'a pas au moins un retour d'investigation reçu et débriefé.
- Les anciennes missions et leurs réponses sont conservées lors de la migration 8 vers 9; leur métier n'est pas deviné à partir du texte historique.
- Missions automatiques issues des points incertains : non construites. L'accompagnateur formule encore chaque mission après l'échange.
- Détails : `GO23-1_INVESTIGATIONS_LIEES_AUX_METIERS_20261024.md`.

## GO23-2 — missions issues des points incertains

- L'accompagnateur peut choisir un point « à confirmer » ou « non documenté » dans la revue ROME courante et préparer un brouillon de mission ciblé, relié au métier concerné.
- La question issue de l'analyse, lorsqu'elle existe, est reprise dans le brouillon. L'accompagnateur relit et modifie la mission avant de la transmettre explicitement.
- Le bénéficiaire garde les ressources externes et la réponse structurée source/date/constat/effet sur le projet. Le retour est débriefé par l'accompagnateur.
- AppTest de préparation et scénario de mission ciblée réussis. Suite complète RC4 : **259 tests réussis**.
- Détails : `GO23-2_MISSIONS_ISSUES_DE_L_ANALYSE_20261024.md`.

## GO23-3 — repère RIASEC associé au ROME

- Un index local de 1 911 codes ROME et de leurs repères RIASEC, extrait du corpus PDF fourni (juin 2026), est disponible même lorsque les API sont indisponibles.
- Le repère est présenté au bénéficiaire et à l'accompagnateur comme un support exploratoire à mettre en regard du PIP. Il n'évalue pas une aptitude ou une compétence et ne calcule aucune compatibilité.
- AppTest et contrôles d'intégrité du corpus réussis. Suite complète RC4 : **261 tests réussis**.
- Détails : `GO23-3_REPERE_RIASEC_ROME_20261024.md`.

## Contrôles

Compilation réussie. Suite complète : **290 tests réussis**, incluant les tests de transport GDA, liens manuels versionnés, signatures, reçus idempotents, génération PDF, compatibilité CP_V1, extraction de CV, anonymisation de l’en-tête, contrôle de taille DOCX décompressée, questions IA structurées, provenance GDA et ajouts idempotents de cartes. Le patch GDA a été appliqué à blanc sur le fichier source de référence local et le résultat compilé. Ces contrôles sont locaux et techniques. Ils ne remplacent ni l'installation sur la copie GDA, ni l'appel réel des API, ni la recette navigateur/VPS ou métier.

## GO23-4 — cohérence entre comparaison, décision et plan d’action

- Une décision prioritaire ou alternative est liée à l’identifiant de la comparaison publiée discutée avec le bénéficiaire.
- Après publication d’une comparaison révisée, une décision plus ancienne reste dans l’historique mais n’est plus affichée comme actuelle. Le choix doit être repris en séance et repartagé.
- Une nouvelle comparaison publiée rouvre les phases validées 6 à 11, afin de reprendre les décisions et livrables de conclusion dépendants. L’ancien plan n’est plus présenté au bénéficiaire comme son plan actuel ; l’écran lui explique qu’un nouveau plan sera partagé après mise à jour.
- Le plan d’action refuse une décision qui ne correspond pas à la comparaison publiée actuelle ou qui n’a pas été explicitement partagée. La génération/remise du PDF est également suspendue pour un plan obsolète.
- Migration additive du schéma 11 vers 12 ; les décisions historiques restent conservées et non rattachées artificiellement à une comparaison.
- Tests ciblés : migration historique, choix devenu obsolète après révision de comparaison, réouverture des phases 6–8, masquage de l’ancien plan côté bénéficiaire et refus de repartir sur l’ancien choix. Suite complète actuelle : **292 tests réussis**; compilation réussie.

## GO23-5 — recherche et fiche ROME hors ligne

- Le corpus XML fourni `RefRomeXml.zip`, version officielle ROME 4.0 version 61 / 26M06 publiée le 15 juin 2026, est transformé en index local compact des 1 911 métiers. Le ZIP XML et les PDF sources ne sont pas recopiés dans le programme ; seul le contenu utile à la recherche, aux attendus, à la définition et à l’accès descriptif est embarqué.
- L’accompagnateur peut chercher par code, intitulé ou appellation, proposer une fiche locale datée, puis confirmer le métier avec le bénéficiaire. Le snapshot conserve source, version, date et empreinte. L’API France Travail reste disponible pour actualiser la fiche, sans bloquer la recherche ROME locale.
- Les savoirs, savoir-faire et savoir-être sont chargés dans l’atelier ROME pour la confrontation accompagnée. Les formations et accès courants indiqués par la fiche restent descriptifs ; l’application précise qu’ils ne prouvent pas une obligation légale de diplôme.
- Contrôles ciblés : intégrité et unicité des 1 911 codes, recherche « comptable » → M1203, création d’un snapshot local, provenance/date/version, présence des attendus M1203, puis confirmation explicite du métier. Suite complète actuelle : **295 tests réussis**; compilation réussie.
- Limite : le référentiel local est un instantané daté du 15/06/2026. Il ne remplace pas un contrôle de version live lorsque l’accès API fonctionne et ne garantit pas qu’aucune nouvelle version n’a paru depuis.

## GO23-6 — ressources officielles pour les investigations sans API

- Le diaporama de ressources du Dossier 5 daté du 18/10/2026 a été relu dans SharePoint. Les dix liens de ressources sont repris dans l’espace bénéficiaire : MétierScope, Onisep, Offres d’emploi, Data Emploi, La Bonne Boîte, Offre Info, Certif Info, France compétences, QuiForme et Catalogue Apprentissage.
- Les catégories sont proposées selon la mission ; aucun parcours ne demande de consulter systématiquement tous les sites. Le questionnaire source/date/apprentissage/effet sur le projet reste affiché indépendamment des API.
- Un test AppTest vérifie les dix destinations du référentiel, leur rendu et le message d’indépendance aux API sans charger de configuration de service. Contrôles ciblés investigation/ROME/ressources : 6 tests réussis. Suite complète à la clôture de GO23-6 : **296 tests réussis**, compilation Python réussie.
- Aucune API d'offres, de marché, de formation ou d'entreprise n'a été appelée. GO23 reste ouvert jusqu'aux tests réels et à la recette fonctionnelle.

## Alignement GO24 sur l’ordre du déroulé A3

Le classeur A3 présente d’abord l’appropriation des résultats détaillés et les conditions/moyens de réalisation, puis la construction du plan d’action, la synthèse et la clôture. La candidate affichait auparavant le plan avant les résultats. L’ordre visible et le déverrouillage suivent maintenant : résultats détaillés → plan d’action → synthèse → clôture et suivi à six mois. Les conditions de réalisation restent dans la restitution détaillée et le plan d’action les transforme en démarches concrètes.

Les identifiants internes des phases 8 (plan) et 9 (résultats), les validations historiques et les données enregistrées ne sont pas renumérotés. Le moteur de progression suit une table d’ordre explicite. Contrôle ciblé : phase résultats confirmée avant le déverrouillage du plan, navigation accompagnateur et bénéficiaire, **13 tests GO24 réussis**. Le relevé GO24 initial comptait 301 tests; la candidate courante en compte 306. GO24 reste ouvert : les appels GDA réels, les formats Word, le suivi externe et les essais d’usage restent à contrôler.

## Contrôle de reprise GO22 — séquence AV1/AV2 avant le CV

- Régression ciblée des écrans accompagnateur/bénéficiaire C-AV1 + C-AV2, questionnaire Q unique, questions personnalisées par piste, verrouillage/publication, confidentialité des notes, réponses multiples et confirmation R1 après modification : **48 tests réussis**.
- Contrôle distinct parcours phase 0, CV après C-AV3 et rapprochement ROME : **14 tests réussis**.
- L’enchaînement reste celui de l’A3 : C-AV1/AV2 → R1 → préparation C-AV3 → CV/parcours. Les essais utilisent des données synthétiques ; ils ne valent pas test navigateur réel ni appel API.
- La configuration `/opt/clarte360/secrets/secrets.toml` n’est pas présente dans cet environnement. Aucun contenu de secret n’a été consulté. Les appels API réels restent à exécuter dans l’environnement autorisé ; les tests indépendants continuent.

## Suite immédiate

La séquence reste GO22, GO23, GO24 puis GO25–GO31. GO22 n'est pas fermé. Une nouvelle tranche locale analyse le CV après une C‑AV3 courante, produit des propositions à vérifier et permet l’ajout volontaire de cartes à confirmer reliées à la référence GDA. Les étapes GO23 et GO24 sont codées en partie mais restent à recetter, notamment avec les vrais services et le navigateur. Le client GDA, le lancement CP_V1 et l’API documentaire sont préparés ; le patch passe l’application et la compilation contre un fichier source de référence, mais il n'est pas installé dans GDA et aucun appel réel n’a été effectué. Les fichiers restent dans l'espace partagé, sont liés manuellement dans C&P et ne sont pas copiés durablement, OCRisés ou rattachés automatiquement. Le catalogue GDA reste inactif. La procédure GO12 impose des démarches d'accès externes pour plusieurs API ; aucune demande ou activation n'est supposée acquise. Les nouvelles pièces de cadrage confirment que les étapes 0–11 de l’app sont un découpage fonctionnel du bilan réglementaire en trois phases.

La source C&P actuelle est une extraction de travail locale sans répertoire `.git`. Les fichiers `integration/gda_patch/` préparent un raccord dans le dépôt GDA sans modifier GitHub. Aucun commit, push, VPS ou ZIP de recette n'a été produit. Le fichier central `/opt/clarte360/secrets/secrets.toml` n’est pas monté ; aucune valeur de secret n’a été lue. Les appels API réels ne sont donc pas testés ici. Le pont GDA n'est pas installé dans son dépôt réel. Le travail local 0.4.17 ne signifie pas que les jalons GO22 à GO29 sont achevés; la candidate finale de recette sera produite au GO30 après ces contrôles.


## GO24 — état vérifié après audit de la source

La documentation RC1 précédente était périmée : le code couvre déjà les résultats détaillés, la relecture et correction par le bénéficiaire, la synthèse distincte, sa finalisation après confirmation, la préparation du suivi autour de six mois et les préconditions de clôture. Des PDF de remise sont générés pour le plan confirmé, les résultats confirmés et la synthèse finalisée ; le retour GDA idempotent est codé. L’ordre a été réaligné sur le déroulé A3 : résultats et conditions, plan d’action, synthèse, clôture. À la date de ce contrôle initial, 292 tests passaient; la suite à la mise à jour A3 comptait 297 tests réussis; à ce relevé historique, une correction GDA portait la candidate à 301 tests réussis (la candidate courante en compte 306).

GO24 n'est pas fermé : la génération PDF et le contrat de remise sont codés mais le patch GDA reste à appliquer et tester; aucun format Word n'est produit. La sélection, l'ouverture, le dépôt et le lien manuel des documents sont câblés dans C&P mais attendent le service GDA. Le suivi externe et l'archivage/destruction à la clôture ne sont pas exécutés. Les API réelles et le navigateur/VPS ne sont pas testés. Voir `GO24_RC1_ETAT_ET_RECETTE_TECHNIQUE.md` pour les limites et étapes restantes.

## Avancement concret vers GO31

| Jalon | État de la candidate actuelle | Reste avant de le déclarer achevé |
|---|---|---|
| GO22 | AV1/AV2, C‑AV3, parcours ROME et enrichissement CV codés/testés localement ; CV IA disponible après C‑AV3 courante, cartes liées à la référence GDA et à confirmer | Appel IA réel sur cas synthétique/anonymisé, flux GDA réel des 5 documents + APS, test navigateur avec accompagnateur et bénéficiaire d’essai |
| GO23 | Enquêtes, comparaison, décisions et repère RIASEC/ROME présents côté C&P | Recette séquentielle de bout en bout après accès aux vraies sources et avec les acteurs d'essai |
| GO24 | Plan, résultats, synthèse, relectures et suivi présents; PDF générés pour remise | Revue visuelle et remise/réception via GDA; format Word et suivi externe restent ouverts |
| GO25 | Quatre clients ROME séparés par scope; cache API 5 min, actualisation explicite, snapshots et revue en cas de changement. Recherche par intitulé dans le snapshot local daté (1 911 codes); code exact chargeable directement par l’API même s’il manque au snapshot. | La publication France Travail affiche 1 923 fiches; récupérer/réconcilier l’export. Confirmer scopes et appels live. Relier la recherche textuelle à l’API après confirmation des paramètres OpenAPI du compte. |
| GO26 | Adaptateurs C-AV3, CV et rapprochement ROME IA avec sortie structurée, références vérifiées et appels simulés; traçabilité minimale CV ajoutée; corpus synthétique GO26 créé | Essais IA réels sur le corpus synthétique, contrôle humain des réponses; coffre central absent ici |
| GO27 | Constructeur CP_V1, contrôle live GDA de l’affectation sur chaque rerun, sidecar et patch de lancement. Patch de lancement et registre vérifiés sur la version GitHub `Clarte360/clarte360-outils/clarte360-emargements-v1.0.0`, sans pousser de modification. | Appliquer les patches dans une copie GDA d'essai; base de test, routes HTTPS, sessions, révocations, rôles et dépôts réels restent à vérifier. |
| GO28 | Client GDA, écrans documents des trois rôles, références sans binaire C&P, provenance du déposant, lien manuel append-only et remise PDF idempotente ajoutés ; aucun format Word ni archivage/destruction GDA effectif | Sidecar GDA et appels réels à tester ; modèles finaux à valider |
| GO29 | **319 tests réussis**, compilation réussie, transports/signatures simulés, provenance des déposants et reçus contrôlés | Campagne sur instance temporaire, navigateur réel et API/GDA à exécuter |
| GO30 | Pas atteint : la Release Candidate, son rapport de tests et sa procédure d'installation/retour arrière restent à produire après la campagne GO29 | Terminer GO22–GO29, installer et tester les intégrations réelles; fournir ensuite le paquet RC avec zéro anomalie bloquante |
| GO31 | Pas atteint : recette métier Dominique, d'abord accompagnateur puis bénéficiaire | Après le GO30, exécuter le parcours réel complet et relever les anomalies |

La cible prévue pour la Release Candidate est `OneDrive - Clarté360/000000 OUTILS DE TRAVAIL CLARTE360/5 COMP ET PROJET PRO ST/1 JALONS INTERMEDIAIRES`. Aucun ZIP de recette n'y est actuellement déposé.


## GO28 — provenance des dépôts dans l’espace partagé

La décision du 24 octobre exige que le déposant, la date, la version et la liaison humaine restent traçables dans le dossier. Le sidecar GDA conserve une provenance minimale pour les dépôts C&P (rôle, référence technique d’acteur, date), et la renvoie avec la source. C&P conserve ces métadonnées uniquement, affiche le rôle et une référence tronquée à l’accompagnateur et ne copie aucun binaire. Les anciennes sources sans provenance remontée restent explicitement « déposant inconnu »; aucun déposant n’est inventé. Schéma 13 ajouté sans réécrire les références existantes. Contrôles locaux dans la candidate courante : 306 tests réussis et compilation. Le patch GDA et l’appel réel n’ont pas été installés/testés dans le dépôt GDA.


## GO25 — scope dédié ROME Fiches métiers

Le chargement de fiche depuis l'écran ne dépend plus de la configuration du scope « ROME Métiers », produit différent réservé au diagnostic. Seul le scope dédié « ROME Fiches métiers » est requis pour la route `/v1/fiches-rome/fiche-metier/{code}`. L'interface force l'actualisation quand l'accompagnateur le demande; le cache de réponse est limité à cinq minutes. Si la fiche renvoyée est identique, aucun snapshot redondant n'est créé; un changement crée une nouvelle version et rend la confrontation à revoir. Si le scope manque, l'API échoue lisiblement et la fiche locale ROME reste disponible. Une réponse HTTP 404 indique que la ressource demandée est introuvable; elle ne permet pas de conclure que le métier ou ses débouchés n’existent pas. Contrôles ciblés cache/snapshot réussis; suite complète : **306 tests réussis**; compilation Python réussie. Aucun appel France Travail réel n'a été fait. GO25 reste ouvert jusqu'au contrôle des scopes et à l'essai réel sur copie isolée.

## GO26 — traçabilité minimale des analyses CV

Candidate 0.4.16 conserve l'événement d'audit d'une analyse CV réussie : référence/version du document, fournisseur, modèle, version de consigne, empreinte de sortie, durée, consommation si fournie et statut « propositions à valider ». Le journal ne reçoit ni texte du CV ni réponse IA. Les propositions restent en mémoire de séance jusqu'à leur ajout volontaire comme cartes à confirmer. Tests ciblés CV/traçabilité réussis; suite complète : **305 tests réussis**; compilation application + patch GDA réussie. Le corpus `tests/fixtures/go26_cv_regression_cases.json` est entièrement synthétique. Aucun appel réel n'a été effectué; GO26 reste ouvert.

## GO25–GO31 — état de la présente reprise

Le relevé détaillé est `GO25_GO31_ETAT_DE_REPRISE_20261024.md`. L'API Offres France Travail est signalée comme non exposée durant une analyse; le référentiel ROME local et les liens d'investigation maintiennent le parcours bénéficiaire. Le dépôt GDA et l'instance navigateur/VPS ne sont pas montés ici. GO27–29 exigent encore ces validations. GO30 et GO31 ne sont pas atteints. Aucun ZIP de recette n'est actuellement déposé dans `1 JALONS INTERMEDIAIRES`.


## GO25 — contrôle de fraîcheur du ROME et avertissement accompagnateur

Le dernier contrôle des sources publiques révèle un écart : l’index embarqué C&P est ROME 4.0 v61 / 26M06, publié le 15/06/2026, avec 1 911 fiches. La page du jeu de données mise à jour le 20/10/2026 indique 1 923 fiches, tandis que sa fiche de métadonnées API affiche encore 1 911. Le dernier export n’a pas pu être récupéré dans cet environnement. L’index reste un secours daté et peut être incomplet. L’écran accompagnateur l’indique désormais et demande une vérification officielle avant confirmation hors ligne.

Version locale 0.4.18, schéma 13. Diagnostic ROME Fiches métiers ajouté sans affichage des secrets; contrôle ciblé script/connecteur : 11 tests réussis. Suite complète : 306 tests réussis; compilation application, patch GDA et script réussie. Aucun appel France Travail réel n’a été exécuté; GO25 reste ouvert jusqu’à la réconciliation du dernier référentiel et au contrôle API réel. Aucun ZIP, commit, push ou installation VPS n’a été produit.

### Correctif de parcours ROME — 24/10/2026

- Le choix de 1 à 3 métiers doit se faire entièrement dans l’application, avec l’accompagnateur et le bénéficiaire ; aucune recherche ROME externe n’est prescrite pour cette étape.
- Recherche intégrée par code, intitulé et appellation sur le ROME 4.0 v61 complet (1 911 fiches issues de `05-RefRomeXml.zip`). Depuis le résultat choisi, l’écran tente d’abord de charger la fiche France Travail via **ROME Fiches métiers** ; le corpus local reste utilisable dans l’application si l’API n’est pas disponible.
- `07-rome_riasec_clarte360.xlsx` est une table de correspondance ROME/RIASEC et non le fichier complet des attendus. Les compétences de l’index embarqué proviennent du corpus XML complet versionné et restent datées du 15/06/2026.
- L’API est appelée avec le code du résultat sélectionné. Le connecteur ne prétend pas proposer une recherche textuelle API : le produit ROME Métiers est un produit distinct. La fiche est ensuite examinée et retenue explicitement en séance, dans la limite de trois métiers.
- Version locale 0.4.18, schéma 13. Tests de parcours et API intégrée à exécuter avant de poursuivre; aucune connexion France Travail réelle n’est affirmée.


## Reprise ROME / GO25 — 24/10/2026, candidate 0.4.19

La recherche des métiers se fait dans l’application avec l’accompagnateur : code, intitulé ou appellation; aucune recherche externe ROME n’est demandée au bénéficiaire. À partir du résultat, l’action principale charge la fiche via l’API France Travail Fiches métiers. Si l’API échoue, l’index ROME 4.0 v61 issu de `05-RefRomeXml.zip` permet de continuer dans l’application. Le fichier `07-rome_riasec_clarte360.xlsx` est une correspondance ROME/RIASEC, pas le catalogue complet des savoirs. Les compétences de l’index complet ont été validées sur 1 911 codes uniques. Jusqu’à trois métiers peuvent être proposés puis confirmés explicitement en séance.

Candidate locale 0.4.19, schéma 13. Tests complets : 307 réussis; compilation Python réussie. Aucun appel live France Travail n’a été exécuté; le contrôle du scope réel, le nouvel export ROME et l’essai API VPS restent à faire. GO25 demeure ouvert. GO22–GO31 ne sont pas déclarés validés; aucun ZIP n’a été créé.


## GO25 — veille automatisable ROME / candidate 0.4.20

Le corpus est désormais `clarte360_cp/data/rome_catalog.json` et la version/date/compte affichés sont tirés de ses métadonnées. Deux outils permettent de reconstruire un export XML officiel dans un fichier candidat séparé et de comparer les codes ajoutés, retirés et modifiés, sans remplacer l’index embarqué. Un export incomplet, dupliqué ou sans blocs de compétences exploitables est rejeté. La procédure détaillée est `docs/VEILLE_ET_MISE_A_JOUR_REFERENTIEL_ROME.md`.

Contrôle réalisé sur le ZIP ROME fourni : reconstruction 1 911 codes, comparaison à l’index embarqué 1 911 codes, aucun ajout/retrait/changement. Cela valide la reproductibilité de ce ZIP v61; la différence signalée avec les données publiques mises à jour en octobre reste à réconcilier avant clôture GO25. Version 0.4.20; suite complète : 309 tests réussis; compilation Python réussie. Aucun appel live France Travail effectué; aucun GO22–GO31 validé, aucun ZIP de recette créé.

### Mise à jour de travail 0.4.22 — 24/10/2026

- Recherche ROME locale améliorée : accents ignorés, code exact et intitulé principal priorisés avant les appellations. Tests de classement ajoutés; suite complète : 311 tests réussis; compilation réussie.
- Le point SharePoint `POINT_REPRISE_ROME_API_GO23_20261024.txt` précise maintenant la portée de l’API : les quatre produits ROME restent la cible GO-12. L’écran consomme actuellement Fiches métiers après une recherche locale dans l’index de 1 911 codes; une recherche textuelle API et l’intégration dans l’écran des API Compétences et Contextes ne sont pas démontrées. Aucun endpoint n’est inventé en l’absence des OpenAPI du compte.
- Le jeu public France Travail affiche 1 923 fiches au 20/10/2026, alors que les métadonnées API affichent 1 911; la page annonce la prochaine actualisation en mars 2027. L’export récent n’a pas été récupéré, donc la fraîcheur du corpus v61 demeure à réconcilier.
- Aucun appel réel France Travail/OpenAI/GDA n’a été lancé ici; aucun GO22–GO31 validé; aucun ZIP de recette produit.

### Mise à jour de travail 0.4.23 — 24/10/2026

- Les clients API ROME utilisent maintenant des scopes distincts pour Métiers, Compétences, Contextes de travail et Fiches métiers, selon les routes documentées au catalogue officiel GO-11.
- `tools/test_france_travail_rome_all.py` est prêt pour un diagnostic borné des quatre produits avec M1203 et des références synthétiques du corpus. Il ne lit aucun dossier bénéficiaire et n’écrit aucune donnée. Aucun appel réel n’a été exécuté, car le coffre central et le VPS ne sont pas montés ici.
- Suite complète : 318 tests réussis; compilation application/outils/patch réussie. Candidate `0.4.23-go22-go28-work`, schéma 13. Recherche ROME accent-insensible, classée par pertinence; les réponses API Compétences/Contextes sont vérifiées contre le code demandé.
- Aucun GO22–GO31 validé; aucun ZIP de recette produit. GO30 reste inaccessible tant que la campagne réelle API, IA, GDA, persistance et navigateur requise au GO29 n’est pas passée.

### Mise à jour de travail 0.4.24 — ROME et raccordement GDA

- Ajout d’un champ « Code ROME direct » qui appelle **ROME Fiches métiers** à partir d’un code exact, y compris si le code n’est pas dans le snapshot local. Recherche par intitulé/appellation : snapshot v61 de 1 911 codes, explicitement daté et non exhaustif par rapport à la publication France Travail de 1 923 fiches en octobre 2026.
- Les tests AppTest vérifient ce chemin direct avec un code synthétique absent du catalogue; suite complète **319 tests réussis**, compilation réussie. L’API France Travail live n’est pas testée, faute de coffre VPS/OpenAPI du compte dans cette copie.
- Dépôt GDA source retrouvé via GitHub. Sur une copie temporaire de `Clarte360/clarte360-outils/clarte360-emargements-v1.0.0`, `git apply --check --recount` valide le patch de lancement et les deux patches du registre; après application d’essai, le registre reste inactif par défaut et l’overlay porte `CANDIDATE_TEST_ONLY`. Compilation de `app.py`, `cp_launch.py`, `cp_hub_api.py` et validation JSON réussies. Aucun commit, push, déploiement ou appel GDA réel.
- Version `0.4.26-go26-work`, schéma 13. Aucun GO22–GO31 déclaré validé et aucun ZIP de recette produit.
