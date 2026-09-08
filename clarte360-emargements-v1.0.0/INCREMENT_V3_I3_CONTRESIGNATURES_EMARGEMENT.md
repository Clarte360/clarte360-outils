# CLARTÉ360 — GESTION DES ACTIONS V3
## Incrément I3 — Contresignatures + émargement V3

Version : **3.0.0-I3** — cumulative **I1 + I2 + I3**.

## Règle bloquante
Une contresignature intervenant est refusée côté service tant que la date/heure courante est antérieure à la fin réelle du créneau. Le contrôle utilise le fuseau de l'organisme et la logique `slot_start_end`, y compris pour un créneau traversant minuit. L'interface désactive également l'action, mais cette désactivation n'est jamais considérée comme une protection suffisante.

## Finalisation des participants
Avant contresignature, chaque participant actif doit être dans un état explicite : signature VALIDE, ABSENT, NON_CONCERNE ou PRESENT_REGULARISE. Tout participant EN_ATTENTE bloque la contresignature.

## Co-animation et preuves
La table additive `trainer_countersignatures_v3` permet une preuve par intervenant actif et par créneau. La table V2 historique est conservée intacte et son contenu est recopié de façon idempotente vers la structure V3 lorsque l'identité de l'intervenant peut être rapprochée.

Chaque nouvelle preuve V3 est immuable et peut contenir : intervenant, email, date/heure, déclaration, signature graphique PNG, empreinte SHA-256, acteur et contexte technique.

## Emargement automatique
I3 remplace la séquence automatique V2 INITIAL + RELANCE_1 + RELANCE_2 par un seul événement automatique INITIAL exactement au début réel du créneau. Les anciennes relances encore PENDING sont passées à SKIPPED ; les relances déjà envoyées restent historiques. Les relances manuelles restent disponibles.

## Reports / rattrapages
Les affectations multi-intervenants I2 restent copiées sur les reports/rattrapages. Une contresignature V3 est désormais une preuve historique empêchant une réécriture ou un report silencieux du créneau concerné.

## Documents
Les feuilles collectives et individuelles utilisent les contresignatures V3 et peuvent afficher plusieurs intervenants contresignataires avec leur signature graphique. Les exports JSON et ZIP incluent les nouvelles preuves.

## Hors périmètre I3
Les relances qualité HOT/COLD/TRAINER restent au périmètre I5. Microsoft Teams reste au périmètre I7.
