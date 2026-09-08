# CLARTÉ360 — Gestion des actions V3
## Incrément I7 — Microsoft Teams / Microsoft Graph

Date : 05/09/2026
Base cumulative : I1 + I2 + I3 + I4 + I5 + I6

## 1. Périmètre livré

I7 introduit le module Teams sans modifier l'URL, les services systemd, le chemin VPS ni les secrets existants.

Le module comprend :
- activation Teams indépendante par action ;
- activation prospective à partir du prochain créneau futur ;
- aucune création rétroactive pour les créneaux passés ;
- modèle de données Teams additif ;
- authentification Graph app-only par certificat ;
- organisateur technique configurable, cible Clarté360 : `teams@clarte360.com` ;
- création d'une réunion Teams d'action avec lien stable comme stratégie cible ;
- occurrences internes rattachées aux créneaux ;
- préparation des rôles intervenants par créneau ;
- invitation Entra B2B optionnelle des intervenants externes ;
- résolution des comptes internes Entra ;
- synchronisation par le worker, indépendante de SMTP ;
- récupération automatique des rapports de présence ;
- rapprochement présence Teams / émargement sans substitution de preuve ;
- affichage du lien dans les espaces intervenant et bénéficiaire ;
- audit des opérations Microsoft sensibles.

## 2. Tables additives

- `teams_action_rooms`
- `teams_occurrences`
- `teams_participant_roles`
- `teams_attendance_reports`
- `teams_attendance_records`
- `teams_sync_events`

Aucune table V2/V3 précédente n'est supprimée.

## 3. Stratégie de réunion

La cible fonctionnelle reste `STABLE_ACTION_LINK` : une réunion Graph est créée au niveau de l'action et les créneaux Clarté360 sont conservés comme occurrences métier distinctes.

Le worker lit ensuite les `meetingAttendanceReports` du meeting et rattache chaque rapport à l'occurrence Clarté360 la plus proche temporellement. Un rapport situé à plus de 12 heures d'un créneau n'est pas rattaché automatiquement.

### Point POC Microsoft encore obligatoire

La documentation Graph confirme qu'un rapport est généré chaque fois qu'une réunion se termine, mais la réutilisation pratique d'un même lien d'action sur plusieurs séances doit encore être validée sur le tenant Clarté360 avec de vraies occurrences. Tant que cette recette réelle n'a pas été faite, le mode lien stable ne doit pas être considéré comme définitivement validé en production.

## 4. Authentification app-only

Le code utilise le flux client credentials Microsoft Entra avec certificat via MSAL.

Valeurs attendues dans `[microsoft_graph]` du `secrets.toml` VPS :
- `tenant_id`
- `client_id`
- `organizer_user_id`
- `organizer_upn`
- `certificate_path`
- `certificate_thumbprint`
- `guest_invites_enabled`
- `stable_link_mode`

La clé privée n'est jamais stockée en base et n'est jamais incluse dans le ZIP/GitHub.

## 5. Permissions Graph à valider / consentir

Permissions applicatives nécessaires à l'implémentation I7 :
- `OnlineMeetings.ReadWrite.All` : création / mise à jour des réunions ;
- `OnlineMeetingArtifact.Read.All` : rapports de présence ;
- `User.Invite.All` : uniquement si l'invitation automatique des Guests externes est activée ;
- `User.Read.All` : résolution des comptes intervenants internes par UPN/email.

Pour les API de réunions/artefacts en mode application, une **Application Access Policy Teams** doit en plus autoriser l'application à agir pour le compte du compte organisateur technique.

## 6. Comportement des intervenants externes

Microsoft Graph n'autorise pas l'attribution du rôle `presenter` / `coorganizer` à une identité qui n'est pas enregistrée dans Entra ID.

I7 prévoit donc :
1. intervenant interne : résolution de son objet Entra ;
2. intervenant externe : invitation B2B Guest si `guest_invites_enabled=true` ;
3. conservation de l'`entra_user_id` dans le rôle Teams ;
4. affectation `COORGANIZER` pour le principal/référent et `PRESENTER` pour le co-intervenant ;
5. journalisation des erreurs ou invitations.

La capacité exacte d'un Guest externe à agir comme co-organisateur, à gérer le lobby et les salles de sous-groupes reste un point de recette réelle Microsoft avant généralisation.

## 7. Bénéficiaires

Les bénéficiaires utilisent le lien Teams depuis leur portail. Ils ne sont pas transformés automatiquement en Guests Entra.

La salle d'attente est configurée de manière prudente : l'organisateur est le seul à la contourner par défaut. L'autorisation effective de rejoindre anonymement dépend également de la politique Teams du tenant et doit être vérifiée lors du POC.

## 8. Présence Teams

Le worker récupère :
- les rapports de présence ;
- les enregistrements de présence ;
- les intervalles entrée/sortie ;
- les durées ;
- l'identité disponible.

Le rapprochement utilise en priorité l'email avec le participant Clarté360.

La règle reste absolue :

> La présence Teams est une preuve complémentaire. Elle ne crée jamais automatiquement une signature d'émargement et ne remplace jamais l'émargement réglementaire.

## 9. Synchronisation planning

Les événements I4 `planning_change_events` déjà marqués `PENDING_I7` sont désormais traités par le worker Teams. Une modification de planning entraîne une resynchronisation de la plage de la réunion et des occurrences internes.

Le worker Graph s'exécute même si SMTP est désactivé.

## 10. Documentation Microsoft officielle utilisée

- Create onlineMeeting : https://learn.microsoft.com/en-us/graph/api/application-post-onlinemeetings?view=graph-rest-1.0
- Application access policy : https://learn.microsoft.com/en-us/graph/cloud-communication-online-meeting-application-access-policy
- Attendance reports : https://learn.microsoft.com/en-us/graph/api/meetingattendancereport-list?view=graph-rest-1.0
- Attendance records : https://learn.microsoft.com/en-us/graph/api/attendancerecord-list?view=graph-rest-1.0
- Create invitation / Entra B2B : https://learn.microsoft.com/en-us/graph/api/invitation-post?view=graph-rest-1.0
- Microsoft Graph permissions : https://learn.microsoft.com/en-us/graph/permissions-reference

## 11. Ce qui n'est volontairement pas activé automatiquement

- enregistrement Teams ;
- transcription ;
- création rétroactive de meetings ;
- activation Teams par simple choix de modalité online/mixte ;
- création automatique d'un Guest pour un bénéficiaire ;
- transformation d'une présence Teams en émargement.

## 12. Recette réelle obligatoire avant production Teams

Le scénario du cahier des charges reste à exécuter sur le tenant Microsoft 365 Clarté360 :
- action online ;
- intervenant interne ;
- intervenant externe Guest ;
- deux bénéficiaires dont un sans compte Microsoft ;
- plusieurs créneaux ;
- déplacement ;
- remplacement ;
- co-animation ;
- lobby ;
- rapports de présence ;
- récupération automatique ;
- rapprochement émargement.

Le développement logiciel I7 est livré, mais cette recette Microsoft réelle nécessite les permissions Entra, le certificat et le tenant de production/test : elle ne peut pas être simulée comme preuve finale.
