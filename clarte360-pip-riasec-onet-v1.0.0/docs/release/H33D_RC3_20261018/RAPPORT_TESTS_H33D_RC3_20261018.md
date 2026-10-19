# Rapport de recette locale — H3.3-D-RC3
Date : 18 octobre 2026. Statut : **candidate préparée et testée localement, non déployée**.

## Base et périmètre
Source : archive officielle OneDrive 75af19dafc22141d7ca3690d5bf6c8778430b89e.
Correctifs PIP seuls. Aucun nouveau commit GitHub, aucun redémarrage VPS, aucun changement de GDA, aucune intervention sur des données réelles.

## Résultats exécutés
- Base avant modification : 210 tests réussis (7,12 s).
- Candidate : **270 tests réussis, 0 échec** (8,04 s lors de la passe consignée).
- Script groupé livré : **270 tests réussis** dans une nouvelle copie temporaire (7,68 s).
- Compatibilité avec une copie jetable du récepteur GDA inchangé : **4 scénarios réussis** (PIP seul ; ajout O*NET après PIP finalisé ; choix initial combiné ; événement déjà traité). Les PDF sont réellement générés et archivés dans des répertoires locaux fictifs ; empreintes et absence de doublons contrôlées.
- 23 fichiers métier/ressources/dépendances comparés byte pour byte : identiques.

## Ce que couvrent les nouveaux tests
Soixante tests ajoutés aux 210 existants : publication par document, complément tardif O*NET, rejeu, publication interrompue, journal incomplet, droits et liens symboliques, intégrité PDF, sauvegarde/lecture refusée, session concurrente moins avancée, identité croisée, 71 réponses restaurées, validation du ressenti, sauvegarde avant erreur, dernière question PIP/O*NET, destinataire PUBLIC, code lié à l'adresse, relances e-mail bornées, séparation des études et du CRM, conservation d'un pseudonyme stable.
Les tests antérieurs ne sont pas supprimés. Cinq fichiers de tests ont été adaptés pour les identifiants de version attendus et la localisation du code après factorisation ; aucun changement de critère métier de notation.

## Limites explicites
Environnement : Python 3.13.5, Linux, pytest ; fonctions d'interface réelles exécutées avec un adaptateur d'interface simulé, pas un navigateur Streamlit.
Aucune connexion à un serveur SMTP réel ni à l'API O*NET, aucun test sur le VPS. Les erreurs de transport sont simulées ; l'acceptation SMTP ne prouve pas la réception dans la boîte de messagerie.
La restauration d'un ancien fichier illisible n'est pas une correction automatique des permissions existantes ; le correctif empêche surtout sa perte par remplacement silencieux.
La lecture/écriture testée est effectuée sur des données synthétiques. L'historique documentaire réel et les notifications intervenant GDA restent hors périmètre.

## Contrôle final après le push de Dominique et le déploiement autorisé
Confirmer le chargement RC3 et le service PIP ; une reprise accompagnée normale conservant les réponses ; un rapport final accompagné accessible ; un envoi PUBLIC vers une adresse vérifiée réelle et une seule sauvegarde statistique pseudonymisée. Aucun nouveau test complet de 132 questions n'est requis pour revalider les mécanismes déjà automatisés.
La comparaison ou réparation d'un fichier de production n'est pas exécutée par ce paquet.
