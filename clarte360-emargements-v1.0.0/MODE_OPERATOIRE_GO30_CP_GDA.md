# GO30 — Mode opératoire de recette humaine CP/GDA

À exécuter sur le VPS de recette après installation des deux candidates et vérification de santé des services. Utiliser des comptes et actions fictifs. Toute erreur bloquante arrête la recette et est inscrite dans le rapport; ne pas poursuivre avec des données réelles.

## Préparation

1. Dans Gestion des Actions, créer deux actions fictives A et B et rattacher le même bénéficiaire fictif aux deux.
2. Affecter l’intervenant 1 à A; ne pas affecter l’intervenant 2 à A. Garder l’administrateur connecté séparément.
3. Vérifier que Projets & Compétences n’est pas prescrit sur A ni B. Pour le bénéficiaire, sélectionner A puis B : le raccourci à droite doit afficher un cadenas dans les deux actions.
4. Dans les secrets de C&P, définir `security.session_timeout_minutes = 60`; vérifier que la configuration active rend une session après au moins 60 minutes sans interaction. Le délai de validité du lien initial (15 min) ne doit pas interrompre une session déjà ouverte. Vérifier aussi que le reverse proxy de C&P garde le WebSocket actif au moins 60 minutes (lecture/écriture configurées à 3 600 secondes ou plus).

## Test 1 — prescription limitée à une action

1. L’administrateur ouvre l’action A, rubrique **Outils Clarté360**, choisit le bénéficiaire fictif puis **Compétences / Projets**, et prescrit.
2. Ouvrir le raccourci Projets & Compétences à droite depuis A : le dossier prescrit doit s’ouvrir.
3. Sélectionner B : le cadenas doit rester fermé. Vérifier qu’aucun bouton C&P ne se trouve dans **Mes outils Clarté360**.
4. Tenter d’ouvrir l’ancien lien générique de lancement de cette prescription : GDA doit le refuser.

## Test 2 — droits intervenant

1. Se connecter avec l’intervenant 1; ouvrir l’action A et Projets & Compétences : le dossier doit s’ouvrir avec son rôle d’accompagnateur.
2. Se connecter avec l’intervenant 2 et tenter l’accès à A : aucune ouverture ne doit être accordée.
3. Dans la préparation C-AV1/C-AV2, modifier une formulation champ par champ, passer aux autres menus puis revenir; vérifier que chaque modification est conservée sur le serveur avant publication. Le bouton de verrouillage/publication doit annoncer que Q ne sera plus modifiable.
4. Après R1, en séance, modifier un champ en C-AV1 puis un en C-AV2; passer d’un onglet à l’autre et revenir. Vérifier la sauvegarde des corrections R2, le retour aux étapes et le maintien de R1 en lecture seule. Tant que les deux parties ne sont pas terminées, la confirmation commune doit rester indisponible. Après confirmation conjointe, vérifier qu’une version R2 distincte est active et qu’une nouvelle correction passe par une version distincte.
5. Retirer temporairement l’affectation de l’intervenant 1, puis retester le lancement : il doit échouer; rétablir ensuite l’affectation.

## Test 3 — droits bénéficiaire et révocation

1. Se connecter comme bénéficiaire, sélectionner A et ouvrir l’espace depuis le raccourci à droite.
2. Vérifier l’action affichée, les étapes A3, les cadenas des étapes non déverrouillées et les icônes d’aide. Aucun code interne ne doit être nécessaire pour comprendre l’action demandée.
3. Vérifier que les cinq repères de progression ont des couleurs pastel distinctes et restent lisibles. Le bénéficiaire ne doit voir que son action sélectionnée.
4. Modifier un choix puis un champ texte en C-AV1; attendre l’indication de sauvegarde, aller à C-AV2 puis revenir à C-AV1. Vérifier que les deux modifications sont revenues du serveur. Refaire le contrôle après une reconnexion.
5. Avant l’envoi, vérifier que les réponses restent modifiables et que les boutons de retour permettent de revenir à C-AV1 depuis C-AV2. Après avoir terminé les deux parties, lire l’avertissement, envoyer R1, puis vérifier que l’écran indique clairement « irréversible » et que les réponses sont en lecture seule.
6. Sélectionner B : aucun accès ne doit être ouvert par la prescription A.
7. Annuler la prescription A et réessayer : l’ouverture doit échouer. Recréer une nouvelle prescription pour poursuivre le test.

## Test 4 — administration et traçabilité

1. Dans l’action A, ouvrir le menu Projets & Compétences de l’administrateur.
2. Dans le menu Projets & Compétences, cliquer **VÉRIFIER LA CONNEXION C&P / GDA**. Vérifier l’état de la clé configurée, du catalogue, du bridge GDA et de la page de santé C&P; aucune valeur de secret ni aucun contenu du bilan ne doit apparaître.
3. Ouvrir le détail de prescription, vérifier les événements et relever l’heure/référence de chaque panne; les traces techniques détaillées se vérifient dans les journaux des services concernés.

## Test 5 — parcours A3, sauvegardes et livrables

1. Depuis A, réaliser la récupération de l’APS selon l’accompagnement prévu, compléter le CV, puis le parcours jusqu’à la synthèse conformément à A3.
2. Dans chaque écran éditable A3 — CV/ROME, investigation et retour, comparaison, décision, plan d’action, résultats, synthèse et suivi — modifier un champ, naviguer vers une étape précédente puis revenir et rouvrir la session. Vérifier la présence du dernier brouillon côté serveur, avant tout partage/finalisation. Une zone restée uniquement dans le navigateur constitue un échec bloquant de sauvegarde.
3. Avant chaque sollicitation C-AV3, CV ou ROME, vérifier que les données qui partiront sont expliquées au bénéficiaire et que la case d’information/accord est nécessaire pour lancer l’appel. Sans coche, le bouton doit rester inactif; aucune sollicitation ne doit partir automatiquement.
4. N’utiliser que des données fictives et un CV synthétique pendant la recette. Vérifier que l’IA ne déclenche aucune validation, aucun score ni classement et que l’intervenant relit les propositions avec le bénéficiaire.
5. Vérifier que l’ordre de conclusion affiche les résultats détaillés avant le plan d’action, puis la synthèse et la clôture; chaque étape dépend de la validation précédente et du rôle attendu.
6. Ouvrir la synthèse définitive comme bénéficiaire puis comme intervenant autorisé; vérifier les contenus, la mise en page et l’impression PDF.
7. Contrôler la remise des documents dans Gestion des Actions, l’historique et le statut de prescription. Relever les anomalies avant de conclure.

## Compte rendu attendu

Pour chaque changement de champ, vérifier le retour « enregistré » avant de quitter l’écran. En cas de perte de connexion, rouvrir le même dossier et vérifier la reprise depuis la dernière version confirmée sur le serveur. Ne considérer aucun champ comme sauvegardé si un message d’erreur ou de conflit est affiché.

Consigner pour chaque test : date/heure, compte-rôle, action, prescription, résultat attendu/obtenu, référence d’erreur et capture si utile. Déclarer séparément les tests non exécutés. GO30 n’est recevable qu’après le ZIP propre, rapport complet, anomalies bloquantes à zéro et rollback vérifié. L’absence de sauvegarde champ par champ dans un écran A3 est une anomalie bloquante tant que cette exigence couvre l’ensemble du parcours.
