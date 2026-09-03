# CHECK-LIST DE RECETTE MÉTIER — V2 RC1

Durée cible : 2 h à 3 h. Cocher OK / KO et noter l'anomalie immédiatement.

## 0 — Sécurisation avant recette — 10 min
- [ ] Sauvegarde de la base et des signatures existantes réalisée.
- [ ] Application et worker redémarrent sans erreur.
- [ ] Connexion administrateur possible.
- [ ] Les anciennes actions sont visibles et leurs données sont conservées.

## 1 — Paramétrage organisme / agence — 10 min
- [ ] Vérifier identité, adresse, SIRET, NDA, email, téléphone, site, RGPD et fuseau.
- [ ] Créer ou modifier une agence/établissement.
- [ ] Vérifier qu'une action peut être rattachée à cette agence.
- [ ] Vérifier que les documents affichent les bonnes mentions d'organisme.

## 2 — Création et modularité d'actions — 15 min
Créer plusieurs petites actions de test.
- [ ] Formation avec émargement + chaud + froid + intervenant.
- [ ] Bilan de compétences sans obligation d'émargement si non souhaité.
- [ ] VAE.
- [ ] Coaching.
- [ ] Mentorat.
- [ ] Autre.
- [ ] Vérifier qu'une action « qualité à froid uniquement » est possible.
- [ ] Vérifier que les modules non activés ne sont pas imposés.

## 3 — Émargement complet — 30 min
Sur une action collective avec 2 ou 3 participants et 2 créneaux :
- [ ] Les créneaux communs ne sont saisis qu'une fois.
- [ ] QR collectif lisible sur smartphone.
- [ ] Lien personnel reçu/ouvert sur smartphone.
- [ ] Identification par nom + code personnel fonctionne.
- [ ] Signature manuscrite tactile fonctionne.
- [ ] Nom/prénom + certification fonctionne.
- [ ] Une seconde signature identique est bloquée.
- [ ] L'heure affichée correspond à l'heure locale réelle.
- [ ] L'administrateur voit la signature sans reconnexion.
- [ ] Marquer un participant absent.
- [ ] Corriger une absence si nécessaire.
- [ ] Reporter un créneau sans détruire l'historique.
- [ ] Créer un rattrapage pour un seul participant.
- [ ] Vérifier que les autres participants sont non concernés par ce rattrapage.
- [ ] Contresigner le créneau une seule fois en tant qu'intervenant.
- [ ] Générer feuille collective et feuille individuelle.

## 4 — Clôture et documents — 15 min
- [ ] Vérifier les alertes empêchant un certificat incohérent/incomplet.
- [ ] Clôturer l'action lorsque les preuves sont complètes.
- [ ] Générer le certificat Formation/BC/VAE approprié.
- [ ] Vérifier l'attestation pour Coaching/Mentorat/Autre.
- [ ] Vérifier identité organisme, participant, numéro, dates et durée.
- [ ] Exporter l'archive ZIP complète de l'action.

## 5 — Qualité bénéficiaire à chaud — 15 min
- [ ] Générer/ouvrir une campagne à chaud.
- [ ] Ouvrir le questionnaire sur smartphone.
- [ ] Vérifier lisibilité, champs obligatoires et consentement RGPD.
- [ ] Enregistrer les réponses.
- [ ] Vérifier qu'une nouvelle saisie complète est bloquée/identifiée comme déjà réalisée.
- [ ] Générer le PDF individuel du questionnaire.

## 6 — Qualité à froid / BC 6 mois / intervenant — 15 min
- [ ] Vérifier l'échéance J+90 d'une prestation concernée.
- [ ] Vérifier le suivi BC à 6 mois.
- [ ] Vérifier le questionnaire intervenant organisation/logistique/moyens.
- [ ] Forcer une échéance de test et vérifier la préparation de l'envoi/relance.
- [ ] Vérifier qu'un questionnaire terminé n'est plus relancé.

## 7 — Difficulté / réclamation / amélioration — 10 min
- [ ] Saisir dans un questionnaire une difficulté ou réclamation.
- [ ] Vérifier sa remontée dans le pilotage.
- [ ] Créer manuellement une difficulté/réclamation.
- [ ] Affecter un responsable et changer le statut.
- [ ] Créer une action d'amélioration avec échéance.
- [ ] Clôturer l'action d'amélioration et la difficulté.

## 8 — Pilotage qualité — 10 min
- [ ] Vérifier taux de réponse et compteurs.
- [ ] Filtrer par type de prestation.
- [ ] Filtrer par agence si disponible.
- [ ] Vérifier les statistiques Rxx/Ixx.
- [ ] Vérifier qu'une personnalisation de libellé ne modifie pas les codes analytiques.

## 9 — Imports — 15 min
- [ ] Import Clarté360 INDIVIDUEL : contrôle CONV ADM.
- [ ] Import Clarté360 INTER : contrôle CONV ADM.
- [ ] Import INTRA : contrôle STAGIAIRE.
- [ ] Import ADCA par NO_ADCA.
- [ ] Prévisualiser avant validation.
- [ ] Créer une action ADCA historique avec qualité à froid uniquement.
- [ ] Vérifier qu'aucun faux émargement n'est créé.

## 10 — Archives, recherche et suppression — 10 min
- [ ] Clôturer puis archiver une action.
- [ ] Vérifier qu'elle disparaît des actifs sans être perdue.
- [ ] Rechercher dans les archives par numéro d'action.
- [ ] Rechercher par bénéficiaire/stagiaire.
- [ ] Exporter l'archive complète.
- [ ] Tester une suppression sur UNE action de test uniquement, après confirmation forte.
- [ ] Vérifier disparition des participants, preuves, qualité et éléments associés.

## 11 — SMTP et worker — 10 min
- [ ] Envoyer un email réel d'émargement.
- [ ] Envoyer un email réel qualité.
- [ ] Vérifier expéditeur, objet, identité organisme, lien HTTPS et RGPD.
- [ ] Vérifier les logs worker.
- [ ] Vérifier qu'aucun doublon n'est reçu lors d'une exécution normale.

## 12 — Verdict
- [ ] Aucun blocage critique.
- [ ] Aucun recul par rapport à V1.1.1.
- [ ] Les anomalies mineures sont listées avec écran, action, heure et résultat attendu.
- [ ] Décision : VALIDÉE / CORRECTIONS RC2 NÉCESSAIRES.
