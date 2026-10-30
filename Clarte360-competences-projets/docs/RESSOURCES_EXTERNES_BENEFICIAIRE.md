# Ressources externes pour les investigations du bénéficiaire

Statut : intégrées à l’espace bénéficiaire de la candidate GO22 RC3H.

## Principe de parcours

Les ressources externes aident le bénéficiaire à réaliser une investigation qui
lui a été confiée : explorer un métier, comparer des offres, vérifier un marché
territorial, préparer une enquête auprès d'une entreprise, rechercher une
formation ou vérifier une certification. Elles ne constituent pas une liste de
tâches à accomplir systématiquement.

Les liens restent accessibles même si une API France Travail fonctionne. Ils
restent également utilisables quand une API est absente, indisponible ou ne
fournit pas l'information recherchée. L'accompagnateur choisit avec le
bénéficiaire la vérification utile et la ressource adaptée.

Après la recherche, la trace attendue est : source consultée, date, information
apprise et effet sur le projet (confirmé, modifié ou encore à vérifier). Le
bénéficiaire rapporte ses constats en séance ; une page externe ne valide pas le
projet à sa place.

## Accès dans l'application

- `Mes actions` donne accès à l'ensemble des ressources, sous trois rubriques.
- La phase 2 `Les métiers étudiés` affiche les liens métiers et offres.
- La phase 5 `Vérifier la réalité` affiche les liens territoire et entreprises.
- La phase 8 `Mon plan d'action` affiche les liens formation et certification.

Les ressources complètent l'action confiée. L'interface précise qu'il ne faut
consulter que les sources utiles à cette action.

## Catalogue des liens

| Besoin d'investigation | Ressource | URL |
|---|---|---|
| Découvrir un métier, ses activités et accès | MétierScope — France Travail | https://candidat.francetravail.fr/metierscope/ |
| Explorer les métiers et parcours associés | Onisep | https://www.onisep.fr/recherche/metiers |
| Comparer des offres réelles | Offres d'emploi — France Travail | https://candidat.francetravail.fr/rechercheoffre/emploi |
| Observer emploi et recrutements sur un territoire | Data Emploi — France Travail | https://dataemploi.francetravail.fr/emploi/accueil |
| Repérer des entreprises à contacter | La Bonne Boîte — France Travail | https://labonneboite.francetravail.fr/ |
| Rechercher une formation et ses modalités | Offre Info — Réseau des Carif-Oref | https://www.intercariforef.org/outils/recherche-offreinfo |
| Trouver une certification et ses correspondances | Certif Info — Réseau des Carif-Oref | https://www.intercariforef.org/outils/recherche-certifinfo |
| Vérifier RNCP, Répertoire spécifique et validité | France compétences | https://www.francecompetences.fr/recherche-resultats/ |
| Rechercher un organisme de formation | QuiForme — Réseau des Carif-Oref | https://www.intercariforef.org/outils/recherche-quiforme |
| Repérer une formation en apprentissage | Catalogue apprentissage | https://catalogue-apprentissage.intercariforef.org/recherche/formations |

Les URL proviennent du PowerPoint de ressources externes bénéficiaire daté du
18 octobre 2026. Les liens sont ouverts directement depuis les boutons de
l'application ; ils ne dépendent pas du raccordement API.

## Souscriptions et raccordements API France Travail

Le parcours fonctionnel V0.3 prévoit l’usage de ROME 4.0, des Offres d’emploi
et du Marché du travail pendant l’exploration et la confrontation à la réalité.
Il recommande La Bonne Boîte pour préparer les enquêtes et les contacts
d’entreprises. La capture du portail du 23/10/2026 confirme sept produits
souscrits dans l’application Clarté360 :

- ROME 4.0 — Métiers.
- ROME 4.0 — Compétences.
- ROME 4.0 — Contextes de travail.
- ROME 4.0 — Fiches métiers.
- Marché du travail.
- Accès à l’emploi des demandeurs d’emploi.
- La Bonne Boîte v2.

L’API Accès à l’emploi des demandeurs d’emploi complète le Marché du travail
par des taux statistiques d’accès à l’emploi à six mois selon le métier
recherché, avec des filtres de territoire, de période, de catégorie et de
durée. France Travail définit ici l’accès à l’emploi comme un emploi d’au moins
un mois dans les six mois suivant l’inscription, pour les catégories A ou B.
Cette donnée peut nourrir une investigation de faisabilité en phase 5 puis la
comparaison en phase 6, lorsqu’elle répond à une question du bénéficiaire. Elle
décrit une population et une période données ; elle ne constitue jamais une
estimation des chances individuelles du bénéficiaire.

Documentation de référence : [fiche de l’API sur data.gouv.fr](https://www.data.gouv.fr/dataservices/api-acces-a-lemploi-des-demandeurs-demploi)
et [documentation technique France Travail](https://francetravail.io/data/api/acces-emploi-demandeurs-emploi?doc-section=api-doc-section-stats-d-acc%C3%A8s-%C3%A0-l-emploi-des-demandeurs-d-emploi-cat%C3%A9gories-a-et-b-%28acc_1%29&tabgroup-api=documentation).

« ROME 4.0 — Substitutions d’entités » et « ROME0 v2 » ne sont pas retenus
dans le périmètre V1 actuel.

L’API Offres d’emploi reste une dépendance souhaitée du parcours, mais France
Travail indique qu’elle n’est plus exposée dans le catalogue et que les
organismes doivent demander l’accès via son formulaire de contact. Le lien
direct de recherche d’offres demeure donc présent pour le bénéficiaire.

Les API ne font pas de choix de métier à la place du bénéficiaire. Le ROME
actualisé fournit des références pour soutenir une exploration accompagnée.
La capture du portail du 23 octobre 2026 confirme ces sept souscriptions. Elle
ne suffit pas à vérifier les scopes, la configuration des secrets dans
l’instance de recette ni le succès d’appels réels.

## Limites de cette candidate

- Les liens externes sont intégrés dans l'interface bénéficiaire.
- Le client technique ROME livré dans cette candidate ne couvre encore que
  l'interrogation d'un métier par son code.
- Les sept produits sont souscrits dans le portail. Pour l’API Accès à l’emploi,
  la route d’appel et le scope effectif doivent encore être relevés dans le
  portail développeur authentifié avant de développer le connecteur et de
  réaliser un appel réel. La documentation officielle décrit le produit et ses
  filtres, mais la route de service n’est pas exposée dans sa fiche publique.
- Les scopes des produits réellement raccordés et la configuration de
  l’instance de recette doivent être vérifiés avant tout appel réel.
- Les actions hors séance sont proposées par l’accompagnateur lorsque la recherche
  peut réduire une incertitude ou aider le bénéficiaire à décider. Les liens seuls
  ne remplacent pas le retour daté et son débrief en séance.
