# GO22 RC3H — règle métier du rapprochement des savoirs et des diplômes

**Statut : contrat fonctionnel et atelier de rapprochement, clarification séquentielle et boucle d’investigation implémentés dans la candidate `0.4.0-go22-rome-matching-rc3`. La connexion live, l’essai IA réel, la recette navigateur/VPS et la validation métier restent ouverts.

## Finalité

Le travail principal consiste à rapprocher, pour chacun des métiers ROME sélectionnés avec le bénéficiaire, les savoirs et compétences attendus avec les éléments réellement étayés de son parcours. L’objectif est de rendre visibles les acquis, les points à confirmer, les éléments non documentés et les savoirs ou compétences que le bénéficiaire souhaite développer. Ce rapprochement aide à investiguer et à décider ; il ne décide jamais à la place du bénéficiaire.

## Sources de savoirs et preuves recevables

Un savoir ou une compétence peut être étayé par :

- une expérience professionnelle ou personnelle et des réalisations observables ;
- des études suivies, même si elles n’ont pas été sanctionnées par un diplôme ;
- une formation, une certification ou un apprentissage individuel ;
- une mise en pratique décrite et vérifiée en entretien, dans une enquête métier ou au moyen d’un autre élément pertinent.

Pour chaque rapprochement, conserver le savoir/compétence ROME visé, l’élément de parcours qui l’étaye, sa provenance et son état de validation par l’accompagnateur et le bénéficiaire. Un diplôme absent ne permet pas de conclure à l’absence de savoir. La présence d’un diplôme ne prouve pas automatiquement la maîtrise actuelle de chaque savoir attendu.

États de travail prévus : **acquis étayé**, **à confirmer**, **non documenté**, **à développer**. Un élément « non documenté » signifie que les preuves disponibles ne suffisent pas encore ; ce n’est pas un verdict d’incapacité.

## Diplômes et autres conditions d’accès

Le diplôme, titre, autorisation ou habilitation est affiché comme **obligatoire pour exercer** uniquement lorsque l’obligation est établie par une source officielle pertinente pour le métier et le périmètre concernés. Garder la référence de la source, sa date de consultation et la règle qu’elle justifie. À défaut, indiquer **obligation non vérifiée** ou **aucune obligation officielle identifiée**, selon le travail réellement effectué ; ne pas présenter une préférence de recrutement comme une obligation légale.

Distinguer explicitement :

1. savoirs et compétences attendus par le ROME ;
2. diplôme/titre ou autorisation officiellement obligatoire pour exercer ;
3. conditions parfois demandées ou souhaitées par les employeurs, notamment celles observées dans des offres ;
4. autres conditions d’exercice et éléments à investiguer.

Le ROME décrit des métiers, activités, compétences et contextes. À lui seul, un libellé de fiche ROME, une offre d’emploi, une réponse d’IA ou un résultat statistique ne suffit pas à déclarer un diplôme juridiquement obligatoire. Les produits France Travail souscrits documentent le métier et le marché ; la vérification des professions réglementées doit s’appuyer sur la source officielle compétente et être tracée séparément.

## Décision de formation

Ne pas prescrire automatiquement une formation à partir d’un diplôme manquant ou d’un statut « non documenté ». Une formation peut être étudiée si :

- elle répond à une exigence obligatoire vérifiée ; ou
- le bénéficiaire et l’accompagnateur constatent un besoin de savoirs/compétences utile au projet et choisissent de le travailler.

Lorsque l’accès est possible par l’expérience, par des études non diplômantes ou par un apprentissage personnel, ces voies restent visibles dans l’analyse. L’exemple métier du porteur de projet est parlant : on peut envisager un poste de chef comptable à partir des savoirs acquis par l’expérience, les études ou l’apprentissage ; il faut traiter séparément les conditions officielles d’exercice d’une profession réglementée telle que l’expertise comptable. Cet exemple illustre le raisonnement et ne remplace pas la vérification de la règle officielle applicable au métier réellement visé.

## Usage de l’IA et des données

