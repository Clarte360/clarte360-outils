# Clarté360 Émargements & Qualité — V2.2 Lot 2
## Bénéficiaires permanents + portail documentaire

Base technique : V2.2 Lot 1 fournie par l'utilisateur. Le dossier historique de déploiement reste `clarte360-emargements-v1.0.0`.

## Réalisé

### Identité bénéficiaire permanente
- Nouvelle table `beneficiaries` avec identifiant interne permanent `BEN-...`.
- Lien additif `participants.beneficiary_id` : une participation reste liée à son action, l'identité permanente peut regrouper plusieurs participations.
- Recherche par Nom + Prénom + Date de naissance avec score de proximité pour détecter les petites différences d'orthographe.
- Aucune fusion automatique : toute correspondance probable doit être confirmée par l'administrateur.
- Création d'un nouvel espace uniquement si date de naissance et email personnel valide sont renseignés.
- Case « Créer / rattacher un espace personnel au stagiaire » décochée par défaut lors de l'ajout d'un participant.

### Espace bénéficiaire
- Invitation par email avec lien temporaire.
- Création du mot de passe par le bénéficiaire.
- Connexion par email + mot de passe, sans faire de l'email l'identité métier.
- Changement d'email sans recréer la personne ni perdre son historique : la nouvelle adresse ne devient l'identifiant de connexion qu'après validation du lien envoyé à cette nouvelle adresse.
- Portail avec rubriques : Accueil, Mes formations / accompagnements, Mon planning, Mes documents administratifs, Documents de cours, Mes questionnaires / actions à réaliser, Mes archives / téléchargements.
- Téléchargement ZIP de l'espace documentaire disponible à tout moment.

### Portail documentaire
- Stockage physique hors SQLite dans `data/documents/blobs`.
- Déduplication stricte par SHA-256 du contenu.
- Deux noms différents pour un contenu identique créent deux références logiques mais une seule copie physique.
- Suppression physique uniquement lorsque la dernière référence logique active disparaît.
- Catégories initiales : `COURS` et `ADMINISTRATIF`.
- Documents d'une action visibles par tous les bénéficiaires de cette action disposant d'un espace.
- Dépôt rapide administrateur par simple numéro d'action depuis le tableau de bord.
- Dépôt depuis l'onglet Documents de l'action.
- Dépôt par l'intervenant uniquement lorsque l'administrateur lui a accordé le droit correspondant.
- Types de fichiers autorisés et limite de 25 Mo par fichier dans ce lot.
- Compteur de stockage physique et de références logiques visible dans l'administration.

### Interface / sécurité
- Les espaces bénéficiaires sont routés séparément de l'administration et de l'espace intervenant.
- Aucune action d'administration n'est exposée dans le portail bénéficiaire.
- Les changements d'identité, rattachements, invitations, changements d'email, dépôts, suppressions et exports ZIP sont journalisés.
- Le contrôle anti-DeltaGenerator du Lot 1 reste présent et la recherche des motifs Streamlit problématiques ne retourne aucun nouveau cas dans `app.py`.

## Migrations
Les migrations sont additives : nouvelles tables, colonnes et index. Aucune table V2.1.4 / Lot 1 n'est reconstruite ou vidée.

Tables ajoutées :
- `beneficiaries`
- `beneficiary_portal_accounts`
- `beneficiary_password_resets` (socle réservé pour la suite)
- `stored_files`
- `document_references`

Colonnes ajoutées notamment :
- `participants.beneficiary_id`
- `trainers.can_upload_documents`
- `beneficiary_portal_accounts.pending_email`

## Tests
Commande : `python3 -m pytest -q`

Résultat final : **63 tests réussis sur 63**.

Le Lot 2 ajoute 7 tests couvrant :
- création et rattachement d'une identité permanente ;
- détection de correspondance sans fusion automatique ;
- invitation / activation / connexion portail ;
- changement d'email avec vérification ;
- déduplication SHA-256 entre plusieurs actions ;
- visibilité d'un document d'action dans le portail du bénéficiaire ;
- ZIP du portail et suppression physique uniquement après disparition de la dernière référence.

## Volontairement réservé au Lot 3
- génération automatique, quelques heures après clôture, du dossier documentaire final stagiaire ;
- intégration automatique des feuilles d'émargement, certificats et évaluations qualité dans ce dossier ;
- transmission automatique au client et choix des destinataires ;
- PDF qualité professionnels définitifs et envoi indépendant de l'évaluation à froid ;
- refonte du pilotage qualité direction ;
- politique de fin de vie / avertissement et purge du portail après 12 mois sans nouvelle action.

Ces éléments s'appuieront sur le socle bénéficiaire et documentaire créé dans ce Lot 2.
