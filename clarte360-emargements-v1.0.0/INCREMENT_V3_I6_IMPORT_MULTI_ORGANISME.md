# CLARTÉ360 — GESTION DES ACTIONS V3
## Incrément I6 — Import générique + multi-organisme

Version : **3.0.0-I6** — cumulative **I1 + I2 + I3 + I4 + I5 + I6**.

## Objectif
Supprimer la dépendance visible à des bases nommées « GESTION OF CLARTE360 » ou « GESTION OF ADCA » et faire de la source d'import un paramètre de l'organisme.

## Modèle de données additif
Ajout de `organization_import_profiles` :
- profil rattaché à un organisme ;
- code et nom du profil ;
- type de source ;
- colonne clé du numéro d'action ;
- onglet action ;
- onglet participants ;
- mapping JSON des colonnes ;
- configuration JSON future ;
- activation/désactivation ;
- audit des créations et modifications.

Aucune table V2/V3 antérieure n'est supprimée.

## Import Excel générique
`excel_import.py` dispose maintenant d'un moteur `read_action_xlsm(...)` piloté par le profil de l'organisme.

Le mapping standard reste compatible avec la structure historique CONV ADM / STAGIAIRE, mais chaque champ peut être remappé sans modifier le code.

Exemples de champs remappables :
- intitulé ;
- client ;
- durée ;
- intervenant ;
- dates ;
- contacts client ;
- nom/prénom/date de naissance/email/téléphone des participants.

Les anciens lecteurs `read_clarte360_xlsm()` et `read_adca_xlsm()` sont conservés uniquement comme compatibilité interne et pour les tests historiques. Ils ne structurent plus l'interface utilisateur.

## Source persistante et copie instantanée
`source_store.py` accepte maintenant des identifiants de source génériques, par exemple `PROFILE_12`.

Chaque profil possède sa propre copie de travail :
- fichier chargé depuis le navigateur ; ou
- chemin serveur / volume monté ;
- copie instantanée avant lecture ;
- fichier d'origine non verrouillé ;
- conservation du chemin pour des imports successifs.

Les sources de deux profils différents ne partagent jamais le même fichier physique de travail.

## Interface Administration
La navigation affiche maintenant **Importer une action**.

L'écran d'import :
1. choisit l'organisme ;
2. choisit le profil d'import actif de cet organisme ;
3. utilise la copie mémorisée ou permet de charger une nouvelle base ;
4. recherche le numéro d'action selon la colonne clé configurée ;
5. préremplit la nouvelle action avec l'organisme correspondant.

Le CSV participants reste disponible.

Les anciens onglets visibles « Base GESTION OF CLARTE360 » et « Base GESTION OF ADCA » ont été supprimés.

## Paramètres organisme
L'onglet **Organisme** permet désormais de créer et gérer plusieurs organismes dans la même instance.

Un nouvel onglet **Imports** permet, par organisme :
- de créer plusieurs profils d'import ;
- de définir clé et onglets ;
- de personnaliser le mapping JSON ;
- d'activer/désactiver un profil ;
- de mémoriser un chemin serveur ;
- d'actualiser la copie de travail.

## Compatibilité Clarté360 existante
Au premier démarrage, si l'organisme principal ne possède aucun profil, un profil générique « Base de gestion principale » est créé avec la clé historique `NO_CLAR`.

Si une copie de travail historique `CLARTE360` existe déjà, ses métadonnées sont reprises sous le nouveau profil générique sans supprimer l'ancienne entrée.

Cette migration est additive et idempotente.

## Isolation multi-organisme
- les profils d'import sont obligatoirement rattachés à un organisme ;
- l'action importée reprend l'`organization_id` du profil ;
- l'import CSV refuse de rattacher des participants à une action appartenant à un autre organisme que celui sélectionné ;
- les chemins et snapshots sont isolés par profil.

## Hors périmètre I6
Microsoft Teams / Graph reste intégralement hors périmètre. Aucun objet Teams, permission Microsoft ou secret n'est ajouté.
