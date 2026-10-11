# CLARTE360 - GDA - Increment J6 (P5-RC2) - 10 octobre 2026

## Version de depart
ZIP complet J5 - SHA256 978cf6264c20e01439cbbda68336f06eb5285890057785f094b22e70f96a5500.

## Evolution fonctionnelle
- Espace Intervenant : accueil personnel autonome, dossier partage, missions, interventions, echanges ; les compteurs d'emargement globaux ne sont visibles que dans le tableau de bord personnel.
- Administration : accueil Intervenants & Partenaires, deux parcours Dossiers professionnels et Pilotage & referentiels ; sept rubriques conservees sans tableau general repete dans chaque fiche.
- Documents professionnels : visibilite INTERNE par defaut, partage admin explicite vers INTERVENANT, droit verifie cote services et au moment du telechargement, notification personnelle J4, revocation immediate, aucune note interne publiee tacitement.
- Prescriptions : possibilite pour intervenant habilite de renseigner uniquement le suivi pedagogique sur une prescription creee par un autre auteur ; aucun statut issu d'un connecteur modifiable, aucun droit de supprimer la prescription d'un autre, aucun ecrasement du statut TERMINE.
- Liens entre une mission et ses documents contractuels prepares pour J8, sans nouveau moteur contractuel.

## Tests
- Campagne complete : 791 tests sur 791 reussis. Deux tests de structure d'ancienne navigation remplaces par des exigences J6 sans supprimer leurs autres controles.
- Nouveaux tests : `tests/test_p5_rc2_j6_intervenant.py`, 16 cas, securite, docs, statuts et ergonomie structurelle.
- Tests de lecture seule, pas de recette navigateur definitive ; recette metier a realiser apres installation unique de la RC2 finale.

## Gouvernance
Ce ZIP est un CANDIDAT J6 de travail, non deployable. Les seuls changements autorises sont locaux. Ne jamais transferer sur GitHub, reserve au proprietaire apres remise du ZIP FINAL P5-RC2. Aucun VPS. Le registre COR/AME edition 0.9 reste intact. L'etape suivante J7 est soumise au GO de l'utilisateur.
