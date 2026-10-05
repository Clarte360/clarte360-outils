# Audit correctif JSON + rapport — Préférences professionnelles V1.9.7

Date : 05/10/2026

## Périmètre
Deux écarts du Jalon 1 sont corrigés sans modifier le questionnaire, les cotations ni les calculs :
1. empêcher le téléchargement d'un JSON préparé avant les dernières réponses ;
2. porter la restitution au niveau de lecture attendu par comparaison avec Moteurs professionnels.

## Correctif JSON
La V1.9.6 conservait `exit_json_payload` en mémoire après « Préparer mon JSON ». Une poursuite du questionnaire pouvait donc laisser disponible un contenu antérieur, puis le callback marquait l'état courant comme sauvegardé.

La V1.9.7 supprime ce cache de contenu. Tant que le bouton de téléchargement est visible, ses octets JSON sont reconstruits depuis l'état validé courant à chaque rendu Streamlit. L'empreinte enregistrée au téléchargement correspond uniquement aux données réellement sérialisées dans ce JSON.

Une sélection radio non encore validée n'est pas sérialisée. Elle continue donc à rendre le garde-fou actif même si un JSON vient d'être téléchargé.

Le bouton « Quitter et télécharger mon JSON » place désormais l'application sur un écran de sortie dédié. Le bénéficiaire reste protégé tant que le JSON correspondant à l'état validé courant n'a pas été téléchargé.

## Rapport enrichi
Les sources de lecture restent celles de l'application et du classeur `questions_preferences_professionnelles_v1.xlsx` :
- libellé de la dimension ;
- question explorée ;
- interprétation basse ;
- interprétation haute ;
- description existante dans l'application ;
- pourcentage et lecture déjà calculés.

Le rapport écran et le PDF présentent désormais les dix dimensions avec ces repères. Le texte précise qu'un pourcentage faible situe les réponses vers le pôle bas de la dimension et ne signifie pas « absence de préférence ».

## Graphiques
Aucune modification des fonctions d'histogramme et de radar. Export PDF maintenu à 180 dpi, radar 0–100.

## Métier inchangé
- 60 questions actives ;
- 10 dimensions x 6 questions ;
- cotations 0 à 3 ;
- score maximum 18 par dimension ;
- formule pourcentage inchangée ;
- ordre aléatoire des questions et propositions inchangé.
