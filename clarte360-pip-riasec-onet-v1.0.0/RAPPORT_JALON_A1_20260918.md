# CLARTÉ360 — PIP RIASEC / O*NET — RAPPORT JALON A1

Date : 18/09/2026
Base : Jalon A livré le 18/09/2026
Objet : finalisation méthodologique et gouvernance de la banque PIP 72 items avant Jalon B.

## 1. Résultat

Le Jalon A1 conserve la cible validée de 72 items : 12 items pour chacune des dimensions R, I, A, S, E et C. Les 30 facettes restent couvertes avec au minimum deux items par facette.

Le scoring n'a pas été modifié.

## 2. Philosophie de formulation retenue

Chaque item décrit désormais une activité professionnelle à l'infinitif. La réponse porte sur l'envie de réaliser cette activité, et non sur la compétence perçue, le métier actuel ou une aptitude supposée.

Consigne active :

« Pour chacune des activités suivantes, indiquez dans quelle mesure vous aimeriez la réaliser dans votre travail. Répondez selon votre envie, et non selon ce que vous savez déjà faire, votre métier actuel ou ce que vous pensez devoir aimer. »

Échelle active :
1. Je n’aimerais pas du tout faire cela
2. J’aimerais peu faire cela
3. Je suis partagé(e) / sans préférence marquée
4. J’aimerais assez faire cela
5. J’aimerais beaucoup faire cela

Exemple confirmé :
« Analyser et comparer plusieurs informations ou observations pour comprendre ce qui les distingue. »

Cette formulation mesure un intérêt de type Investigateur sans supposer que la personne exerce un métier particulier et sans l'orienter automatiquement vers un autre métier.

## 3. Tableur maître V0.6

Source métier active : `docs/sources/CLARTE360_PIP_RIASEC_TABLEUR_MAITRE_V0_6_ACTIF.xlsx`.

Trois onglets seulement sont visibles par défaut :
- `01_QUESTIONS_72`
- `02_REPONSES_CONSIGNE`
- `03_REVUE_HISTORIQUE`

Les anciens onglets sont conservés dans le fichier pour l'historique, la méthode, les contrôles et la traçabilité, mais sont masqués afin de simplifier l'usage quotidien.

## 4. Source de vérité et absence de questions en dur

Le tableur maître est la source métier des 72 formulations.

Le script `scripts/build_pip_runtime.py` :
- lit exclusivement le tableur maître actif ;
- contrôle le nombre d'items ;
- contrôle la répartition 12 x 6 ;
- contrôle les 30 facettes ;
- contrôle les IDs ;
- contrôle `item_version` et `bank_version` ;
- lit la consigne et les cinq libellés de réponse ;
- génère `resources/runtime/pip_bank_PIP-BANK-0.5.json`.

La commande `python scripts/build_pip_runtime.py --check` échoue si le JSON versionné ne correspond plus exactement au tableur maître.

Ainsi, une future modification d'une question se réalise dans le tableur maître puis entraîne une régénération contrôlée du JSON. La formulation n'est pas maintenue en double dans le code Python.

## 5. Versions méthodologiques

- Tableur maître : V0.6
- Banque runtime : PIP-BANK-0.5
- Item version : 0.6
- Scoring : inchangé
- Jalon : A1

## 6. Périmètre non traité

Aucune fonctionnalité du Jalon B (RGPD, timeout, navigation, sauvegarde/reprise) n'a été modifiée dans A1.
