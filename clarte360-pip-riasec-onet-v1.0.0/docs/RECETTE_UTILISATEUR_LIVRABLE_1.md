# Clarté360 PIP RIASEC + O*NET — Recette utilisateur Livrable 1

Version 1.0.0-l1 — L1-D

## Préparation
1. Installer les dépendances : `python -m pip install -r requirements.txt`.
2. Lancer : `streamlit run app.py`.
3. Vérifier l'ouverture de l'accueil Clarté360 sans erreur et sans secret O*NET local.

## R1 — Accueil / cadre PIP
- Vérifier que le PIP est présenté comme complet et autonome.
- Vérifier qu'il mesure l'attraction / l'intérêt et non compétence, aptitude, intelligence ou personnalité.
- Vérifier l'accès RGPD puis l'introduction PIP.

## R2 — Choix du parcours
- Tester « PIP seul ».
- Tester « PIP + comparaison facultative O*NET 60 en anglais ».
- Vérifier qu'aucun parcours O*NET seul n'est proposé.

## R3 — Passation 120 items
- Vérifier les 3 blocs métier et la progression jusqu'à 120/120.
- Vérifier l'échelle fermée 1 à 5 et ses libellés.
- Vérifier que dimension, facette, score et interprétation ne sont jamais visibles pendant la passation.
- Revenir à une question précédente, modifier la réponse puis poursuivre.

## R4 — PIP seul
- Terminer les 120 réponses.
- Vérifier que la passation est acceptée comme complète et que le scoring est calculé sans résultat intermédiaire durant le questionnaire.
- Le rapport bénéficiaire détaillé n'appartient pas au Livrable 1.

## R5 — Parcours PIP + O*NET
- Choisir ce parcours puis terminer le PIP.
- Vérifier qu'aucun résultat PIP n'est affiché après le PIP.
- Vérifier l'écran indiquant que la passation O*NET appartient au lot dédié.
- Le verrou anti-influence doit rester actif tant que `onet_state.completed` est faux.

## R6 — Sauvegarde / reprise
- Télécharger une sauvegarde depuis l'accueil ou après interruption.
- Recharger le JSON depuis l'accueil.
- Vérifier le retour à la progression enregistrée avec réponses conservées.

## R7 — Mode accompagné — smoke test technique uniquement
- Ouvrir `?mode=accompagnement&beneficiary_id=B1&action_id=A1&prescription_id=P1`.
- Vérifier l'affichage de l'action et du bénéficiaire.
- L'intégration signée Gestion des actions appartient à un lot ultérieur.

## Critère de validation L1
Le Livrable 1 est recevable si R1 à R7 sont conformes, sans erreur bloquante, sans fuite de dimension/facette pendant la passation, sans résultat PIP prématuré dans le parcours O*NET et avec reprise fonctionnelle.
