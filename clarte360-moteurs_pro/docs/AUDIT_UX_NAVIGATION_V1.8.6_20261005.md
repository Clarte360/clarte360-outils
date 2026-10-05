# CLARTÉ360 — Moteurs professionnels — Audit UX / navigation V1.8.6

Date : 2026-10-05
Base fiable : V1.8.5 `1.8.5-json-save-fix-vps-hub`
Mode : ACCOMPAGNEMENT — outil bénéficiaire, support de réflexion et de débrief avec l'accompagnateur.

## Périmètre
Correction ergonomique ciblée sans modification du questionnaire, du scoring, des moteurs, des seuils, des graphiques ou du rapport métier.

## Évolutions
- logo Clarté360 visible dans la barre latérale ;
- questionnaire recentré sur la situation et les deux propositions ;
- progression fondée sur le nombre de réponses validées ;
- lecture vocale conservée et rendue compacte, avec boutons Écouter / Arrêter sans rerun Streamlit ;
- bouton `← Question précédente` pendant la passation ;
- les réponses déjà validées restent présentes lors des retours arrière ;
- la valeur validée d'une question est retrouvée lors de sa réouverture ;
- aucun élément de réponse suivant n'est supprimé lors d'une modification antérieure ;
- le garde-fou examine désormais tous les curseurs déjà rendus afin qu'un brouillon non validé ne soit pas masqué par une navigation arrière.

## Non modifié
- 60 situations / curseurs ;
- fichier XLSX métier ;
- ordre aléatoire ;
- calculs et scoring ;
- interprétations ;
- JSON métier et compatibilité de reprise ;
- rapport PDF ;
- Hub / VPS / SMTP / RGPD.

## Recette attendue
1. répondre à plusieurs questions ;
2. revenir d'une question ;
3. constater que la réponse précédente est bien repositionnée ;
4. la modifier puis valider ;
5. vérifier que les réponses suivantes déjà validées existent toujours ;
6. tester plusieurs retours successifs ;
7. déplacer un curseur sans valider, revenir en arrière puis vérifier que le garde-fou reste actif ;
8. vérifier Écouter / Arrêter ;
9. sauvegarde JSON, reprise JSON, fin de questionnaire, rapport PDF.
