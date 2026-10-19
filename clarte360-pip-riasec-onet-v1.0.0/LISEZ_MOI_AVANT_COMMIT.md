# CLARTÉ360 — PIP RIASEC / O*NET H3.3-D-RC3
## Candidate de clôture technique — 18 octobre 2026

**Livraison complète de PIP uniquement. Non déployée.**
Le ZIP contient un seul dossier applicatif : `clarte360-pip-riasec-onet-v1.0.0/`.
Il ne contient aucune nouvelle version de Gestion des actions ni des autres outils.
Base de travail : archive officielle 75af19dafc22141d7ca3690d5bf6c8778430b89e.

## Ce que Dominique fait maintenant
1. Télécharger puis extraire le ZIP candidat, sans supprimer le ZIP de production.
2. Dans GitHub Desktop, choisir le dépôt `clarte360-outils`, branche `main`, puis « Show in Explorer ».
3. Copier le dossier `clarte360-pip-riasec-onet-v1.0.0` extrait dans la racine de ce dépôt, en fusionnant les dossiers et en remplaçant les fichiers de même nom. Ne pas imbriquer deux dossiers du même nom. Ne pas supprimer le dossier applicatif existant : cela pourrait supprimer des fichiers locaux hors ZIP.
4. Vérifier que les modifications de cette livraison sont toutes sous `clarte360-pip-riasec-onet-v1.0.0/`. Aucun fichier de `clarte360-emargements-v1.0.0/` ne doit provenir de ce ZIP. Ne pas mélanger un autre travail local dans ce commit.
5. Faire le commit puis le push soi-même. Proposition de message : `PIP H3.3-D-RC3 - cloture technique PIP uniquement`.
6. Communiquer le commit créé pour préparer la mise à jour VPS. Ne pas réutiliser les anciennes commandes qui pointent vers 75af19d ou vers la branche de recette historique.

**Aucun commit, push, pull, changement de branche, redémarrage ou déploiement n'a été effectué par l'assistant pour cette livraison.**

## Correctifs inclus
- Publication des PDF accompagnés suivie document par document. Un O*NET complémentaire peut être annoncé sans renvoyer le PIP déjà publié. Le premier PDF PIP est conservé sans régénération.
- Erreur de reprise accompagnée : arrêt explicite, sans création silencieuse d'un questionnaire vierge ni remplacement du rattachement existant.
- Protection contre une session moins avancée et préservation des permissions lors des écritures atomiques. Aucune réparation globale des droits du VPS n'est effectuée.
- Bouton de ressenti utilisable avec « Aucune » ; réponses obligatoires manquantes indiquées ; ressenti accompagné enregistré avant la génération et la transmission.
- E-mail PUBLIC : adresse explicitement affichée, preuve de vérification serveur requise, absence de boucle d'envoi lors des rafraîchissements, relance manuelle bornée (60 secondes / 3 essais). Un JSON modifié ou une preuve serveur absente impose un nouveau code sans effacer les réponses.
- Enregistrement pseudonymisé indépendant de l'e-mail ; pseudonyme conservé entre les sauvegardes ; aucune transmission de résultats PUBLIC à GDA.

## Ce qui reste identique
Questionnaires, calculs, interprétations, modèles PDF, logos et ressources métier : identiques au code source de référence (preuves SHA-256 jointes).
Le choix initial PIP + O*NET conserve le masquage des résultats PIP jusqu'à la fin d'O*NET. Aucun questionnaire de ressenti O*NET n'est ajouté.
Les noms techniques des PDF et le contrat du récepteur GDA sont conservés.
L'ajout tardif d'O*NET est fiabilisé lorsqu'il est accessible dans le parcours existant ; cette livraison ne déverrouille pas les prescriptions terminées dans GDA et n'ajoute pas un nouveau parcours métier.

## Point de vigilance
Le correctif PIP **ne change pas l'historique visible ni les notifications intervenant de GDA**. Voir `docs/release/H33D_RC3_20261018/RESERVES_GESTION_ACTIONS.md`.
Le ZIP ne contient ni données bénéficiaires, ni base de production, ni secrets, ni `.venv`, ni `.git`. Il ne remplace pas une sauvegarde des données.

## Contrôles reproductibles disponibles
`python scripts/verify_release.py` : empreintes des fichiers de livraison, en lecture seule.
`python scripts/recette_cloture.py` : tous les tests PIP dans une copie temporaire et sur données fictives. N'installe rien et n'utilise pas les données du service.
Ces outils sont fournis pour l'exploitation et le futur déploiement ; Dominique n'a pas à les lancer maintenant sur le VPS.
