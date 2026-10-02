# CHECKLIST RECETTE MANUELLE — RC2-2-1 — 01/10/2026

## Avant ouverture UI
- [ ] PUSH GitHub effectué par l'utilisateur.
- [ ] PULL VPS volontaire effectué.
- [ ] `PYTHONPATH=. ./.venv/bin/pytest -q` vert.
- [ ] compilation Python verte.
- [ ] service web redémarré.
- [ ] worker redémarré.
- [ ] deux services `active`.
- [ ] HTTP local 200.

## Espace bénéficiaire multi-outils
Préparer un bénéficiaire ayant simultanément plusieurs prescriptions, au minimum :
- PIP RIASEC / O*NET ;
- IPIP NEO-120 ;
- un outil HUB générique actif (ex. Moteurs professionnels ou Boussole selon disponibilité).

Vérifier :
- [ ] ouverture de l'espace bénéficiaire sans incident global ;
- [ ] onglet `Mes outils Clarté360` visible ;
- [ ] tous les outils prescrits sont affichés ;
- [ ] ouverture PIP fonctionnelle ;
- [ ] ouverture IPIP fonctionnelle ;
- [ ] ouverture d'un autre outil non perturbée ;
- [ ] Planning / Documents / Questionnaires / autres onglets restent accessibles ;
- [ ] une erreur sur un outil ne fait pas tomber tout l'espace bénéficiaire.

## Règle de reprise PIP / IPIP
Pour PIP puis IPIP :
- [ ] statut `A_FAIRE` : ouverture autorisée ;
- [ ] statut `CONSULTE` : reprise autorisée ;
- [ ] statut `EN_COURS` : reprise autorisée ;
- [ ] une ancienne valeur `expires_at` dépassée ne bloque pas le lancement spécialisé PIP ;
- [ ] statut `TERMINE` : aucun bouton permettant de relancer la même prescription ;
- [ ] message indique qu'une nouvelle passation nécessite une nouvelle prescription ;
- [ ] une nouvelle prescription peut être créée après `TERMINE` ;
- [ ] une seconde prescription est refusée tant que la précédente est encore active/non terminée.

## IPIP retour / rapport
- [ ] worker consomme un événement IPIP valide ;
- [ ] `CONSULTE` / `EN_COURS` mettent à jour le statut attendu ;
- [ ] `TERMINE` sans rapport est refusé ;
- [ ] `TERMINE` avec rapport valide vérifie taille + SHA-256 ;
- [ ] PDF est archivé dans Gestion des Actions ;
- [ ] rejeu d'un même événement ne duplique pas le traitement.

## Non-régression RC2-2
- [ ] menu `Intervenants / Partenaires` au-dessus de `Paramètres` ;
- [ ] modification Nom / Prénom indépendante du titre professionnel ;
- [ ] reset dossier professionnel protégé par mot de passe admin ;
- [ ] réanalyse SHA-256 / version documentaire ;
- [ ] anti-doublon expériences/diplômes/certifications ;
- [ ] PDF scanné analysable ;
- [ ] lecture IA 0/4 corrigée ;
- [ ] décision humaine prioritaire dans Qualifications ;
- [ ] absence de l'étape `Retenir pour instruction`.
