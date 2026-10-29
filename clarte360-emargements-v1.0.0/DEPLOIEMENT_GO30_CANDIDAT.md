# Installation et retour arrière — GO30 candidate coordonnée

Cette procédure concerne uniquement la recette isolée. Elle ne vaut pas validation de déploiement. La candidate GDA RC3 est construite à partir du ZIP RC2 exact; la candidate C&P 0.4.30 vient de la dernière recette locale non déployée.

## Avant installation

1. Vérifier les SHA-256 des deux ZIP et extraire chacun dans un nouveau répertoire de recette. Ne pas remplacer le dossier de production ou le dossier de référence RC2.
2. Sauvegarder la base GDA, les fichiers de documents, les deux applications, les secrets et la configuration Nginx. Noter les versions/services actifs.
3. Vérifier que les domaines HTTPS de recette pointent vers le VPS de recette et que les ports du bridge (8765), GDA et C&P ne sont pas exposés directement sur Internet.
4. Dans le coffre de secrets, renseigner une clé CP_V1 de recette d’au moins 24 caractères identique dans les deux applications; définir `GESTION_ACTIONS_CONNECTOR.API_BASE_URL` côté C&P. Ne jamais mettre la clé dans le navigateur, le dépôt, le ZIP ou un ticket.

## Mise en service de la recette

1. Installer les dépendances selon les `requirements.txt` livrés dans chaque candidate.
2. Configurer le service GDA bridge depuis `integration/cp_v1/clarte360-cp-bridge.service.example`; vérifier `CP_GDA_BIND=127.0.0.1`, le chemin des secrets et les droits d’écriture du stockage documents.
3. Ajouter la route HTTPS de recette issue de `integration/cp_v1/nginx-location.example`, proxyfiée vers `127.0.0.1:8765`. Valider la configuration Nginx avant rechargement.
4. Démarrer le bridge, puis GDA et C&P avec leurs fichiers de configuration de recette. Vérifier les health checks, journaux et accès par navigateur.
5. Créer des données fictives sur deux actions; activer le droit d’outil de recette et prescrire une seule des deux actions. Vérifier tous les tests du mode opératoire joint avant d’utiliser une donnée réelle.

## Retour arrière

1. Arrêter les trois services de recette et le proxy dédié à la recette.
2. Restaurer les fichiers/configurations sauvegardés; désactiver ou retirer le service bridge et sa route HTTPS.
3. Restaurer la sauvegarde de base si des écritures de recette ont été faites. Ne pas restaurer la base de production avec une sauvegarde de recette.
4. Redémarrer le socle précédemment déployé et vérifier la page de santé et les journaux. Le retour à RC2 ne doit pas réutiliser la base modifiée sans restauration/contrôle, car la recette produit des événements et documents.

Le déploiement réel reste à effectuer par l’administrateur VPS. L’installation et le rollback ci-dessus n’ont pas encore été exécutés sur le VPS.
