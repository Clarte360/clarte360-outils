# Rapport de tests – V2.1.3.9C préproduction

## Résultat
- Compilation Python : conforme.
- Tests automatisés : 68 réussis sur 68.
- Nouveau référentiel embarqué : 204 valeurs canoniques dans l’onglet « Référentiel nettoyé ».
- Définitions du nouveau référentiel correctement chargées depuis la colonne « Définition Clarté360 ».

## Contrôles ciblés
- Le refus de tous les mots proposés ne clôt plus immédiatement la situation.
- Le bénéficiaire peut approfondir un autre aspect de la même situation.
- La question de réorientation exploite les couples questions-réponses des deux voies et les candidats déjà refusés.
- Deux réorientations au maximum sont autorisées après refus.
- Une seule hypothèse peut être retenue par cycle.
- Une hypothèse retenue est enregistrée uniquement dans le panier Hypothèses.
- Le seuil d’invitation reste : au moins 3 hypothèses et un total valeurs validées + hypothèses supérieur ou égal à 8.
- Compatibilité de reprise JSON préservée.

## Test réel restant
La pertinence humaine des nouvelles questions de réorientation et des hypothèses proposées doit être validée en situation réelle avec l’API configurée.
