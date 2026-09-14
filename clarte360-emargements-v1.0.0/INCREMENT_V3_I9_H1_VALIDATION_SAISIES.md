# I9-H1 — Validation exhaustive des champs de saisie

## Objet
Durcissement transversal de la candidate I9-H afin d'empêcher l'enregistrement de valeurs structurellement incompatibles avec leur champ, tout en conservant la souplesse nécessaire aux champs libres.

## Règle retenue
Les contrôles sont réalisés au niveau des services métier, pas seulement dans l'interface. Une donnée invalide ne peut donc pas contourner l'interface par un import ou un appel interne.

## Champs structurés couverts
- nom / prénom / nom de naissance / nom complet : lettres Unicode, espaces, apostrophes et tirets uniquement ; chiffres, balises, emoji et symboles refusés ;
- e-mails : syntaxe locale + domaine complet, espaces et injections d'en-têtes refusés ;
- téléphones : caractères téléphoniques usuels uniquement, 6 à 15 chiffres, signe + uniquement en tête ;
- dates de naissance : vraie date, jamais future, limite de plausibilité 120 ans ;
- dates d'action : date de fin >= date de début ;
- créneaux : date et heures valides, début différent de fin ;
- numéros d'action : lettres/chiffres et séparateurs . _ / - uniquement ;
- codes techniques/profils : caractères contrôlés ;
- SIRET : 14 chiffres ;
- NDA : 11 chiffres ;
- NAF : 4 chiffres + 1 lettre ;
- TVA intracommunautaire : préfixe pays + identifiant alphanumérique ;
- code postal : format alphanumérique international raisonnable ;
- URL : http/https obligatoire ;
- fuseau horaire : identifiant IANA valide ;
- JSON de mapping/configuration : objet JSON valide uniquement ;
- durées/effectifs/rétention : bornes numériques contrôlées ;
- contacts client / expéditeur / Microsoft Teams : validation e-mail centralisée ;
- CRM / intervenants / bénéficiaires / participants / organismes / agences : mêmes règles métier partagées.

## Champs libres
Les observations, descriptions, adresses et notes restent volontairement libres en ponctuation, mais sont protégées par :
- longueur maximale ;
- refus des caractères de contrôle ;
- requête SQL paramétrée côté stockage.

## UX
Pour les écrans principaux (action, participant, organisme, agence, administrateur, intervenant, contacts client), les erreurs de format sont renvoyées comme messages métier compréhensibles et ne doivent pas produire de traceback utilisateur.

## Non-régression
- suite historique complète conservée ;
- nouveaux tests de validation et d'entrées malveillantes ;
- compilation Python complète ;
- release_check vert.
