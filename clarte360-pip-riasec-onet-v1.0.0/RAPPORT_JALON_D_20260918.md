# CLARTÉ360 PIP RIASEC / O*NET — RAPPORT JALON D
Date : 18/09/2026

## Base
Développement réalisé exclusivement à partir du Jalon C officiel récupéré depuis OneDrive.

## Périmètre D — O*NET
- Instrument : O*NET Interest Profiler Short Form, 60 activités, version anglaise officielle.
- API : O*NET Web Services API v2, endpoints `mnm/interestprofiler/questions` et `mnm/interestprofiler/results`.
- Réponses : valeurs officielles 1 à 5 ; 60 réponses obligatoires ; chaîne transmise dans l'ordre officiel des questions.
- Résultats : six scores RIASEC O*NET conservés tels que renvoyés par l'API et triés pour l'affichage par score décroissant.
- Aucune conversion des scores O*NET vers l'indice PIP 0–100.
- Aucune fusion, moyenne ou score composite PIP/O*NET.
- Comparaison uniquement descriptive des rangs/dominantes.
- Parcours PRE_PIP : résultat PIP masqué jusqu'à la fin d'O*NET.
- Parcours POST_PIP_RESULTS : choix après restitution PIP conservé et identifié.
- Métadonnées instrument/API/langue/question_count/timing conservées dans l'état O*NET.

## Non-régression
Banque PIP PIP-BANK-0.5, tableur maître V0.6 et scoring PIP inchangés.

## Références officielles vérifiées le 18/09/2026
- O*NET Web Services API v2 — Interest Profiler Short Form Questions.
- O*NET Web Services API v2 — Interest Profiler Results.
- O*NET Resource Center — Interest Profiler.

## Résultat
Jalon D prêt comme base du Jalon E.
