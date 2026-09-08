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
