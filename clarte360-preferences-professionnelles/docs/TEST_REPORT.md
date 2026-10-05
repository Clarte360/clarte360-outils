# Rapport de tests — Préférences professionnelles 1.9.7

Date : 05/10/2026

## Commandes exécutées
- `python -m py_compile app.py guard_state.py validation.py hub_contract.py`
- `PYTHONPATH=. pytest -q`

## Résultat
- Compilation Python : **OK**.
- Tests automatisés : **57 réussis / 57**.

## Couverture déjà présente
- validation des noms, e-mails, téléphones, textes et codes d'accès ;
- JSON UTF-8, taille, structure, reprise 1.9.4, questions/options ;
- structure de la banque XLSX : 60 questions, 10 dimensions x 6 ;
- contrat Hub HMAC, rôles, scopes, expiration et identifiants ;
- garde-fou navigateur sur état modifié et sélection non validée.

## Régressions ajoutées en 1.9.7
- distinction entre empreinte de l'état courant et empreinte de l'état réellement sérialisé dans le JSON ;
- une sélection radio non validée reste non sauvegardée après téléchargement du JSON ;
- le JSON de barre latérale est reconstruit à chaque rendu et n'utilise plus `exit_json_payload` comme cache ;
- présence de l'écran de sortie dédié ;
- référentiel `Dimensions` complet pour les 10 lectures détaillées ;
- présence des sections détaillées écran/PDF ;
- fonctions histogramme et radar conservées.

## Contrôle PDF de recette technique
Un rapport PDF de démonstration a été généré directement à partir des fonctions de la V1.9.7 et du classeur officiel :
- format A4 ;
- 4 pages ;
- histogramme et radar lisibles ;
- 10 dimensions détaillées ;
- aucun titre de dimension isolé en bas de page ;
- pied de page et pagination présents.

## Contrôles d'intégrité métier
Comparaison AST entre la V1.9.6 source et la V1.9.7 :
- `compute_results` : inchangé ;
- `interpretation_level` : inchangé ;
- `plot_bar_results` : inchangé ;
- `plot_radar_results` : inchangé.

Le fichier `data/questions_preferences_professionnelles_v1.xlsx` n'a pas été modifié.

## Limite avant mise en service
Le runtime local d'audit ne contient pas Streamlit. Le démarrage réel de l'interface, le clic utilisateur et la recette Hub/VPS devront être vérifiés au Jalon 3 / déploiement. Cette limite n'affecte pas la compilation, les tests de logique ni la génération PDF contrôlée ici.
