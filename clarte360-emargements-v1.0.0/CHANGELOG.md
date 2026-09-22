## 3.0.0-I9-J2C-PIP-LIAISON-I-CRM0-RC2 — 2026-09-19
- CRM-0 : fiche plus compacte avec onglets Fiche / Notes & tâches / Actions liées / Timeline.
- Ajout d’actions directes Ouvrir/Modifier et Supprimer sur la liste des contacts.
- Suppression sécurisée d’une fiche CRM et de son contenu CRM uniquement ; les actions, bénéficiaires et études PIP/O*NET sont préservés.
- Notes supprimables ; tâches modifiables, terminables et supprimables.
- Liaison à une action existante réversible sans supprimer l’action.
- Correctif « Créer une action pour ce contact » : navigation différée via _next_nav pour éviter l’incident Streamlit de session_state.
- Conservation des correctifs RC1 marketing_opt_in -> marketing_consent et centres d’intérêt PIP PUBLIC.

## 3.0.0-I9-J2C-PIP-LIAISON-I-CRM0-RC1 — 2026-09-19
- Correctif marketing PIP PUBLIC (`marketing_opt_in` -> consentement CRM).
- Centres d’intérêt PIP PUBLIC conservés/visibles.
- CRM-0 : fiche prospect, notes, tâches, timeline et actions liées.
- Recherche/création CRM lors de la création d’une action.

## 3.0.0-I9-J2C-PIP-LIAISON-I-RECETTE-FINALE — 2026-09-18
- Candidate finale construite exclusivement depuis le Jalon H validé.
- Aucun changement fonctionnel : gel du code après intégration PIP H.
- Recette locale complète : 358 tests historiques et nouveaux réussis, 0 échec.
- Recette ciblée liaison PIP A à H + RC8 : 62 tests réussis, 0 échec.
- Contrôles compilation/imports principaux réussis.
- Contrat PIP/Gestion des Actions V1 conservé ; aucune modification du programme PIP, Calendar ou Teams.
- Limite d'intégration externe maintenue : l'émission PUBLIC signée et le transfert automatique des PDF doivent être activés côté chantier PIP avant recette bout-en-bout VPS.

## 3.0.0-I9-J2C-PIP-LIAISON-H-INTEGRATION — 2026-09-18
- Intégration finale côté Gestion des Actions avec le contrat observé du PIP Jalon E1.
- Jeton Hub enrichi du vocabulaire `scopes/tool_id/hub_source/return_mode` sans retirer `rights`.
- Routage unifié des événements PUBLIC et ACCOMPAGNEMENT ; enveloppe HMAC cible.
- Support documentaire séparé PIP / O*NET par prescription.
- Documentation du contrat V1 et alignement des chemins persistants PIP.

# 3.0.0-I9-J2C-PIP-LIAISON-G-ETUDES — 2026-09-18

- Reprise exclusive du jalon F PDF/DOCUMENTS.
- Rend opérationnel le raccordement en lecture seule au stockage d'études PUBLIC pseudonymisé via `pip_connector.study_dir`.
- Ajoute un diagnostic explicite du stockage (non configuré, absent, non-répertoire, prêt).
- Renforce la séparation absolue CRM / études : suppression récursive des identifiants et clés de rapprochement (`crm_id`, `contact_id`, `source_ref`, `passation_id`, identités, e-mail, téléphone, bénéficiaire/participant).
- Déduplique les enregistrements par `study_id` et ignore les liens symboliques et schémas non conformes.
- Documente le bloc `[pip_connector]` dans `secrets.example.toml` sans modifier ni renommer le secret HMAC existant.
- Aucun changement Calendar/Teams, aucun calcul PIP/O*NET dans Gestion des Actions, aucun contrat final PIP figé avant H.
- Tests ciblés A à G + RC8 : 63 réussis.

# 3.0.0-I9-J2C-PIP-LIAISON-E-RESUME-RESULTATS — 2026-09-18

- Jalon E construit exclusivement depuis le jalon D.
- Réception et canonicalisation minimale du résumé final PIP ACCOMPAGNEMENT.
- Garde-fous stricts : aucune réponse brute PIP/O*NET, identité ou clé étude/CRM dans le résumé.
- Affichage admin compatible avec le modèle canonique.
- 43 tests ciblés réussis.

# 3.0.0-I9-J2C-PIP-LIAISON-D-TOKEN-ENRICHI — 2026-09-18
- Jalon D construit exclusivement à partir du jalon C validé.
- Enrichissement additif du token ACCOMPAGNEMENT signé : prénom et nom d’affichage du bénéficiaire, numéro lisible et titre de l’action.
- Conservation stricte des identifiants techniques, des quatre droits RC8, de HMAC-SHA256 et du secret existant `pip_connector.launch_signing_key`.
- Compatibilité descendante : le constructeur de token reste utilisable sans les champs d’affichage ; aucun contrat d’événement PIP n’est figé ici.
- Aucune adresse e-mail, date de naissance, réponse ou résultat PIP/O*NET ajoutés au token.
- Aucun changement Calendar/Teams, CRM PUBLIC, callback, documents ou programme PIP.

