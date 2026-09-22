# CLARTÉ360 — Intervenants J17 — Action → Prestation → Intervenant
Date : 21/09/2026

## Objectif
Rendre opérationnelle et visible la chaîne métier ACTION → PRESTATION → EXIGENCES DE QUALIFICATION → INTERVENANT → CONTRÔLE D’ADÉQUATION → INSTRUCTION HUMAINE.

## Réalisé
- Le rattachement d'une action à une prestation est explicite : aucune première prestation du catalogue n'est sélectionnée silencieusement.
- À la création d'une action, le titre reste libre et une prestation Clarté360 peut être liée séparément avec niveau humain minimum et exigence éventuelle de complétude des critères obligatoires.
- Une prestation absente peut être créée rapidement depuis l'écran de création d'action, dans une famille existante, sans remplacer l'intitulé libre de l'action.
- Pour les actions importées, des prestations proches peuvent être suggérées à partir de l'intitulé ; la suggestion ne vaut jamais sélection automatique.
- Lorsqu'un référent est choisi à la création et qu'une prestation est liée, l'affectation passe par le contrôle de qualification du dossier professionnel.
- Les intervenants déjà affectés affichent désormais en permanence leur statut relatif à la prestation de l'action : QUALIFIE, NON_QUALIFIE, NIVEAU_INSUFFISANT, CRITERES_INCOMPLETS ou A_VERIFIER.
- Le motif du statut est affiché (absence de validation humaine, niveau insuffisant, critères obligatoires incomplets, prestation non rattachée...).
- Un bouton « Étudier / valider cette qualification » ouvre directement le dossier professionnel concerné et positionne la prestation à instruire.
- Après décision humaine, le statut est recalculé à partir de la qualification réellement enregistrée.
- L'affectation exceptionnelle reste possible uniquement avec justification et audit ; elle n'altère jamais la qualification humaine.
- Le pont de compatibilité trainer_id ↔ professional_person_id est conservé pour l'historique de Gestion des Actions.

## Garde-fous
- CANDIDAT non affectable.
- IA seule insuffisante pour rendre un intervenant qualifié.
- Aucun choix automatique de prestation à partir d'une simple ressemblance de titre.
- Le titre d'action et la prestation de catalogue restent deux données distinctes.
- Aucun changement VPS / production dans ce jalon.
