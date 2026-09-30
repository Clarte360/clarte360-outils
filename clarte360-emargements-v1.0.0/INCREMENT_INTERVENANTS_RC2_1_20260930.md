# INCRÉMENT INTERVENANTS RC2-1 — 30/09/2026

Version applicative : **3.0.0-INTERVENANTS-RC2-1**  
Statut : **à tester avant constitution du ZIP de recette**

## Objet

Consolider les retours de recette RC2_PROVISOIRE sur :
1. l'analyse IA globale du dossier professionnel ;
2. l'exploitation des propositions dans Qualifications ;
3. les tableaux de gestion de l'ensemble de l'application.

## Corrections IA

- Un seul lancement utilisateur depuis **Documents**.
- Analyse technique robuste : extraction factuelle unique puis lots de prestations.
- Délai API augmenté et retry contrôlé.
- **100 % des prestations actives doivent recevoir un résultat**.
- Une prestation sans preuve reste visible avec **niveau IA 0 / Aucun rapprochement**.
- Contrôle bloquant si un lot IA omet une prestation.
- Contrôle des critères : tout critère omis est replacé à 0 avec alerte.
- JPG/JPEG/PNG/WEBP conservés dans l'analyse multimodale.
- En cas d'échec d'une nouvelle tentative, aucun résultat partiel n'est enregistré et l'interface signale explicitement que l'analyse précédente est affichée.

## Qualifications

- Matrice enrichie : lecture IA, niveau proposé, confiance, critères IA, preuves IA, niveau humain.
- Bouton **Accepter les propositions IA de cette prestation**.
- Le niveau global humain n'est jamais validé automatiquement.
- Preuves de qualification : modification, changement de rattachement et retrait/suppression tracée.
- Correction du blocage du bouton de rétention des prestations proposées.

## Audit transverse des tableaux

Audit complet documenté dans :
`AUDIT_TRANSVERSAL_TABLEAUX_APPLICATION_RC2_1_20260930.md`

Après corrections : **87 rendus de tableaux**.

### Nouveaux points de gestion

- Tableau de bord : ouverture d'une action récente.
- Outils : suppression sécurisée si jamais utilisé ; sinon inactivation.
- Qualité : actions d'amélioration modifiables/supprimables avec audit.
- CAPA : statut ANNULEE disponible pour corriger une saisie sans détruire l'historique.
- Signalements : traitement direct depuis la fiche action.
- Organismes : suppression physique seulement sans dépendance.
- Agences : suppression physique seulement sans dépendance.
- Profils d'import : suppression de configuration sans suppression du fichier source.
- Intervenants / candidats / preuves / prestations / critères : gestion vivante consolidée.

Les tableaux de preuve, historique ou restitution restent volontairement en lecture seule et sont identifiés comme tels dans l'interface.

## Tests ajoutés / adaptés

- Alignement des anciens tests de version sur RC2-1.
- Tests exhaustivité IA.
- Tests modification/suppression des preuves.
- Tests CRUD organismes/agences/profils d'import.
- Tests modification/suppression actions d'amélioration.
- Test annulation CAPA.
- Garde-fou statique : tout tableau doit être actionnable ou explicitement justifié comme lecture seule/historique.

## Déploiement

Aucun déploiement n'est considéré validé tant que la campagne complète :

`PYTHONPATH=. ./.venv/bin/pytest -q`

n'est pas entièrement verte, suivie de la compilation et de la recette métier.
