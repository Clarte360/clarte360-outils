# D5 GO30 — mise en service web sur le VPS Clarté360

## Version

Candidate `0.4.30-go30-dual-candidate`, application Python dont le point d’entrée web est `app.py`. La candidate n’est pas encore installée ni validée GO30. Le lanceur de démonstration locale a été retiré de la copie GitHub de travail.

## Référence de déploiement

Exécuter la procédure déjà définie dans le document **FW VPS** pour le VPS Clarté360. Ce document est la référence pour les chemins d’installation, DNS, service systemd, secrets, reverse proxy HTTPS, contrôles et retour arrière. L’adresse prévue pour l’application est `https://competences-projets.clarte360.com`.

La mise en service doit raccorder D5 à Gestion des Actions par CP_V1 et au bridge GDA réellement en place. Les secrets correspondants sont configurés sur le VPS seulement ; aucune clé ne doit être copiée dans le dépôt ou dans un ticket.

## Vérifications avant de déclarer le service opérationnel

1. Confirmer que le DNS résout vers le VPS prévu et que le certificat HTTPS est valide.
2. Vérifier que le service D5 démarre `app.py`, écoute uniquement selon la configuration FW VPS et répond par le reverse proxy HTTPS.
3. Depuis Gestion des Actions, lancer D5 pour une action fictive prescrite ; vérifier le refus pour une action non prescrite et pour un intervenant non affecté.
4. Vérifier les contrôles CP_V1/GDA, les droits, la sauvegarde des brouillons et les échanges réels de documents.
5. Faire les vérifications navigateur bénéficiaire, intervenant et administrateur décrites dans `MODE_OPERATOIRE_GO30_CP_GDA.md`.
6. Consigner chaque résultat et anomalie. Un test non exécuté reste indiqué comme tel ; ne pas déclarer GO30 validé sans recette terminée et retour arrière vérifié.

Les essais automatisés et la compilation Python vérifient le code localement. Ils ne prouvent pas le fonctionnement de l’application sur le VPS ni les appels réels aux API.