L’IA peut aider à extraire, reformuler, relier et proposer des questions de vérification. Elle doit présenter les preuves et les incertitudes et ne peut ni inventer un savoir, ni déclarer seule un acquis, ni transformer une exigence d’offre en obligation officielle, ni décider qu’une personne est exclue d’un métier. Toute proposition est relue et validée humainement.

Pas de score global, de classement ou d’exclusion automatique. Le bénéficiaire garde la décision sur son projet et sur les investigations ou formations qu’il souhaite engager.

## Raccordement prévu

- **ROME Métiers, Compétences, Contextes de travail et Fiches métiers** : références métier versionnées pour sélectionner les attendus et contextualiser les activités.
- **Marché du travail, Accès à l’emploi des demandeurs d’emploi et La Bonne Boîte** : éclairages collectifs et pistes d’enquête, à contextualiser par métier et territoire ; ils ne remplacent pas la confrontation des savoirs ni la décision du bénéficiaire.
- **Ressources externes remises au bénéficiaire** : elles restent accessibles même lorsque les API sont fonctionnelles et nourrissent ses investigations (rencontres, offres, immersions, formations et vérifications de terrain).
- Conserver pour chaque source sa date, sa version si disponible, le périmètre consulté et l’information effectivement retenue.

### Indépendance des investigations vis-à-vis des API de marché

Les API Offres d'emploi, Marché du travail, Accès à l'emploi et La Bonne Boîte sont des éclairages d'investigation. Leur indisponibilité ne bloque ni le rapprochement des savoirs avec le ROME, ni la prescription d'une action au bénéficiaire, ni son retour. L'accompagnateur confie une question ciblée ; le bénéficiaire utilise les liens de ressources adaptés et retourne dans le formulaire de l'application la source, la date, ce qu'il a appris et l'effet sur son projet. Le retour est ensuite débriefé en séance. Les ressources externes restent accessibles même si les API correspondantes échouent.

Cette souplesse ne dispense pas de disposer d'une référence ROME exploitable pour sélectionner et confronter les attendus du métier. Le catalogue ROME sert le cœur de l'application ; les API de marché enrichissent l'investigation et ne se substituent jamais au travail de confrontation parcours / ROME.

Dans la candidate `rome-matching-rc3`, les attendus sont lus depuis le snapshot de fiche ROME du métier confirmé. Le connecteur appelle la route GO-11 ROME Fiches métiers `/v1/fiches-rome/fiche-metier/{code}` avec son scope distinct `rome_fiches_metiers_scope`. Le scope doit être renseigné dans la configuration centrale ; aucun scope ni secret réel n’est stocké dans le code ou l’archive. Le connecteur existe mais aucun appel France Travail live n’a encore été exécuté depuis cette candidate.

L’accompagnateur peut cocher plusieurs savoirs/compétences et relier chacun à un ou plusieurs éléments du parcours, puis choisir le statut après l’échange. Pour chaque attendu ROME, il consigne également le niveau d’exercice discuté avec le bénéficiaire : 1 — pratique encadrée / contribution ; 2 — maîtrise autonome ; 3 — pilotage, expertise ou transmission. Le niveau n’est jamais déduit du poste, du diplôme ou de l’IA ; il peut rester à préciser tant que le statut n’est pas « acquis étayé ». Un acquis étayé exige une preuve de parcours et un niveau discuté. L’ajout en séance permet de qualifier explicitement un emploi, des études (avec ou sans diplôme), une formation, un apprentissage personnel ou un autre élément ; chaque apport est marqué comme tel et reste à confirmer. Les propositions IA sont limitées aux attendus cochés (40 maximum par analyse), structurées, historisées et rattachées à l’empreinte de la fiche/parcours ; toute modification rend l’analyse obsolète. La phase suivante fait remonter une question centrale à la fois pour les points incertains. Avant la comparaison, une action ciblée qui aide à vérifier chaque métier ROME retenu est confiée au bénéficiaire et son retour est débriefé. Les liens de ressources et les API disponibles sont choisis selon la question : aucune API ni ressource particulière ne conditionne l’action. Le bénéficiaire peut enregistrer un brouillon, transmettre la source, la date, ses constats et l’effet sur son projet ; l’accompagnateur débriefe et clôture l’action. Les réponses transmises sont historisées, tandis que le bénéficiaire voit les rapprochements validés en lecture seule. Le connecteur IA utilise l’API Responses avec `store=false`; il transmet la fiche/savoirs sélectionnés et des extraits de travail nécessaires à la comparaison, sans envoyer le fichier CV brut ni le nom de l’organisation.

