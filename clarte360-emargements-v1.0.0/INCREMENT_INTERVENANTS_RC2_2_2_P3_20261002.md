# INCREMENT — INTERVENANTS RC2-2-2 P3 — DOSSIER UX — 02/10/2026

## Base de départ
- Checkpoint validé : `3.0.0-INTERVENANTS-RC2-2-2-P2`.
- Périmètre : P3 du CDC RC2-2-2 V1.0.
- Aucun déploiement GitHub/VPS pendant ce jalon.

## Réalisations P3
1. Navigation du dossier réduite à 7 écrans métier : Synthèse, Parcours professionnel, Conformité & collaboration, Analyse IA, Qualifications, Missions / Affectations, CV Clarté360.
2. Navigation pilotable par état (`st.radio`) afin qu'un deep-link puisse réellement ouvrir Qualifications ou Analyse IA ; suppression de la dépendance du dossier à des `st.tabs` non pilotables.
3. Cockpit Synthèse : statut, collaboration, complétude, conformité, qualifications, points ouverts, alertes/révisions, missions, services humainement validés et bloc « À faire maintenant ».
4. Candidature contextuelle : le workflow candidature est visible dans Synthèse uniquement pour un CANDIDAT ; il ne monopolise plus un onglet d'un INTERVENANT.
5. Parcours professionnel regroupé : expériences, spécialités, diplômes/formations, langues, certifications et habilitations.
6. Analyse IA placée immédiatement avant Qualifications ; documents, consentement, analyse différentielle et propositions restent réunis.
7. Aide unique `ⓘ Comprendre cet écran` pour chaque écran du dossier.
8. Qualification : préremplissage IA non décisionnel, grille humaine 0–4, points à vérifier actionnables, validation finale explicite ; verrou humain retiré de l'interface.
9. Dates métier principales converties en date-pickers : révision qualification, validité document, NDA/Qualiopi.
10. Missions / Affectations : projection des Actions actives de la personne avec rôle, référent, prestation et état d'éligibilité/qualification.

## Fichiers principaux modifiés
- `app.py`
- `services.py`
- `tests/test_intervenants_rc2_2_2_p3_ux.py`
- documentation de jalon.

## Hors P3 / étapes suivantes
- P4 : refonte transversale des tableaux de pilotage et priorisation DRH.
- P5 : raccordement complet Action -> Qualification -> Retour Action et ouverture directe de l'Action depuis Missions.
- P6 : CV / finition et audit final.

## Statut
P3 terminé et testé. Le checkpoint n'est pas une RC de déploiement.
