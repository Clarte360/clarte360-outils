# Clarté360 Émargements — Rapport tests V1.1.0

Date de construction : 2 septembre 2026.

## Vérifications automatisées

- Compilation Python de `app.py`, `services.py`, `db.py`, `pdf_utils.py`, `worker.py`, `backup.py` : OK.
- Pytest : **7 tests réussis sur 7**.
- Couverture métier ajoutée : verrouillage d'un créneau avec preuve, absence, rattrapage collectif, report conservant l'historique, réinitialisation PIN, exigences du certificat et rattrapage d'une absence.

## À tester impérativement sur le VPS avant mise en production

1. migration d'une copie de la base V1.0.0 réelle ;
2. signature manuscrite et signature nom/prénom ;
3. régularisation a posteriori et mentions PDF ;
4. espace intervenant sur smartphone ;
5. absence puis rattrapage individuel et collectif ;
6. report d'un créneau futur ;
7. contresignature ;
8. SMTP OVH réel ;
9. affichage Europe/Paris été/hiver ;
10. sauvegarde et restauration ;
11. génération des PDF et du certificat définitif.

Cette archive est une candidate V1.1.0 à recette : elle ne doit pas remplacer directement la version VPS sans sauvegarde et test sur copie de la base.
