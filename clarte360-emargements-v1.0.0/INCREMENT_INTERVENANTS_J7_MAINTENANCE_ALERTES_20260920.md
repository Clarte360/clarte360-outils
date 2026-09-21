# J7 — Documents / maintien des qualifications / alertes

Date : 20/09/2026
Socle : J6 Matrice collective

## Objet
Mettre sous surveillance les échéances du dossier professionnel sans automatiser une décision de qualification.

## Réalisé
- Nouvel onglet **Alertes** dans Intervenants & partenaires.
- Surveillance des dates de validité des documents actifs du dossier professionnel.
- Surveillance des certifications, habilitations et attestations disposant d'une date de fin.
- Surveillance de la date de validité Qualiopi lorsque le statut personnel est Oui.
- Surveillance des dates de révision des qualifications humaines par prestation.
- Surveillance de la date de révision globale du dossier professionnel lorsqu'elle est renseignée.
- Fenêtre d'anticipation administrable à l'écran : 30, 60, 90, 120 ou 180 jours (90 jours par défaut).
- États : **Échu** et **À renouveler / revoir**.
- Possibilité de marquer une alerte comme traitée ou de reporter son rappel à une date choisie, avec commentaire et traçabilité.
- Archivage d'un document obsolète depuis le dossier 360° : retrait du dossier actif sans destruction de la preuve stockée.

## Garde-fou métier
Une échéance dépassée ou une alerte J7 **ne retire jamais automatiquement une qualification humaine** et ne modifie jamais son niveau. L'application signale ; l'administrateur vérifie et décide. Cette règle préserve la souveraineté humaine définie aux J4/J5.

## Données
Table additive `professional_maintenance_actions` pour tracer les traitements/reports d'alertes. Les alertes elles-mêmes sont dérivées des données sources afin d'éviter une seconde vérité métier.

## Non-régression
403 tests automatisés réussis, dont 5 nouveaux tests J7.
