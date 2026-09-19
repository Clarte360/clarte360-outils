# Rapport — Liaison PIP — Jalon B

Version : `3.0.0-I9-J2C-PIP-LIAISON-B-IDEMPOTENCE-SECURITE`
Base : jalon A `3.0.0-I9-J2C-PIP-LIAISON-A-CRM-PUBLIC`.

## Réalisé
- registre additif des événements externes entrants, clé unique `(source,event_id)` ;
- empreinte SHA-256 canonique du payload, sans conservation du payload sensible dans ce registre ;
- rejet d'une collision `event_id` si le contenu diffère ;
- cycle RECU / EN_COURS / ERREUR / TRAITE avec compteur de tentatives ;
- rejeu d'un événement déjà traité sans retraitement ;
- vérificateur HMAC-SHA256 générique à comparaison constante ;
- aucun contrat externe PIP définitif figé à ce jalon.

## Tests
- ciblés A+B+CRM+contrat RC8 : 19/19 réussis ;
- suite globale relancée après adaptation des assertions de version : aucun échec observé jusqu'à 65 %, puis arrêt par limite de temps de l'environnement. Il n'est donc pas affirmé que la suite globale complète a terminé.

## Non-régression / hors périmètre
Aucune modification Calendar/Teams, application PIP, documents ou flux ACCOMPAGNEMENT existant.
