# GO22 RC3I — cartes de parcours en phase 0

Date : 24 octobre 2026  
Candidate : `0.4.4-go-work-rc4`  
Statut : développement local contrôlé ; GO22 reste ouvert et non validé.

## Parcours ajouté

En phase 0, l’accompagnateur peut maintenant créer un apport de parcours discuté en séance, avant la sélection d’un métier ROME. Il peut ensuite compléter et enregistrer chaque carte : nature (emploi, études, formation, apprentissage personnel ou autre), dates, structure, contexte, activités ou contenus étudiés, autonomie, résultats, outils et savoirs mobilisés.

Les études sans diplôme sont expressément recevables comme source de savoirs. Le niveau d’exercice 1/2/3 décrit une expérience précise et se choisit à partir des faits. Le titre du poste ne détermine pas ce niveau. La phase 0 ne peut être validée que si chaque carte active a été explicitement relue avec le bénéficiaire ; une carte ajoutée comme apport de séance reste « à confirmer » jusqu’à cette relecture.

Les cartes modifiées sont historisées. Tout rapprochement ROME déjà enregistré devient à revoir après modification des éléments du parcours. Si une phase déjà validée dépend de ces éléments, le parcours et les phases de rapprochement/conclusion concernées sont réouverts. Les cartes restent cachées dans l’interface bénéficiaire tant que la phase 0 n’est pas de nouveau validée ; après validation, le bénéficiaire dispose d’une carte détaillée en lecture seule.

Les accès restent limités au dossier et au rôle accompagnateur, et l’événement d’écriture ne contient que des métadonnées minimales.

## Frontière documentaire

Cette fonction n’importe pas un CV et ne prétend pas lire un document GDA. Le document source reste dans l’espace commun ; aucune copie binaire n’est créée. Les éléments saisis sont des apports C&P issus de l’échange. La sélection/listage/ouverture/dépôt GDA et le lien manuel entre document et besoin restent à intégrer selon le protocole GO14, aux jalons GO27/28. Cette séparation est présentée dans l’écran.

## Vérifications

- AppTest : visibilité de la limite GDA et de l’expérience existante.
- AppTest : ajout d’une carte d’études sans diplôme en phase 0, avant ROME.
- Gate de progression : une carte non relue bloque la validation de la phase 0.
- Projection Bénéficiaire : carte cachée avant validation de la phase 0, puis détails visibles en lecture seule après validation.
- Test métier : édition, niveau discuté, relecture explicite, provenance conservée, version historisée, réouverture du parcours et invalidation de la revue ROME.
- Suite complète : 252 tests passés.
- `python -m compileall -q clarte360_cp` : réussi.

Ces résultats locaux ne remplacent pas le test réel des API IA/France Travail, le raccordement Gestion des Actions/Hub, la recette navigateur et VPS ni la validation métier. Aucun GO n’est déclaré validé par cette note.
