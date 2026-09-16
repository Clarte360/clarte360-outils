# RAPPORT — JALON 1 A+B RC2 — 15/09/2026

## Périmètre demandé
Correctif strictement limité à :
1. fonctionnement du système des outils Clarté360 ;
2. gestion de la suppression définitive d'une action.

## Diagnostic production CLA0004
- CLA0004 = action_id 8.
- Base SQLite intègre ; index UNIQUE(action_id, tool_id) présent.
- Catalogue central cohérent : PIP RIASEC et Boussole actifs/prescriptibles ; autres outils référencés mais planifiés.
- `action_tool_permissions` : 0 ligne sur CLA0004 après tentative UI.
- `tool_prescriptions` : historique conservé (une prescription ADMIN annulée, une prescription INTERVENANT active).
- Conclusion : le moteur de persistance isolé était valide, mais le parcours UI réel n'assurait pas de confirmation transactionnelle de la sélection.

## Correctifs Outils
- Enregistrement des outils autorisés effectué via `st.form` + `form_submit_button`.
- Après sauvegarde, relecture immédiate de la DB et comparaison stricte avec la sélection demandée.
- En cas d'écart : erreur d'interface tracée, aucune fausse confirmation utilisateur.
- Ajout et retrait d'outils gérés par la même sélection complète.
- Une prescription existante n'est pas supprimée si l'outil est ensuite retiré de l'action.
- Le doublon actif action + bénéficiaire + outil reste interdit, quel que soit le créateur.
- Tableau des prescriptions : affichage explicite du prescripteur réel et de son rôle.

## Correctifs Suppression action
- Commande de suppression conservée uniquement dans `Actions`.
- Authentification administrateur obligatoire.
- Sans signature/contresignature : confirmation n° action + mot de passe.
- Avec signature/contresignature : suppression bloquée sauf si :
  - « Est-ce une action d'essai ? » = Oui ;
  - « Avez-vous totalement terminé les essais ? » = Oui ;
  - n° action correct ;
  - mot de passe administrateur correct.
- Si une réunion Teams distante existe, suppression Graph tentée avant la purge locale. Si Graph échoue, la purge locale est bloquée.
- Purge locale : données action, participants, créneaux, signatures, contresignatures, outils/prescriptions, documents/références, qualité, communications et données Teams locales.
- Les identités permanentes partagées (bénéficiaires/intervenants) sont conservées.

## Validation technique
- `python -m py_compile app.py services.py graph_client.py` : OK.
- `PYTHONPATH=. pytest -q` : **299 passed**.
- `python release_check.py` : **CANDIDATE TECHNIQUE OK**.

## Recette ciblée VPS après déploiement
1. CLA0004 > Outils : sélectionner PIP + Boussole, enregistrer, vérifier compteur = 2.
2. F5 : vérifier que les 2 restent sélectionnés.
3. Retirer Boussole, enregistrer, F5 : PIP seul autorisé ; prescription historique Boussole toujours visible.
4. Vérifier « Prescrit par » : nom/email + rôle.
5. Vérifier qu'une prescription active existante empêche un doublon ADMIN/intervenant.
6. Créer une action d'essai sans signature puis supprimer depuis Actions avec mot de passe.
7. Créer/choisir une action d'essai signée : vérifier blocage tant que les deux confirmations d'essai ne sont pas à Oui.
