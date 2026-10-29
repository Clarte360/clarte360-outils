# GO30 — Avis d’intégration Projets & Compétences / Gestion des Actions

Statut : **candidate coordonnée, non déployée, non validée GO30**. La base GDA est exclusivement `clarte360-gestion-actions-v3.0.0-P5-RECETTE-RC2.zip`; la base C&P est la dernière recette locale 0.4.29 GO29, qui n’avait pas été déployée. GO4 n’est pas utilisé.

## Changement d’accès

- Un raccourci distinct **Projets & Compétences** apparaît à droite dans le contexte de l’action pour le bénéficiaire, l’intervenant affecté et l’administrateur.
- Le raccourci bénéficiaire est recalculé pour l’action sélectionnée. Le numéro d’action métier est transmis dans le contexte signé et affiché dans C&P, sans exposer d’identité civile. Une prescription d’une autre action ne l’ouvre pas.
- Sans prescription active, le raccourci affiche un cadenas et sa raison. Une prescription annulée ou une affectation retirée bloque aussi le lancement.
- C&P n’est plus ouvert par **Mes outils Clarté360**. L’ancien lien générique de lancement est refusé pour ce code d’outil.
- Les liens Accompagnateur/Bénéficiaire sont signés CP_V1, temporaires et limités à l’action, au bénéficiaire, à la prescription, au participant et à l’acteur. L’autorisation est revérifiée côté GDA et à la reprise de session côté C&P.
- L’écran Administrateur de l’action expose le statut et l’historique de prescription, et un bouton vérifie la clé (sans l’afficher), le catalogue, le bridge GDA et la page de santé C&P. Il ne donne pas accès au contenu du bilan; les erreurs détaillées restent dans les journaux des services. Les opérations de prescription restent dans la gestion des outils de l’action.
- Les étapes C&P et leurs validations demeurent régies par le parcours A3 déjà présent dans C&P.

## Compatibilité et connexion

Le changement coordonne l’interface GDA et le contrat de lancement CP_V1. Il faut installer les deux candidates comme un même lot. Le côté GDA ajoute `cp_launch.py` et le bridge dans `integration/cp_v1/`; le bridge CP_V1 est requis pour que C&P revalide l’affectation et lise/dépose les documents GDA. Il faut configurer la même clé de signature secrète des deux côtés, l’URL HTTPS GDA côté C&P et l’URL HTTPS C&P dans le catalogue GDA. Aucune valeur de secret n’est incluse dans le package.

L’activation du catalogue est marquée `CANDIDATE_TEST_ONLY`. Elle ne constitue pas une activation de production. La clé, les scopes réels, le reverse proxy, le service bridge, les droits documentaires et la compatibilité avec les versions présentes sur le VPS restent à vérifier avant la recette utilisateur.

## Contrôles requis sur VPS de recette

1. Sauvegarder l’application, la base de données, les secrets et la configuration du proxy; vérifier la procédure de retour à P5-RECETTE-RC2.
2. Installer les deux candidates ensemble dans l’environnement de recette, sans écraser le dossier source d’origine.
3. Configurer les secrets par le coffre prévu; démarrer GDA, le bridge CP_V1 et C&P; vérifier leur état et les journaux.
4. Tester deux actions fictives et un bénéficiaire présent dans les deux actions : prescription sur une seule action, vérification du cadenas dans chaque contexte et interdiction d’accès depuis Mes outils.
5. Tester intervenant affecté/non affecté, administrateur (diagnostic sans lecture du bilan), bénéficiaire; annulation de prescription, expiration et retrait d’affectation.
6. Parcourir les étapes A3, vérifier les étapes verrouillées, les validations, les documents GDA et les trois livrables jusqu’à la synthèse; imprimer/ouvrir la synthèse définitive selon les rôles prévus.
7. Consigner les anomalies, vérifier rollback, puis seulement établir le rapport GO30. Aucun essai réel VPS n’est attesté par ce package.

## Vérification locale

Compilation Python et validation JSON effectuées. Les suites pytest complètes n’ont pas pu être lancées : `pytest` est absent de l’environnement; l’installation a échoué sur les délais de téléchargement du réseau. Aucun chiffre de tests automatisés passés n’est revendiqué pour cette candidate.
