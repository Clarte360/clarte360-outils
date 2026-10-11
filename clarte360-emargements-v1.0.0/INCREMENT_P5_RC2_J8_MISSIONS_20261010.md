# P5-RC2 — J8 : couverture des missions et pont contractuel / fournisseur

Date : 10 octobre 2026 | Développement isolé, hors GitHub et hors VPS.

## Objet et règle métier

L'action est le point d'entrée : choix du ou des intervenants, mission et responsable du suivi (y compris ELEARNING). En brouillon, l'action peut être incomplète ; les actions nouvelles créées avec le donneur d'ordre (parcours J7) activent le contrôle renforcé `ENFORCE`. La validation opérationnelle exige pour **chaque intervenant actif** une mission et une référence de document accepté vérifiée administrativement. Les actions anciennes restent en mode de consultation `PREVIEW` jusqu'à activation volontaire du contrôle, sans blocage rétroactif inattendu.

Le type de document dépend du statut du dossier professionnel : salarié → lettre/ordre de mission ; mandataire associé → lettre/validation de mission ; sous-traitant → contrat/bon de sous-traitance et fournisseur référencé. Les autres statuts (`A_DEFINIR`, stagiaire...) ne sont pas validables sans étude humaine.

## Réalisation locale

- Module `mission_engagements.py` et schéma additif : `action_mission_policy`, `action_mission_engagements`, `action_mission_events`, `action_mission_outbox`.
- `services.py` : création d'action J7 avec politique atomique, création automatique d'une mission sur affectation active, historisation en cas de retrait, changement de rôle ou référent ; contrôle renforcé dans `activate_action`.
- `app.py` : contrôles visibles dans la fiche Action, rubrique Intervenants, choix de mission, saisie contrôlée des références de document déjà accepté, refus/annulation/avenants ; dossier professionnel et Espace Intervenant personnel en lecture autorisée.
- Outbox locale d'événements versionnés `CLARTE360_GDA_MISSION_EVENT_V1` : **A_RACCORDER**, sans appel API, sans transmission effective, sans paiement ni reprise de la base Gestion Clients.
- `purge_guard.py` : empreinte de suppression J1 étendue aux quatre nouvelles tables J8, y compris celles sans colonne entière `id`.

## Précautions et limites

1. GDA **ne génère ni ne signe** le bon de mission. Le document est produit, validé et conservé juridiquement par la future application Contractualisation (13), ou transmis par un circuit externe vérifié ; GDA enregistre une référence et une attestation de vérification humaine, **pas une validation cryptographique** de signature.
2. Le fournisseur et les montants restent maîtres dans Gestion Clients (17). `supplier_id` et `cost_commitment_ref` sont des références techniques ; aucune facture ou paiement n'est créé ni accepté ici.
3. Les archives des missions sont consultables par numéro de document et version ; **l'ouverture du PDF définitif doit être raccordée et recettée ultérieurement** avec le dépositaire des documents contractuels et les autorisations appropriées.
4. L'intégration authentifiée avec les applications 13/17 et la recette des factures multi-actions, écarts, rejets et avenants restent à réaliser. L'outbox ne prétend pas être un bus d'événements opérationnel.
5. Les actions historiques en cours ne sont pas automatiquement bloquées : seul l'administrateur peut activer le garde-fou renforcé sur une ancienne action.
6. L'installation définitive P5-RC2 n'aura lieu qu'une fois, après le ZIP final et l'intervention GitHub du propriétaire exclusivement.

## Tests techniques

Fichier principal : `tests/test_p5_rc2_j8_missions.py` — schémas, statut de collaboration, absence de référent, e-learning, multipersonnes, preuve/avenants, sous-traitance, sécurité, suppression, outbox, décisions, rollback. Les preuves exactes de campagne sont jointes au dossier J8 officiel OneDrive.

## Prochain jalon

Après accord explicite du propriétaire : **J9 — dates, formats régionaux et finitions d'ergonomie**. Partir du ZIP J8 complet figé ; registre COR/AME édition 0.9 inchangé.
