# Clarté360 Gestion des Actions — J2C URGENT QUALITÉ RC3

Version : `3.0.0-I9-J2C-URGENT-QUALITE-RC3`
Date : 16/09/2026
Socle : J2 Correctif RC2, développement cumulatif.

## Correctifs urgents inclus

### 1. Worker communications Teams H-2 / H-15
- Prise en charge effective des types `TEAMS_REMINDER_H2` et `TEAMS_REMINDER_H15` dans le worker.
- Destinataires bénéficiaire et intervenant distingués.
- Le mail rappelle le numéro d'action, la date, l'horaire et le délai (2 h / 15 min).
- Le mail renvoie vers l'espace Clarté360 concerné et demande d'ouvrir l'onglet Teams.
- Aucun lien Teams direct n'est injecté dans ces rappels.
- Le courrier de confirmation planning rappelle que les formations en ligne sont rejointes depuis l'espace Clarté360 / onglet Teams.

### 2. Contresignature intervenant
- Alignement UX avec la signature bénéficiaire : choix entre signature manuscrite et `Nom et prénom + certification`.
- Canvas avec barre d'outils, souris / doigt / stylet.
- Conservation du contrôle anti-signature vide pour le mode manuscrit.
- Certification numérique autorisée et tracée avec `method=NOM_PRENOM`.
- Même logique appliquée au portail intervenant personnel et au lien direct/historique de contresignature.

### 3. Tableau de bord intervenant
- Les signatures bénéficiaires à régulariser ne comptent plus les créneaux futurs ou non terminés.
- Même règle pour les métriques de finalisation : seules les séances échues sont considérées.

## Reprise structurelle Qualité C + D

### 4. Tableau de bord Qualité
Deux blocs métier séparés :
- Files d'entrée : Points <=3, Difficultés/aléas, Réclamations, Non-conformités, Incidents, Signalements/contacts, Suggestions/améliorations, Autres.
- Plan d'action : Total, En cours, À vérifier, Clôturées, En retard.

Les données historiques `quality_issues` restent prises en compte tant qu'elles sont ouvertes et non migrées.

### 5. Signalements bénéficiaires / intervenants
- Tout signalement alimente automatiquement le moteur J2 `quality_events`.
- La nature initiale du signalement est conservée via son type métier (information, observation, difficulté, incident, réclamation, suggestion...).
- Une trace historique de compatibilité reste créée dans `quality_issues` avec statut `MIGRE`, sans double comptage dans les files ouvertes.

### 6. Points <=3
- `A_EXAMINER` reste une file d'entrée.
- Décision `Reprendre dans le plan d'action` : création d'un événement qualité + création immédiate d'une action du plan.
- Le point passe à `REPRIS_PLAN_ACTION`, et non à un statut ambigu `TRAITE`.
- Il n'est considéré comme clôturé qu'après réalisation et vérification de l'action.

### 7. Fiches qualité et plan d'action
- Responsable sélectionné parmi les administrateurs / intervenants Clarté360 connus, plus de responsable principal en texte libre.
- Échéances via calendrier.
- Statut CAPA `A_VERIFIER` disponible en plus de A_FAIRE / EN_COURS / EN_ATTENTE / TERMINEE.
- Le plan d'action conserve l'origine, l'action, le sujet, la personne/source, le responsable, l'échéance, le statut et l'efficacité.

### 8. Lecture questionnaires
- Traduction des rubriques intervenant I01 à I07 en libellés métier lisibles.
- Les codes internes restent techniques et ne constituent plus le libellé principal.

## Validation technique
- `pytest` : **304 passed**.
- `release_check.py` : **CANDIDATE TECHNIQUE OK**.
- Compilation/imports principaux : OK.

## Important déploiement
Le conteneur du ZIP est nommé `clarte360-emargements-v1.0.0` afin de correspondre au répertoire GitHub/VPS existant et de ne pas modifier les URL de déploiement.