La ROME Fiches métiers est la source des éléments de métier actuellement chargée par cet écran. Les produits ROME Compétences/Contextes et les API de marché restent à raccorder à leurs usages dédiés lorsque leurs scopes et contrats sont configurés. Les liens d’investigation externes restent nécessaires et visibles au bénéficiaire, même si les API fonctionnent.

## Première boucle livrée dans la candidate

1. En phase 2, l’accompagnateur et le bénéficiaire recherchent le métier dans l’application par intitulé, appellation ou code. L’accompagnateur tente d’abord de charger la fiche du résultat via l’API France Travail Fiches métiers ; si l’API ne répond pas, il peut charger la fiche complète locale datée. La fiche devient une proposition, pas une sélection implicite.
2. L’accompagnateur confirme le choix avec le bénéficiaire, dans la limite de trois métiers actifs. Le chargement seul ne sélectionne pas le métier.
3. En phase 3, l’accompagnateur filtre et coche plusieurs attendus ROME (savoirs, savoir-faire, savoir-être), puis associe chaque ligne à une ou plusieurs expériences. Pour chaque attendu, il discute et enregistre aussi un niveau d’exercice. Il peut également noter un apport de séance séparément.
4. L’IA propose des correspondances et des questions de séance, avec références aux seuls attendus et expériences transmis. L’accompagnateur et le bénéficiaire confrontent les propositions en partage d’écran ; l’accompagnateur choisit le statut final. L’IA ne valide, n’exclut et ne classe personne.
5. La revue est historisée et le résultat validé devient visible dans la vue Bénéficiaire en lecture. Une nouvelle expérience ou une fiche ROME actualisée rend les rapprochements antérieurs à revoir.

6. Lorsqu'un point utile reste incertain, l'accompagnateur peut prescrire une action d'investigation liée au métier ROME. Le bénéficiaire dispose toujours du formulaire de retour et des liens de ressources, sans dépendre de la disponibilité des API de marché ; le retour est repris et débriefé en séance.

Les statuts enregistrables sont « acquis étayé », « à confirmer », « non documenté » et « à développer ». « Acquis étayé » exige au moins une expérience explicitement reliée. Les études sans diplôme, formations et apprentissages personnels sont des sources recevables dès lors qu’ils sont structurés dans le parcours. Les attentes de diplôme des offres ne sont jamais converties en obligation officielle par cette fonction.

**Limites de cette candidate :** la recherche textuelle appelle maintenant les deux opérations officielles d’autocomplétion ROME Métiers (métiers et appellations reliées au métier parent), puis bascule sur l’index local daté de 1 911 fiches si l’API échoue ou ne retourne rien. Le résultat sélectionné est actualisé par l’API Fiches métiers avec son code ROME exact. Le payload réel, les scopes, le résultat d’un appel live et l’analyse IA sur un dossier de recette restent à vérifier. Le bénéficiaire n’a pas de recherche externe à faire pour identifier les 1 à 3 métiers ; après la confrontation, il conserve les actions d’investigation ciblées confiées par l’accompagnateur, avec le questionnaire de retour de l’application.

## Ancrage documentaire

Cette règle précise le rapprochement prévu par le parcours fonctionnel V0.3, les phases de confrontation du projet à la réalité et les tâches d’investigation du bénéficiaire. Elle complète le contrat de données RC3B et la documentation d’intégration France Travail/ROME GO-11. Elle s’applique aux prochaines étapes de réalisation et de recette RC3H/GO-22.
