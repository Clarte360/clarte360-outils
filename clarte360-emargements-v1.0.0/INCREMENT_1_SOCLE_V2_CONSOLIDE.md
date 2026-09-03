# Clarté360 Émargements & Qualité — V2
## ZIP intermédiaire n°1 — Socle V2 consolidé

### Réalisé

1. Cycle de vie V2 normalisé : `BROUILLON`, `PLANIFIEE`, `ACTIVE`, `A_CLOTURER`, `CLOTUREE`, `ARCHIVEE`, avec migration additive des anciens statuts.
2. Recherche des actions actives et archivées par numéro, intitulé, client, bénéficiaire ou email.
3. Archivage et désarchivage conservatoires.
4. Paramétrage organisme enrichi : identité, siège, SIRET, RCS, NAF, TVA, NDA, coordonnées, fuseau horaire, RGPD, expéditeur et durée indicative de conservation.
5. Gestion des agences/établissements et rattachement d'une action à une agence.
6. Six types de prestations : Formation, Bilan de compétences, VAE, Coaching, Mentorat, Autre.
7. Modules activables par action : émargement, chaud, froid, retour intervenant.
8. Protection : une campagne qualité déjà envoyée empêche de modifier les paramètres qui invalideraient son historique.
9. Worker renforcé : réservation atomique `SENDING`. En cas d'arrêt ambigu pendant SMTP, l'événement ancien est placé en `UNKNOWN_DELIVERY` au lieu d'être renvoyé automatiquement.
10. Emails d'émargement préparés à partir de l'identité/RGPD de l'organisme lorsque ces paramètres existent.
11. Sauvegarde conservée et ajout d'un utilitaire `restore_backup.py` avec contrôle d'intégrité SQLite et copie de sécurité avant restauration.
12. Index SQLite ajoutés sur statuts, organisme/agence, noms participants et file email.
13. Interface administrateur complétée pour organisme, agences, types de prestations, modules, archivage et recherche.

### Ce qui appartient encore aux incréments suivants

- questionnaires électroniques complets et PDF qualité ;
- moteur de campagnes qualité et relances chaud/froid/intervenant ;
- import ADCA et reprise historique qualité seule ;
- tableaux de bord qualité, réclamations et actions d'amélioration ;
- paramétrage graphique complet des PDF et suppression de toutes les dernières chaînes Clarté360 codées en dur ;
- recette VPS réelle SMTP/smartphone/restauration.

### Résultat automatisé

22/22 tests réussis.
