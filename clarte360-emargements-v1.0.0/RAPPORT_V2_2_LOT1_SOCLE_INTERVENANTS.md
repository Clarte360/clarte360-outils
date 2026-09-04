# Clarté360 Émargements & Qualité — V2.2 Lot 1

## Base
Développement réalisé exclusivement à partir du ZIP V2.1.4 fourni, en conservant le dossier historique `clarte360-emargements-v1.0.0`.

## Contenu du lot 1

### 1. Socle UI / DeltaGenerator
- Suppression des deux constructions Streamlit conditionnelles identifiées comme susceptibles de rendre un objet interne dans l'interface.
- Remplacement par des blocs `if/else` explicites.
- Test de non-régression statique ajouté pour empêcher le retour des motifs connus.

### 2. Espace intervenant authentifié multi-actions
- Tableau de bord limité aux actions affectées à l'intervenant connecté.
- Affichage : action, intitulé, client, prestation, modalité, lieu, période, statut, prochaine séance et nombre de participants.
- Calendrier complet par action avec état des signatures, absences et contresignature.
- Vue opérationnelle intégrée au portail authentifié : QR, suivi des participants, absence, remise en attente, relance email et contresignature.
- Les anciens liens opérationnels par token liés à un intervenant exigent désormais la session authentifiée correspondante.

### 3. Codes personnels participants
- L'intervenant peut afficher le code personnel uniquement pour un participant de sa propre action.
- Consultation journalisée.
- Renvoi par email journalisé.
- Régénération séparée, volontaire et protégée par une confirmation explicite ; l'ancien code est invalidé.
- Les nouveaux codes sont conservés sous forme chiffrée/authentifiée pour permettre une récupération autorisée ; le hash existant reste utilisé pour l'authentification QR.
- Pour un code V2.1.4 historique dont seule l'empreinte existe, le programme ne tente pas de casser le hash : une régénération volontaire est nécessaire une fois.

### 4. Invitation / accès / mot de passe intervenant
- Invitation initiale et renouvellement conservés.
- Ajout de « Mot de passe oublié ».
- Lien de réinitialisation temporaire et à usage unique.
- Réponse neutre à la demande de réinitialisation pour ne pas révéler l'existence d'un compte.
- Désactivation conservant l'historique.
- Journalisation des étapes sensibles.

### 5. Remontées intervenant
- Formulaire par action : observation, difficulté, incident, problème logistique, besoin de contact ou autre.
- Objet et description obligatoires.
- Pièce jointe facultative (types limités, 10 Mo maximum).
- Option d'alimentation du suivi qualité ; création d'un point qualité ouvert lorsque choisie.
- Historique visible par l'intervenant.
- Vue administrateur avec statut NOUVEAU / EN_COURS / TRAITE et téléchargement de la pièce jointe.

### 6. Questionnaire qualité intervenant
- Présence dans l'espace action lorsque la campagne existe.
- Accès direct au questionnaire depuis le portail.
- État complété / non disponible clairement affiché.

## Migrations additives
- `participants.pin_recovery_cipher`
- `trainers.reset_requested_at`
- table `trainer_password_resets`
- table `trainer_reports`
- index associés

Aucune table existante n'est supprimée ni reconstruite.

## Secret
Un nouveau secret facultatif est documenté :

```toml
[security]
participant_pin_key = "..."
```

Si ce secret n'est pas présent, l'application utilise en secours la clé de mise en service `[app].setup_key` déjà existante. Aucun secret réel n'est inclus dans le ZIP.

## Tests
- Suite historique conservée.
- 5 nouveaux tests V2.2 Lot 1.
- Résultat : **56 tests réussis sur 56** avec `python -m pytest -q`.
- Test de migration V2.1.4 -> V2.2 Lot 1 effectué sur une base créée avec l'ancien schéma : action, participant et intervenant préservés ; migration additive OK.
- Compilation Python : OK (`app.py`, `services.py`, `db.py`, `security.py`).
- Recherche statique des motifs Streamlit conditionnels connus : aucune occurrence restante dans `app.py`.

## Limite du contrôle local
Le runtime de cette session ne contient pas le paquet Streamlit ; le serveur Streamlit n'a donc pas pu être lancé ici pour un smoke-test navigateur. La validation d'exécution complète sera effectuée lors de l'installation des dépendances dans l'environnement VPS via `requirements.txt`, conformément à la procédure de déploiement déjà définie.

## Périmètre volontairement reporté aux lots suivants
Le stockage documentaire mutualisé SHA-256, l'espace bénéficiaire permanent et les dossiers automatiques de fin d'action restent hors Lot 1 et seront traités dans les Lots 2 et 3 conformément au découpage validé.
