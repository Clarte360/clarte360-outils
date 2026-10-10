# CLARTE360 Gestion des Actions - P1 droits et documents - RC1

Statut: VERSION CANDIDATE A RECETTER LOCALEMENT. PAS UNE AUTORISATION DE DEPLOIEMENT.
Origine: archive officielle `clarte360-gestion-actions-v3.0.0-INTERVENANTS-RC2-2-2-RC2.zip`, commit `a7094c4ad6cf3694ac4fa42c79448693f570769d`.

## Perimetre P1
- Les supports de cours non nominatifs restent partages une seule fois entre tous les inscrits de la meme action.
- Les rapports individuels et PDF PIP/NEO sont restreints au beneficiaire concerne et a l'intervenant referent de l'action.
- Le QAP individuel prepare pour la suite reste visible aux intervenants actifs affectes a l'action; son questionnaire complet et le perimetre multi-formateurs seront figes au jalon metier suivant.
- Contrats et autres pieces administratives non individuelles non visibles dans les portails beneficiaire/intervenant.
- Les droits sont recontroles pour le telechargement et les ZIP, pas seulement pour l'affichage.
- Les depots des portails sont verifies cote service (compte, role, action, personne, droit de depot).
- Les pieces supprimees depuis l'administration sont archivees logiquement, sans effacement physique dans P1.
- Les anciens lots finaux clients ne sont pas reutilises : le worker regenere exclusivement les justificatifs formation autorises.
- Les reponses individuelles de satisfaction a froid ne sont plus envoyees telles quelles au client; anciennes taches COLD bloquees au worker.
- Migration additive pour garantir la colonne `trainers.can_upload_documents` en base neuve comme en base preexistante.

## Compatibilite et limites
- Les fichiers de code et les migrations existantes sont conserves; aucun schema de production n'a ete touche.
- Les traitements Microsoft Teams/Graph, l'emargement, les signatures et qualifications intervenants restent dans la base du package.
- Les evolutions documentaires avancees (progression de depots, versions/publication, anti-doublons logiques, cycle legal RGPD et revue multi-formateur QAP) restent au P2/P5.
- Espace Client reel, contrats CRM17 et integration GO-14 restent hors P1.
- Les fonctions automatiques de purge reglementaire et les exceptions de consultation doivent etre arretees juridiquement avant un futur deploiement.
- La campagne pytest locale complete a reussi : 538/538, dont 17 tests specifiques P1. Teams/Graph et SMTP en conditions reelles restent non recetes.

## Livraison
Ce ZIP est l'archive applicative complete de P1, SANS les bases, fichiers documents, images signatures, journaux, donnees d'usage, sauvegardes ni secrets.
Le dossier runtime `data/` doit etre conserve et sauvegarde sur le VPS : NE JAMAIS le remplacer par le dossier vide de ce ZIP.
Le nom du ZIP n'est pas l'identite du deploiement. Application existante: `emargements.clarte360.com` port 8501, service `clarte360-emargements.service`.
Tout passage VPS exige autorisation distincte du proprietaire, protocole de restauration isolee et controle Framework VPS V1.4.
GitHub Desktop, commit et push restent exclusivement sous le controle du proprietaire.
