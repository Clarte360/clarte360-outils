# RC2-2-2 — P5 Actions — 02/10/2026

## Objectif
Finaliser le parcours métier Action → qualification concernée → décision humaine → retour Action → recalcul immédiat de l'éligibilité.

## Réalisé
- Le bouton « Étudier / valider cette qualification » mémorise désormais explicitement l'Action d'origine, la personne et la prestation attendue.
- Le dossier professionnel s'ouvre sur Qualifications et sur la prestation exigée par l'Action.
- Après validation humaine, l'éligibilité est relue depuis la base et recalculée immédiatement ; aucun statut d'éligibilité n'est mis en cache.
- Un bouton « Retour à l'action et à ses intervenants » restitue l'Action d'origine et affiche le résultat du recalcul.
- Une affectation exceptionnelle reste distincte d'une qualification : justification obligatoire et aucune transformation artificielle en statut QUALIFIE.
- Les règles existantes de niveau minimum et de critères obligatoires restent appliquées par action_professional_eligibility().

## Non-régression
Aucune modification des applications PIP/IPIP, signatures, émargements, worker ou contrats de connecteurs.