# 3.0.0-I9-J2C-PIP-LIAISON-C-CALLBACK — 2026-09-18
- Jalon C : demande de rappel PIP PUBLIC reliée au CRM existant.
- Activité CRM datée, notification interne asynchrone robuste et idempotente par event_id.
- Email limité aux données commerciales CRM ; aucune donnée d'étude/PIP n'est incluse.
- Aucun changement Calendar/Teams ni programme PIP.

## 3.0.0-I9-J2C-PIP-LIAISON-B-IDEMPOTENCE-SECURITE — 2026-09-18
- Jalon B construit exclusivement à partir du jalon A validé.
- Registre additif `external_incoming_events` avec unicité `(source,event_id)`, empreinte SHA-256 du payload et aucun stockage du payload sensible.
- Détection des collisions : un même `event_id` avec un contenu différent est rejeté.
- Cycle de traitement/retry traçable : RECU, EN_COURS, ERREUR, TRAITE, compteur de tentatives et erreur tronquée.
- Vérification HMAC-SHA256 générique à comparaison constante ; aucun secret en URL, payload persistant ou log.
- Le contrat externe PIP définitif (enveloppe, signature et noms d'événements) reste volontairement non figé avant le jalon H.
- Aucun changement Calendar/Teams, PIP, documents ou flux ACCOMPAGNEMENT existant.

## 3.0.0-I9-J2C-PIP-LIAISON-A-CRM-PUBLIC — 2026-09-18
- Jalon A liaison PIP : CRM PUBLIC additif à partir de RC8.
- Upsert par e-mail normalisé après vérification ; ajout automatique non destructif de `PIP-RIASEC` et fusion des intérêts.
- Consentement marketing facultatif ; refus sans blocage de création du prospect.
- Aucune donnée d'étude pseudonymisée, réponse, score, code Holland ou identifiant de passation PUBLIC dans le CRM.
- Aucun changement Calendar/Teams, documents, prescriptions ou connecteur ACCOMPAGNEMENT.


## 3.0.0-I9-J2C-MAJ-RC8-OUTILS-PIP-CONTRAT — 2026-09-18
- Reprise intégrale de RC7 OUTILS SIMPLES.
- Correction du contrat de lancement PIP 1.0.10 ACCOMPAGNEMENT : scopes PIP_RUN, PIP_RESUME, PIP_STATUS, PIP_RESULT_READ.
- Aucun renommage des secrets : pip_connector.launch_signing_key reste inchangé côté Gestion des Actions.


## 3.0.0-I9-J2C-MAJ-RC6-OUTILS-PIP110 — 2026-09-18
- Sauvegarde automatique des ajouts/retraits d’outils autorisés par action.
- Suppression du bouton de validation intermédiaire des outils afin d’éviter les sélections visuelles non persistées.
- Maintien explicite de l’accès à tous les outils actifs/prescriptibles quel que soit le type de prestation.
- Registre PIP aligné sur 1.0.10 ACCOMPAGNEMENT et statut de déploiement production.
- Ajout de tests ciblés de persistance multi-outils et de non-régression du filtrage prestation.

## 3.0.0-I9-H2.8 — Consolidation ergonomie / outils / qualité / robustesse

- Isolation de chaque onglet administrateur : une panne locale ne bloque plus les onglets suivants et les incidents sont journalisés avec leur contexte réel.
- Espace intervenant : aucune action présent/absent/relance n'est proposée si la signature du participant existe déjà ; les relances admin sont également bloquées sur un émargement déjà signé.
- Outils Clarté360 : liste d'outils autorisés explicitement au niveau de l'action, utilisée par l'intervenant ; doublons de prescription interdits ; suppression logique possible uniquement par le créateur de la prescription.
- Teams : ajout/modification/suppression d'un créneau recalcule immédiatement les occurrences Teams côté Gestion des Actions, en plus de la file de synchronisation Graph.
- Qualité : tableau de bord hiérarchisé (global -> thème -> action), détail des questions masqué par défaut, traitement/historique des signalements intervenants et bénéficiaires avec réponse administrative.
- Portail bénéficiaire : nouvel onglet Signaler / informer avec historique et réponse de l'administration.
- Calendrier : le champ personnalisé n'affiche plus -10 par défaut lorsqu'il est inactif.
- Version affichée : 3.0.0-I9-H2.8.

## 3.0.0-I9-H2.6 — Correctif Teams preuves / helper durée

- Correction du crash `NameError: _duration_hms is not defined` dans l’onglet Teams : import explicite du helper privé depuis `services`.
- Affichage administrateur enrichi des réunions réellement constatées : début réel, fin réelle, durée exacte et nombre de connexions.
- Conversion des heures d’entrée/sortie Teams dans le fuseau de l’organisation au lieu d’afficher uniquement l’UTC brut.
- Conservation du détail par identité/pseudo, email Microsoft, rôle, durée exacte et rapprochement Clarté360.
- Les références techniques Graph restent réservées à l’administration.
- Aucun changement de schéma ni de données persistantes.

# V3.0.0-I9-F — Études PIP/O*NET pseudonymisées — 12/09/2026

- base obligatoire conservée : I9-E validée ;
- espace administratif Études PIP/O*NET alimenté uniquement par les enregistrements de recherche pseudonymisés RC5 ;
- filtres parcours, PRE/POST, banque, statut et consentement ;
- synthèse méthodologique et qualité item descriptive ;
- comparaison PIP/O*NET uniquement chez les doubles passations, sans fusion ni recalcul des scores ;
- exports CSV/XLSX pseudonymisés réservés aux consentements recherche ;
- journalisation utilisateur/date/filtres/schéma/finalité/volume de chaque export ;
- défense en profondeur contre nom, prénom, email, téléphone et identifiants métier dans les exports ;
- indicateurs de fatigue non disponibles dans RC5 non inventés ;
- 171 tests automatisés réussis sur 171 ; compilation/imports OK ;
- aucune modification VPS ; raccordement au dossier persistant PIP différé à la recette finale.

# V3.0.0-I9-E — Connecteur PIP RIASEC / O*NET RC5 — 12/09/2026

- base obligatoire conservée : I9-D validée, aucune reconstruction ;
- implémentation du contrat de lancement PIP RC5 HMAC-SHA256 strictement compatible avec `GestionActionsPort` ;
- lancement accompagné via `mode=accompagnement&launch=<jeton>` sans exposer les identifiants métier dans l'URL ;
- clé `pip_connector.launch_signing_key` lue uniquement depuis les secrets VPS, jamais stockée en base ni incluse dans le ZIP ;
- ajout d'un consommateur idempotent de l'outbox JSONL PIP RC5 pour `CONSULTE`, `EN_COURS`, `TERMINE` ;
- vérification forte bénéficiaire / action / participant / prescription avant toute mise à jour du Hub ;
- curseur de lecture persistant additif (`connector_cursors`) avec reprise après redémarrage et gestion de troncature/rotation ;
- aucune consommation d'une ligne JSONL partiellement écrite ;
- arrêt sur événement incohérent sans avancer le curseur, avec audit technique ;
- conservation des seules références réellement émises par RC5 (`passation_id`, `app_version`) ; aucun score ou résultat inventé ;
- traitement PIP par le worker indépendant de SMTP afin qu'une panne email ne bloque jamais la synchronisation PIP ;
- statut runtime du connecteur : `CONNECTED`, `LAUNCH_ONLY` ou `NOT_CONFIGURED`, sans persister le secret ;
- interface bénéficiaire : message métier en cas d'indisponibilité, sans traceback ni information de connecteur exposée ;
- 165 tests automatisés réussis sur 165 ;
- compilation Python complète réussie ;
- aucune modification VPS ; recette réelle du secret partagé et de l'outbox différée à la candidate finale.

# V3.0.0-I9-A — Socle I9 : sessions persistantes + robustesse — 12/09/2026

- base obligatoire conservée : I8 validée, aucune reconstruction ;
- migration additive `auth_sessions` et index associés ;
- session persistante ADMIN / INTERVENANT / BÉNÉFICIAIRE via cookie opaque et jeton hashé serveur ;
- révocation des sessions à la déconnexion et après changement de mot de passe ;
- correction définitive du bug ReportLab `wrapOn` sur image de signature absente ;
- nouveau garde d'interface et journalisation technique `UI_MODULE_ERROR` sans traceback brut côté utilisateur ;
- routes publiques et pages administrateur protégées par isolation d'erreur ;
- 132 tests automatisés réussis sur 132 ;
- compilation Python des modules principaux réussie ;
- aucune modification VPS ; recette navigateur F5 différée à la candidate finale.

# V3.0.0-I6 — Import générique + multi-organisme — 05/09/2026

- ajout de profils d’import configurables par organisme (`organization_import_profiles`) ;
- moteur Excel générique piloté par clé, onglets et mapping JSON ;
- suppression des onglets d’import visibles spécifiques Clarté360 / ADCA ;
- source persistante et snapshot isolés par profil d’import ;
- création et gestion de plusieurs organismes depuis les paramètres ;
- rattachement automatique des actions importées à leur organisme ;
- compatibilité interne maintenue avec les lecteurs historiques ;
- migration additive du profil principal Clarté360 et reprise de la copie source historique lorsqu’elle existe ;
- 114 tests automatisés réussis sur 114 ;
- Teams / Graph non commencé.

# V3.0.0-I1 — Socle V3 + migration additive — 05/09/2026

- identité produit : Clarté360 — Gestion des actions ;
- ajout `action_trainers`, `slot_trainers`, `trainer_assignment_history`, `action_modules` ;
- migration additive et idempotente des actions V2.2 existantes ;
- conservation de `actions.trainer_id` et des colonnes `use_*` pendant la transition ;
- synchronisation des affectations V2 avec le socle V3 ;
- Teams créé comme module futur désactivé et jamais activé automatiquement ;
- 85 tests automatisés réussis sur 85 ;
- compilation réussie de `app.py`, `worker.py`, `services.py`, `db.py`.


## 2.2 RC1.1 - Correctif urgent envois (2026-09-04)
- Correction de l'envoi manuel d'emargement : remplacement de la constante obsolete `PRIVACY_NOTICE` par `privacy_notice_html(action_id)`.
- Durcissement du worker : les evenements PENDING d'actions actives sont recalcules depuis le creneau et le fuseau avant decision d'envoi, meme si une ancienne `due_at` stockee est erronee dans le futur.
- Le garde-fou anti-envoi premature reste actif : aucun envoi n'est effectue avant l'echeance metier recalculee.
- Ajout d'un test de regression sur une echeance stockee a tort dans le futur.
- Suite de tests : 76 tests reussis.

## 2.1.1 — Correctif configuration email VPS
- Priorité donnée à la section `[email]` déjà utilisée par l’infrastructure Clarté360.
- Prise en charge de `smtp_server`, `smtp_port`, `smtp_user`, `smtp_password`, `from_email`.
- Compatibilité conservée avec `[MAIL]`, `[mail]` et `[smtp]`.
- Aucun secret réel inclus.

# Changelog

## 1.0.0
- Socle graphique Clarté360 vert canard #008080.
- Logo officiel et mentions légales Clarté360.
- Administrateur et mise en service sécurisée.
- Actions INTRA / INTER / INDIVIDUEL.
- Nombre prévu de stagiaires.
- Import réel GESTION OF CLARTE360 et CSV.
- Participants, créneaux illimités, duplication et modification journalisée.
- Calcul prévu/planifié.
- Liens individuels et QR de créneau.
- Signature graphique tactile/souris.
- Fenêtre temporelle d'émargement.
- Envois et relances automatiques via worker.
- Relance manuelle.
- Tableau de suivi et heures justifiées.
- PDF collectif, individuel, certificat.
- JSON + ZIP portable et piste d'audit.

## 1.1.0 — développement 2026-09-02
- migration additive des données (preuves existantes conservées)
- blocage de la réécriture d'un créneau contenant une preuve
- statuts de présence/absence
- rattrapages reliés au créneau d'origine, y compris collectifs
- régularisation de signature a posteriori explicitement tracée
- espace intervenant restreint : QR, suivi, absence, relance, contresignature
- contresignature unique par créneau
- dates de naissance JJ/MM/AAAA et détection initiale des doublons
- affichage des horodatages en Europe/Paris
- certificat définitif bloqué tant que le dossier n'est pas complet
- signature alternative « nom et prénom + certification »
- report d'un créneau futur avec conservation de l'ancien créneau au statut REPORTE
- réinitialisation administrateur du code personnel QR
- certificat calculé sur les dates effectivement émargées
- sauvegarde SQLite + signatures/documents avec rotation de 30 archives et timer systemd fourni
- tests V1.1 portés à 7 scénarios automatisés


## 1.1.1 — recette renforcée 2026-09-03
- suppression définitive contrôlée des participants, créneaux et actions, y compris données associées, avec confirmation + mot de passe administrateur
- correction de cohérence : une signature valide prime sur un ancien statut ABSENT et interdit de marquer ensuite la personne absente
- workflow de clôture explicite avant certificat définitif + aperçu NON DÉFINITIF disponible à tout moment
- référentiel administrateurs multiples : ajout, désactivation, suppression protégée, changement de mot de passe
- référentiel formateurs/accompagnants : ajout, activation/désactivation, suppression, affectation aux actions
- accès restreint intervenant conservé et régénéré lors d'un changement d'intervenant
- choix de l'administrateur référent de l'action parmi les comptes actifs
- modification des fiches participants
- envoi/réinitialisation du code QR personnel par email sans stockage du code en clair
- notice données personnelles ajoutée à l'écran de signature et aux emails d'émargement
- feuilles collectives enrichies avec absences et contresignature intervenant
- export JSON enrichi : présences/absences, contresignatures et événements email

## 2.0.0-dev — incrément intermédiaire n°1 consolidé — 2026-09-03
- consolidation organisme/agences et écran de paramétrage ;
- types de prestations V2 et modules à la carte branchés aux actions ;
- cycle de vie et archivage normalisés ;
- recherche actifs/archives ;
- worker avec réservation atomique et quarantaine des livraisons SMTP ambiguës ;
- utilitaire de restauration validant l'intégrité SQLite ;
- 22 tests automatisés réussis.

## 2.0.0-dev — incrément intermédiaire n°2 — 2026-09-03
- module Qualité fonctionnel à chaud / à froid / intervenant ;
- 13 questionnaires standard V2 versionnés avec codes Rxx/Ixx stables ;
- parcours public sécurisé PC/tablette/smartphone ;
- campagnes, échéances et relances automatisées ;
- worker qualité idempotent avec quarantaine des livraisons ambiguës ;
- PDF individuel questionnaire ;
- détection structurée difficultés/réclamations ;
- export et purge étendus aux données qualité ;
- 29 tests automatisés réussis + smoke test PDF.

## 2.0.0-dev-I3-pilotage — 2026-09-03
- Import ADCA historique et mapping métier INTRA / INTER / INDIVIDUEL.
- Pilotage qualité consolidé et statistiques par codes stables.
- Gestion difficultés, réclamations, incidents et actions d'amélioration.
- 33/33 tests automatisés.

## 2.0.0-rc1 — 2026-09-03
- Candidate complète de recette métier.
- Finition de transférabilité des notices RGPD, emails manuels et documents PDF.
- Fuseau du contrôle de complétude aligné sur l'organisme.
- Tests candidate : 35/35 réussis.
- Ajout rapport final, procédure VPS et check-list de recette 2–3 h.

## 2.1.0 — 2026-09-03
- Validation/activation explicite des actions ; aucun envoi d'émargement en BROUILLON.
- Actions ACTIVE toujours modifiables.
- Priorité à la configuration secrète MAIL avec compatibilité smtp.
- Confirmation automatique du planning à l'activation et renvoi manuel du planning actualisé.
- Calendrier remanié : numéros de séances métier, ajout séparé de la modification, duplication plus logique, envoi « au début du créneau ».
- Présentation lisible des erreurs email et nettoyage des anciennes erreurs sur événements PENDING recalculés.
- 39 tests automatisés réussis.

## 2.1.3 - 2026-09-03
- Activation visible depuis Calendrier et Envois & relances.
- Validation de coherence horaire avant activation des actions avec emargement.
- Planning envoye lors de l'activation.
- Preparation automatique des campagnes qualite activees.
- Qualite recalee sur la fin reelle de la derniere seance et recalcul dynamique des campagnes PENDING.
- Correction des affichages parasites DeltaGenerator.

## 2.1.4
- Correction robuste des échéances d'émargement pour les séances passant minuit.
- Garde-fou worker contre les envois anticipés sur échéance incohérente.
- Affichage des échéances en heure locale organisme.
- Espace intervenant authentifié avec invitation email et liste des actions affectées.
- Copie persistante sur VPS des bases d'import Clarté360 / ADCA et réutilisation multi-actions.
- Clarification du délai de régularisation après fin de séance.

## 2.2-Lot2 — bénéficiaires + portail documentaire
- Identité bénéficiaire permanente multi-actions, rapprochement Nom/Prénom/date de naissance sans fusion automatique.
- Espace bénéficiaire facultatif avec invitation et changement d'email vérifié.
- Portail bénéficiaire : parcours, planning, documents, questionnaires et ZIP.
- Stockage documentaire hors SQLite avec déduplication SHA-256 et références logiques.
- Dépôt rapide par numéro d'action et droit de dépôt documentaire intervenant.
- 63 tests automatisés réussis.

## V2.2 Lot 3 - Fin d'action + qualite - 2026-09-04
- Dossiers finaux stagiaires et ZIP collectif automatique apres cloture.
- Evaluation HOT PDF incluse si completee ; COLD reste un second flux independant.
- Contacts client structures/importes et destinataires configurables.
- Socle de transmissions client journalisees.
- Pilotage qualite direction enrichi.
- Fin de vie du portail beneficiaire apres 12 mois sans nouvelle action, sans confusion avec les archives internes.
- 69 tests automatises reussis.

## V2.2-RC1 — Candidate de recette complète — 2026-09-04
- Consolidation finale des Lots 1, 2 et 3 sur la base historique `clarte360-emargements-v1.0.0`.
- Version d'interface corrigée en `2.2-RC1`.
- Transmission réelle par le worker du dossier final client avec pièce jointe ZIP et journalisation.
- Transmission indépendante de l'évaluation à froid en PDF aux destinataires configurés, après complétion.
- Anti-doublon et réservation atomique des transmissions client ; quarantaine `UNKNOWN_DELIVERY` après interruption ambiguë.
- Fin de vie du portail renforcée : avertissement après 12 mois sans nouvelle action, délai de 30 jours, puis purge du portail uniquement après avertissement effectivement envoyé.
- Une nouvelle action avant la purge annule automatiquement la condition de purge.
- Nommage du ZIP final basé prioritairement sur la date de fin d'action : `AAMMJJ NO_ACTION DOCS STAGIAIRES.zip`.
- Journal des transmissions client visible dans l'administration.
- Contrôle transversal : aucune expression conditionnelle Streamlit de type `DeltaGenerator` résiduelle dans `app.py`.
- 75 tests automatisés réussis sur 75 + compilation Python des modules principaux.

## V2.2-RC1.2 — Correctif accès bénéficiaire — 2026-09-05
- Ajout d'un accès permanent visible « Accès stagiaire / bénéficiaire ».
- Un lien d'activation déjà utilisé/expiré propose désormais explicitement la connexion permanente.
- Une URL `?beneficiary_invite` sans jeton bascule vers la connexion bénéficiaire au lieu de l'administration.
- L'email d'activation distingue le lien temporaire d'activation et l'accès permanent.
- Ajout du parcours bénéficiaire « Mot de passe oublié » avec jeton temporaire à usage unique.


## V3.0.0-I2 — Multi-intervenants — 2026-09-05
- Plusieurs intervenants par action et par créneau.
- Référent, principal, co-intervenant et remplaçant.
- Historique des affectations et remplacements sans effacement.
- Portail intervenant fondé sur les affectations V3 et créneaux réellement affectés.
- Reports et rattrapages conservent les affectations du créneau source.
- Nouvel onglet Intervenants dans l'administration de l'action.
- Compatibilité conservée avec `actions.trainer_id` et les actions V2 migrées.
- 88 tests automatisés réussis sur 88.

## V3.0.0-I3 — Contresignatures + émargement V3 — 2026-09-05
- Blocage serveur et interface de toute contresignature avant la fin réelle du créneau, fuseau organisme et créneaux traversant minuit compris.
- Contresignature refusée tant qu'un participant concerné reste EN_ATTENTE.
- Nouvelle preuve additive `trainer_countersignatures_v3`, sans modification des preuves V2 historiques.
- Une contresignature immuable par intervenant actif du créneau ; co-animation compatible.
- Signature graphique intervenant avec fichier PNG, empreinte SHA-256, identité, horodatage, déclaration et audit.
- Les contresignatures deviennent des preuves bloquant la réécriture/report du créneau.
- PDF d'émargement adaptés aux contresignatures multiples et signatures graphiques intervenants.
- Emargement automatique V3 : un seul email INITIAL au début réel du créneau ; aucune RELANCE_1/RELANCE_2 automatique.
- Les rappels V2 encore PENDING sont neutralisés en SKIPPED sans effacer l'historique déjà envoyé.
- Relance manuelle conservée pour administration/intervenant.
- Export JSON/ZIP enrichi avec les preuves de contresignature V3.

## V3.0.0-I4 — Portails séparés + planning intervenant — 2026-09-05
- Écran Administration isolé : aucun lien vers les autres portails sur la page de connexion.
- Libellés dédiés « Espace intervenant » et « Espace bénéficiaire ».
- Droits explicites de gestion planning au niveau action et au niveau créneau.
- Modification, report et ajout de créneaux depuis l'espace intervenant selon autorisations.
- Garde-fous serveur : action clôturée, preuves, séance passée, volume, bornes, chevauchements, conflits intervenants et co-animation.
- Synchronisation des échéances d'émargement et qualité après modification validée.
- Journal additif `planning_change_events` avec hook Teams différé à I7.
- Notifications planning aux personnes concernées sur action active, sans envoi en BROUILLON/PLANIFIÉE.
- Export calendrier ICS avec UID stable par créneau dans les espaces intervenant et bénéficiaire.
- 102 tests automatisés réussis sur 102 + compilation Python des modules principaux.

## 3.0.0-I5 — Qualité, relances manuelles et documents finaux
- Suppression des relances automatiques HOT / COLD / TRAINER : un seul envoi automatique INITIAL par campagne.
- Neutralisation additive des anciennes relances PENDING sans effacement de l'historique.
- Relances qualité manuelles réutilisant la campagne et le lien existants, avec compteur, auteur, date et audit.
- Nouvel écran Administration « Relances » avec sélection groupée des questionnaires non revenus et liste des émargements à régulariser.
- Nouvel écran Administration « Qualité » orienté métier : taux de réponse, rubriques libellées, points faibles, difficultés et améliorations.
- Retour intervenant qualité étendu à tous les intervenants actifs d'une action multi-intervenants.
- PDF des questionnaires complétés directement téléchargeables depuis Documents de l'action.
- Conservation du dossier final, des transmissions client anti-doublon et de l'envoi COLD ultérieur séparé.

## V3.0.0-I7 — Microsoft Teams / Graph — 05/09/2026
- Module Teams indépendant par action, activation prospective uniquement.
- Authentification Graph app-only par certificat, secrets hors Git.
- Tables additives salles, occurrences, rôles Entra, rapports et synchronisations.
- Lien Teams stable par action comme stratégie cible soumise à POC réel Microsoft.
- Intervenants externes préparés pour Entra B2B Guest et rôles avancés.
- Récupération automatique des rapports de présence par le worker.
- Rapprochement Teams / émargement sans substitution de signature.
- Liens Teams dans espaces intervenant et bénéficiaire.
- 122 tests réussis.

## V3.0.0-I8 — recette métier et simplification Teams
- Teams sélectionnable dès l'ouverture/création de l'action, sans exiger un planning préalable.
- Premier créneau futur = date d'effet Teams automatique + synchronisation en file worker.
- Contrôle strict du nombre prévu/réel de participants à l'activation.
- Rattachement bénéficiaire exact automatique ; correspondances approximatives manuelles.
- Nouveau participant ajouté à une action active : planning existant envoyé automatiquement.
- Relances automatiques d'émargement retirées de l'UI.
- Portail bénéficiaire enrichi : questionnaires terminés et feuilles d'émargement.

## I9-B — 2026-09-12
- Modalités métier contrôlées et séparées de l'organisation et du lieu/précision.
- Normalisation robuste des dates Excel, dont numéros de série.
- Rattachement automatique strict des bénéficiaires sur identité exacte.
- Planning automatique pour participant ajouté après activation.
- Journal générique des communications I9.
- Contresignature anticipée autorisée dès finalisation complète des statuts participants.
- Demande automatique de contresignature à la fin du créneau si nécessaire.
- Compteur intervenant de contresignatures à traiter et lien ciblé action/créneau.
- Bornes cohérentes pour les offsets calendrier.
- 139 tests automatisés réussis.

## I9-C — 2026-09-12
- Interface Teams orientée métier : prochaine réunion réelle, date + horaires, suppression des identifiants techniques dans les portails utilisateur.
- Synchronisation Teams présentée comme automatique ; synchronisation manuelle déplacée en administration avancée comme outil de secours.
- Identité Microsoft permanente ajoutée à la fiche intervenant : email Microsoft/Teams, Entra ID, statut et dernière vérification.
- Recherche obligatoire d'une identité Entra existante avant toute création/invitation.
- Suppression de la création silencieuse des Guests : une invitation Microsoft externe nécessite désormais une demande administrateur explicite.
- Rôles Teams avancés alimentés depuis l'identité Microsoft permanente de l'intervenant.
- Présence Teams maintenue comme preuve complémentaire uniquement.
- Présences Teams avec email différent/non reconnu laissées non attribuées ; rapprochement manuel explicite, contrôlé et audité.
- Bénéficiaire et intervenant ne voient plus Graph, Meeting ID, Entra ID ni identifiants techniques de créneaux.
- 146 tests automatisés réussis + compilation Python des modules principaux.

## I9-D — 2026-09-12
- Création du catalogue central générique des outils Clarté360 (`tool_catalog`) : code, nom, catégorie, URL, version, activation, publics, prestations compatibles, prescription, type de lancement, durée d’accès, RGPD et état de connecteur.
- Création du modèle universel de prescription (`tool_prescriptions`) relié à l’outil, au bénéficiaire permanent, à l’action, au participant et au prescripteur.
- États normalisés : A_FAIRE, ENVOYE, CONSULTE, EN_COURS, TERMINE, A_REVOIR_EN_SEANCE, REVU_EN_SEANCE, ANNULE.
- Jetons de lancement temporaires stockés uniquement sous forme d’empreinte SHA-256, à usage unique, avec expiration et révocation possibles.
- Journal additif des événements de prescription avec `event_id` idempotent pour préparer les connecteurs externes.
- Nouveau droit explicite `can_prescribe_tools` par intervenant et par action ; aucune prescription n’est accordée par simple visibilité de l’action.
- Nouveau volet « Outils Clarté360 » dans l’administration de l’action et dans l’espace intervenant autorisé.
- Nouveau volet « Mes outils Clarté360 » dans le portail bénéficiaire avec statut, échéance et lancement sécurisé.
- PIP RIASEC/O*NET RC5 référencé dans le catalogue avec son URL et sa version réelles, mais son connecteur signé reste explicitement en attente de I9-E : aucun lancement PIP non signé n’est introduit en I9-D.
- Le catalogue reste générique : un outil non-PIP peut être ajouté et prescrit sans code métier PIP spécifique.
- 155 tests automatisés réussis + compilation Python des modules principaux.

## I9-G — 2026-09-12
- Ajout du CRM léger Contacts / Prospects avec consentement marketing indépendant et révocable.
- Conversion prospect → bénéficiaire avec contrôle anti-doublon.
- Ajout d'un espace administrateur Contacts / Prospects.
- Ajout du contrat `CLARTE360_CONTRACTUALISATION_CONTEXT_V1`.
- Ajout du suivi des dossiers Contractualisation et de leurs références PDF/JSON/financements.
- Aucun moteur juridique/PDF Contractualisation dupliqué dans Gestion des Actions.

## I9-H — 2026-09-12
- Consolidation finale de la séquence I9-A → I9-H et préparation de la candidate de recette.
- Ajout d'un onglet administrateur « Diagnostic I9 » en lecture seule, sans exposition des secrets.
- Contrôles de disponibilité du socle et contrôles non bloquants Email / Microsoft 365 / PIP.
- Ajout de `release_check.py` : compilation Python, imports principaux et pytest avant commit/push.
- Ajout de tests de durcissement contre exposition de traceback et motifs évidents de secrets codés en dur.
- Documentation de recette finale et maintien strict du processus VPS : aucune modification serveur avant PUSH FAIT.
- 185 tests automatisés réussis sur 185 ; candidate technique OK.

## V3 I9-H1 — Validation renforcée des saisies — 2026-09-12
- Ajout d'un validateur transversal `input_validation.py`.
- Validation Unicode des noms/prénoms : lettres, espaces, apostrophes et tirets uniquement.
- Validation renforcée e-mails, téléphones, dates, créneaux, numéros d'action, SIRET, NDA, NAF, TVA, URL, fuseaux IANA et JSON.
- Contrôles appliqués aux frontières métier : actions, participants, bénéficiaires, intervenants, CRM, organismes, agences, contacts client, Microsoft/Teams et imports.
- Messages métier pour les erreurs de saisie sur les principaux écrans ; pas de traceback attendu pour une erreur de format utilisateur.
- 263 tests réussis ; release_check OK.


## 3.0.0-I9-H2 — Correctifs recette réelle
- Correction du portail bénéficiaire : requête qualité alignée sur le schéma réel (suppression de la référence inexistante `quality_campaigns.updated_at`).
- Correction de l'affichage Streamlit qui exposait un objet `DeltaGenerator` dans l'espace intervenant.
- Zone de signature/contresignature rendue visuellement identifiable (cadre gris, consigne explicite, souris/doigt/stylet).
- Statut d'activation de l'espace bénéficiaire visible en administration et dans l'espace intervenant, avec dernière connexion.
- UX multi-intervenants clarifiée sans suppression des capacités multi-affectations existantes.
- Catalogue outils : sélection d'un outil existant et préremplissage ; PIP protégé en connexion signée ; vocabulaire métier pour l'état du connecteur.
- Mise à jour du catalogue sans effacer silencieusement le contrat/connecteur technique existant.
- Version affichée corrigée en 3.0.0-I9-H2.


## 3.0.0-I9-H2.3 — 2026-09-15
Voir `INCREMENT_V3_I9_H2_3_TEAMS_PREUVES_UX.md`.

## 3.0.0-I9-H2.4 — 2026-09-15
Voir `INCREMENT_V3_I9_H2_4_CONTRESIGNATURE_DOCUMENTS_ERGONOMIE.md`.

## 3.0.0-I9-H2.5 — Correctif calendrier / collision `time`
- Correction d'un crash global de la fiche action provoqué par la collision entre `datetime.time` et le module standard `time` réexporté par `from services import *`.
- Le calendrier utilise désormais explicitement `dt_time` pour les champs horaires et `fromisoformat`.
- Ce correctif rétablit Calendrier et, par effet de bord Streamlit, les onglets suivants qui pouvaient sembler indisponibles (notamment Teams).
- Ajout d'un test de non-régression dédié.

## 3.0.0-I9-H2.7 — Consolidation recette réelle
- Corrige le crash `time(12,0)` du module Suivi qui bloquait Qualité/Documents/Journal et polluait visuellement les autres onglets.
- Corrige le workflow de contresignature : aucune demande future prématurée ; activation seulement quand le créneau est actionnable.
- Annule automatiquement les anciennes demandes futures créées par les builds précédents.
- Clarifie l'UX Teams pour les séances futures versus les rapports réellement en attente.

## 3.0.0-I9-J2C-PIP-LIAISON-F — Rapport PDF PIP / documents / droits — 2026-09-18
- Reprise exclusive du jalon E.
- Archivage du rapport professionnel PDF PIP dans le système documentaire existant (`stored_files` + `document_references`), sans silo PIP.
- Liaison additive prescription-document (`prescription_documents`) avec unicité par prescription et traçabilité source.
- Déduplication SHA-256 et rejeu idempotent : un même rapport ne crée ni seconde copie physique ni seconde référence métier.
- Protection contre le remplacement silencieux d'un rapport déjà archivé par un contenu différent.
- Rattachement automatique action + bénéficiaire + participant ; visibilité bénéficiaire et intervenant via les droits documentaires existants de l'action.
- Téléchargement du PDF depuis la vue de résultat PIP administrateur ; les intervenants autorisés le retrouvent dans Documents de leur action.
- Le transport PIP -> Gestion des Actions reste volontairement non figé avant le contrat d'intégration final du jalon H.

## 2026-09-20 — INTERVENANTS J1 — Référentiel prestations
- Référentiel administrable et versionné des prestations Clarté360.
- Critères de compétence versionnés par prestation, niveaux 0–4 et preuves acceptables.
- Interface `Paramètres > Intervenants & partenaires > Prestations`.
- 369/369 tests automatisés réussis.

## Intervenants J15 — 2026-09-21
- Référentiel maître et versionné des familles de prestations.
- Familles non libres dans la gestion des prestations.
- Réaffectation/fusion de familles et réaffectation en masse des prestations.
- Filtres du catalogue de prestations.
- Référentiel initial de 152 critères de compétences pour 26 prestations.
- Origine des critères explicitée et administrable.
- Grille de critères à cocher pour validation humaine dans l’adéquation.

## J18.1 - 2026-09-21 - Synchronisation registre outils
- Synchronisation de `config/tool_registry.json` avec la version courante utilisée dans GitHub.
- Activation de MOTEURS_PROFESSIONNELS en production/prescriptible avec son profil HUB actuel.
- Mise à jour des tests du registre afin qu'ils contrôlent l'état courant du référentiel et non l'ancien état planifié.
- Aucun changement métier Intervenants hors synchronisation du registre outils.
