# P5-RC2 / J5 - Administration generale et navigation des actions (10/10/2026)

## Perimetre
- COR-001, COR-011 (presentation J5), AME-001, AME-002, AME-003.
- Deux espaces distincts apres authentification, tableau de bord propre a chaque espace ; transition avec confirmation de saisie potentiellement non sauvegardee.
- Gestion des actions seule contient creation, import, recherche, selection et les 12 rubriques conservant leurs services metier.
- Recherche SQL sur toutes les identites participantes, filtre statuts/prestations/annees, archives masquees par defaut, pagination 25/50, premiere personne inscrite et effectif.
- Liaisons _next_nav, qualification d'intervenant, et notifications J4 restaurees sans confusion de menu ; aucun nouveau droit n'est confere.
- L'intitule Parametres de l'action n'est presente qu'une fois.

## Tests
- 21 tests nouveaux `tests/test_p5_rc2_j5_admin_navigation.py` ; test historique de navigation professionnel adapte au nouveau classement.
- Campagne complete `PYTHONPATH=. pytest -q` : 775/775 PASS en 118.09 s.
- Verification locale fictive : 205 actions, 6 archives, 199 visibles sur 8 pages, second stagiaire retrouvable.

## Limites et gouvernance
- Code local isolé, aucune entree de donnees de production, aucune mise en ligne.
- Recette d'interface en navigateur et non-regression intermodulaire a reprendre en J10 / J11 puis apres unique deploiement RC2.
- Registre COR/AME officiel edition 0.9 non modifie.
- Seul le proprietaire agit sur GitHub, uniquement avec le ZIP final P5-RC2.
