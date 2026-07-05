# Boussole Valeurs Pro v1.8 - Socle Clarte360 v3.0

## Modifications
- Barre laterale a deux etats : accueil institutionnel puis menu metier en premier dans le coeur de l'application.
- Suppression du bouton "Reinitialiser la session" des que la session beneficaire est active.
- Suppression de l'onglet RGPD du menu metier ; le bouton "RGPD et mentions legales" devient l'unique acces et affiche la tracabilite disponible.
- Rapport PDF Boussole restructure en document professionnel : page de synthese, roue, tableau des valeurs, pages de detail. Aucune interpretation ajoutee.
- Version application portee a 1.8 et socle a 3.0.

## Tests techniques
- Compilation Python : OK.

## Tests manuels a realiser apres deploiement
- SMTP reel avec Secrets Streamlit.
- Timeout reel apres 15 minutes sans activite.
- Verification navigateur de l'alerte de fermeture.
