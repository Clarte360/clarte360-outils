# Plan de test Streamlit Cloud - V1.0.0

1. Configurer `[security].admin_password` dans les Secrets.
2. Charger `GESTION OF CLARTE360_CONTRACTUALISATION_V1.xlsm`.
3. Vérifier le message « macros VBA détectées ».
4. Choisir « Créer / compléter depuis une APS JSON ».
5. Charger une APS valide.
6. Vérifier que la première ligne CLA libre est proposée.
7. Vérifier l'identité et corriger si nécessaire.
8. Saisir / vérifier 13 h, le calendrier, le consultant et la modalité.
9. Saisir le prix TTC.
10. Ajouter les financeurs et vérifier que l'équilibre est à 0,00 €.
11. Générer.
12. Télécharger la base XLSM et l'ouvrir dans Excel.
13. Vérifier que les macros historiques fonctionnent toujours.
14. Vérifier `CONV ADM` sur le NO_CLAR créé.
15. Vérifier les lignes correspondantes dans `FINANCEMENTS`.
16. Vérifier que les formules de `STAGIAIRE` et `FACTURATION` se recalculent après ouverture dans Excel.
17. Télécharger et contrôler le contrat PDF.
18. Vérifier le JSON contractuel.

Test technique réalisé hors Streamlit avant livraison : le hash SHA-256 de `xl/vbaProject.bin` est identique avant/après mise à jour de la base.
