# GO22 RC3F — C-AV3 raccordée au contrat IA partagé

Date : 23 octobre 2026. Statut : candidate technique non validée. GO21 RC2 demeure le dernier jalon officiellement validé.

## Contrat utilisé

- La configuration réutilise le contrat Clarté360 déjà établi : `[openai] api_key` et `model`, avec `gpt-5-mini` par défaut. La candidate n'introduit pas de nom de secret dédié ni de valeur réelle.
- Appel par l'API Responses, sortie JSON stricte, `store=False`, durée bornée et aucune tentative automatique de répétition.
- L'adaptateur ne charge aucun CV/PDF. Il envoie le jeu de réponses C-AV1/C-AV2 et les références déclarées dans Q, avec leurs éléments d'évidence disponibles.
- Les références citées par la sortie sont vérifiées contre les identifiants présents. Les erreurs n'exposent ni le corps fournisseur ni la clé.

## Règles C-AV1 / C-AV2 / C-AV3 et R1 / R2

C-AV1 puis C-AV2 composent le questionnaire unique préparé et verrouillé par l'accompagnateur. Le bénéficiaire réalise une seule passation, sans IA, et transmet un R1 immuable. C-AV3 est déclenchée par l'accompagnateur après R1, sans deuxième questionnaire. Une revue conjointe crée R2; les modifications rendent toute analyse R1 obsolète. L'analyse lancée sur brouillon R2 reste provisoire jusqu'à confirmation conjointe.

Le garde contre les changements concurrentiels est conservé : si réponses ou sources évoluent durant l'appel, aucun snapshot de résultat n'est écrit. Les analyses persistées contiennent fournisseur, modèle, statut R1/R2, empreinte des entrées, références de sortie, version de consigne, empreinte SHA-256 de sortie et compteurs de jetons disponibles.

## Vérifications et limites

- 212 tests Python : PASS, y compris clients simulés et contrôle d'accès bénéficiaire.
- Compilation et archivage final vérifiés.
- Aucun appel IA réel n'a été réalisé dans ce poste; aucun secret réel n'est fourni. Le raccordement est exercé avec un client Responses simulé.
- SOURCE_LIST/SOURCE_GET et l'import réel Hub/GDA ne sont pas présents dans cette candidate. Les repères manuels ne sont pas qualifiés de sources vérifiées.
- Recette navigateur/VPS, import/synchronisation des six sources prévues, validation métier et suite GO22/GO23+ restent à accomplir avant V0. Aucun déploiement de production, commit, push, ou modification de données GDA n'a été effectué.
