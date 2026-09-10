# CLARTÉ360 — PIP RIASEC + O*NET
## Instructions de développement — Seconde partie après recette L1
**Date : 10 septembre 2026**  
**Base technique obligatoire :** `CLARTE360_PIP_RIASEC_ONET_L1-D_LIVRABLE1_v1.0.2_VPS`  
**Base métier :** `CLARTE360_PIP_RIASEC_TABLEUR_MAITRE_V0_4_CONTEXTES.xlsx`  
**Frameworks obligatoires :** Framework Clarté360 V4 + Framework VPS Clarté360 V1.0

## 1. Règle de départ
Ne pas repartir de zéro. Ne pas modifier le scoring, les 120 formulations source ou la séquence PIP/O*NET sans décision méthodologique explicite. Toute correction est additive et doit préserver les 39 tests L1 existants.

## 2. Priorité A — Corriger les anomalies de recette L1
### A1. Branding Clarté360
- Réintégrer le vrai logo Clarté360 issu du socle de référence.
- Logo visible au minimum sur l’accueil, la sidebar et la fin de parcours.
- Conserver une interface légère et mobile.

### A2. Sauvegarde / reprise publique
- Pendant toute la passation, afficher une commande claire `Sauvegarder ma passation (JSON)`.
- Le JSON doit contenir l’ordre, l’index courant, les réponses, le parcours, la version de banque et les métadonnées de reprise.
- À l’accueil, permettre `Reprendre une passation` par import du JSON.
- Reprendre exactement au bon item, sans perdre ni modifier les réponses.
- Aucun score intermédiaire ne doit être présent dans le JSON avant la fin de la passation.

### A3. Fin de parcours
- Interdire toute impasse après la question 120.
- `PIP_SEUL` : fin PIP → restitution PIP compréhensible → ressenti fermé → clôture.
- `PIP_PUIS_ONET60` : fin PIP → O*NET 60 → seulement ensuite restitution PIP/O*NET → ressenti.
- Le verrou anti-influence reste absolu.
- Tant que le rapport complet n’est pas encore développé, la restitution minimale doit présenter les 6 scores, leur sens, le profil relatif et le code Holland uniquement s’il est méthodologiquement justifié. Elle doit explicitement rappeler qu’un score n’est ni une compétence ni une prescription métier.

### A4. Fatigue / interruption
- Conserver la progression 1/120.
- Prévoir une transition neutre entre les blocs ACT / SIT / ENV.
- Permettre la pause via sauvegarde sans perdre la session.

## 3. Priorité B — Contextualisation des 120 items
Le tableur V0.4 contient une feuille `CONTEXTUALISATION` avec une proposition d’exemple concret pour chaque item.

Règles impératives :
- la colonne `formulation_source` reste inchangée ;
- l’exemple est affiché séparément sous la formulation, avec le libellé `Exemple concret :` ;
- l’exemple ne participe jamais au scoring ;
- il doit ancrer la facette cible sans introduire la dimension concurrente ;
- aucun exemple ne doit nécessiter une compétence, un diplôme ou une expérience préalable ;
- éviter jargon, prestige, stéréotype de genre, génération ou secteur ;
- les exemples sont versionnés dans la ressource runtime et traçables par `item_id`.

Avant publication, exécuter des contrôles automatiques : 120 exemples, 120 IDs uniques, correspondance 1:1 avec la banque, aucune formulation source modifiée, aucune dimension/facette modifiée.

## 4. Priorité C — Mode bénéficiaire accompagné
Ne pas créer un deuxième système de compte dans le PIP.

La source d’identité reste Gestion des actions / Espace bénéficiaire existant. L’intégration doit se faire par un connecteur générique : bénéficiaire + action + participant + prescription + droits.

État actuel constaté : Gestion des actions I8 possède les comptes bénéficiaires et l’onglet `Mes questionnaires / actions`, mais ne fournit pas encore le mécanisme générique de prescription PIP décrit dans le CDC. Le raccordement complet doit donc être construit conjointement avec l’incrément Gestion des actions prévu pour ce connecteur, et non simulé par un login local PIP.

Côté PIP, préparer/maintenir :
- un point d’entrée `ACCOMPAGNEMENT` distinct de PUBLIC ;
- validation d’un lancement signé ;
- interdiction d’identifiants Clarté360 en mode PUBLIC ;
- persistance serveur de la passation accompagnée ;
- publication future des événements `CONSULTÉ / EN_COURS / TERMINÉ`.

## 5. Tests obligatoires
- Tous les tests L1 existants doivent rester verts.
- Ajouter tests branding/ressources, snapshot/reprise au milieu d’une passation, fin question 120, verrou O*NET, 120 exemples, correspondance IDs et absence de modification des formulations source.
- Commande VPS de référence : `PYTHONPATH=. .venv/bin/pytest -q`.
- Compilation Python complète.
- Scan secret/cache/.venv/data de production avant ZIP.

## 6. Livrables attendus de cette seconde partie
1. Tableur métier : `CLARTE360_PIP_RIASEC_TABLEUR_MAITRE_V0_4_CONTEXTES.xlsx`.
2. ZIP applicatif cumulatif corrigé, dérivé de v1.0.2 VPS.
3. Rapport court de tests.
4. Changelog précisant ce qui est corrigé et ce qui dépend encore du connecteur Gestion des actions.

## 7. Règle de déploiement
Toujours : correction locale → tests → ZIP → GitHub Desktop Commit/PUSH → VPS `git pull` → tests VPS → compilation → restart systemd → recette.
Aucune correction définitive uniquement sur le VPS.
