# Intégration Gestion des Actions — H3.3-C

Ce dossier contient le patch nécessaire à l'écran `Études PIP/O*NET` de Gestion des Actions I9.

Fichiers concernés :
- `app.py` : nouvelle restitution collective de l'étude ;
- `services.py` : statut d'étude compatible H3.2/H3.3 et agrégats ;
- `study_analytics.py` : moteur pur de population, concordance et ressenti ;
- `db.py` : copie de référence inchangée pour contexte de reprise ;
- `tests/test_h33c_study_analytics.py` : tests ciblés H3.3-C.

Aucun profil individuel n'est affiché. Les calculs utilisent seulement les fichiers d'étude pseudonymisés déjà produits par PIP.

Ce patch ne doit pas être déployé indépendamment d'une vérification du dossier I9/Gestion des Actions officiel et du Framework VPS.
