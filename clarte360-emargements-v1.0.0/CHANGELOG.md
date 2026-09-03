
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
