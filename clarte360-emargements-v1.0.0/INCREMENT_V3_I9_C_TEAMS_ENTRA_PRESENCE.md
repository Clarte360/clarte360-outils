# CLARTÉ360 — Gestion des Actions V3
## I9-C — Teams / Microsoft Graph / Entra / Présences

Date : 12/09/2026
Base cumulative : I9-B

## Objectif
Consolider le module Teams existant sans le réécrire : calendrier Clarté360 comme source métier, synchronisation automatique, interfaces orientées métier, identité Microsoft permanente des intervenants et traitement prudent des rapports de présence.

## Livré

### 1. UX Teams par rôle
- Administration : affichage de la prochaine réunion par date et horaires réels.
- Intervenant : date + horaires + rôle métier, sans identifiant de créneau, Entra ID ou Meeting ID.
- Bénéficiaire : lien de réunion et prochaine séance uniquement.
- Le message standard devient : synchronisation automatique, aucune action nécessaire.
- Le bouton manuel est déplacé dans « Administration avancée Microsoft 365 » et devient un outil de secours.

### 2. Identité Microsoft permanente intervenant
Ajout additif sur `trainers` :
- `microsoft_email`
- `entra_user_id`
- `entra_status`
- `entra_last_verified_at`
- `entra_creation_requested_at`
- `entra_creation_requested_by`

L'adresse Teams peut être différente de l'adresse principale Clarté360.

### 3. Recherche avant création
Le worker recherche systématiquement une identité existante dans Entra avant toute invitation.
Aucune création Guest n'est déclenchée silencieusement.
Une création/invitation externe nécessite :
1. demande explicite administrateur ;
2. nouvelle recherche d'un compte existant juste avant l'opération ;
3. `guest_invites_enabled=true` côté secrets VPS.

### 4. Présence Teams
- Les rapports restent une preuve complémentaire.
- Aucun rapport ne crée de signature réglementaire.
- Email Teams exact = rapprochement automatique existant conservé.
- Email différent/non reconnu = aucune attribution automatique.
- L'administration peut confirmer explicitement le rapprochement avec un participant de l'action.
- La confirmation est auditée.

### 5. Non-régression
Le socle I9-B est conservé. Les tables et colonnes I9-C sont additives. Aucun secret Microsoft n'est inclus dans le ZIP.

## Fichiers principaux impactés
- `db.py`
- `services.py`
- `graph_client.py`
- `worker.py`
- `app.py`
- `tests/test_v3_i9_c_teams_identity.py`

## Critères d'acceptation couverts
- organisateur technique central conservé ;
- synchronisation automatique mise en avant ;
- IDs techniques retirés des interfaces utilisateur ;
- identité Microsoft permanente intervenant ;
- aucune création Entra silencieuse ;
- recherche préalable anti-doublon ;
- présence Teams non substitutive à l'émargement ;
- identité Teams différente traitée sans attribution aveugle ;
- isolation des détails techniques des portails bénéficiaire/intervenant.

## Limite volontaire
La validation réelle des permissions Graph, Application Access Policy, rôles coorganizer/Guest et rapports de présence sur le tenant Microsoft reste une recette réelle de fin de cycle. Aucun changement VPS n'est effectué dans ce lot.
