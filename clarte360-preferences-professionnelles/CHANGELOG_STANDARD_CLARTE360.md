# CHANGELOG STANDARD CLARTÉ360

## v1.9.4-socle-clarte360 - 05/07/2026

- Alignement renforcé de l'écran d'accueil sur le socle Clarté360 : choix initial JSON / nouvelle session avant l'entrée dans le questionnaire.
- Correction de l'affichage du module d'import JSON : l'upload n'apparaît plus immédiatement dans la barre latérale, mais uniquement après choix de reprise.
- Rapport PDF : coordonnées institutionnelles Clarté360 placées en pied de page sur chaque page, avec numérotation.
- Fin de questionnaire : ajout d'un avertissement visible avant transmission automatique du JSON final à Clarté360, puis confirmation de transmission.
- Version applicative mise à jour en v1.9.4-socle-clarte360.
- Logique métier, questionnaire, calculs, scores et interprétations inchangés.

## v1.9.3-socle-clarte360
- Correction de l'erreur validate_question_bank.

## v1.9.2-socle-clarte360
- Alignement RGPD / traçabilité / code d'accès.

## v1.9.6-validation-saisies-vps-hub-ready-garde-fou - 12/09/2026

- Ajout d'une couche `validation.py` centralisée pour les entrées utilisateur et les JSON de reprise.
- Noms internationaux légitimes, apostrophes et tirets conservés ; chiffres, contrôles et contenus incohérents refusés.
- E-mails protégés contre multi-adresses et CR/LF ; téléphone international contrôlé souplement.
- Code d'accès généré avec `secrets` et validé sur exactement six chiffres.
- JSON de reprise limité à 2 Mo, UTF-8, structure bornée, identifiants/questions/options validés.
- Compatibilité de reprise testée avec le format JSON 1.9.4 Streamlit Cloud.
- Banque XLSX vérifiée : 60 questions actives, 10 dimensions x 6, IDs uniques, champs et nombres cohérents.
- Préparation VPS : identité applicative, URL cible, service systemd exemple, secrets exemple.
- Préparation Hub I9-H1 : contrat HMAC signé, rôles prescripteurs `admin` et `intervenant`, retours limités au statut/référence documentaire.
- Questionnaire, scores, calculs, ordre métier et interprétation inchangés.


## 1.9.6 - Garde-fou sauvegarde JSON
- Protection F5/fermeture/navigation active tant que l etat metier a change depuis le dernier JSON telecharge.
- Re-armement automatique apres toute nouvelle reponse ou selection non encore validee.
- Import JSON considere comme point de sauvegarde de reference.
- Les traces techniques et timers ne declenchent pas de fausse alerte.


## v1.9.7-json-save-report-equivalence-vps-hub - 05/10/2026

- Correctif critique de sauvegarde JSON : suppression du payload de sortie mis en cache ; reconstruction du JSON depuis l'état validé courant au moment où le bouton de téléchargement est rendu.
- Liaison du garde-fou à l'empreinte exacte du contenu sérialisé ; une réponse sélectionnée mais non validée n'est jamais considérée comme sauvegardée.
- Sortie utilisateur sécurisée par un écran dédié jusqu'au téléchargement du JSON.
- Même principe d'empreinte appliqué au JSON de timeout et au JSON final.
- Rapport écran/PDF renforcé pour atteindre un niveau de lecture comparable à Moteurs professionnels : détail des 10 dimensions, question explorée, description, pôles bas/haut et position sur le continuum.
- Première lecture reformulée : un score faible est présenté comme une position vers le pôle bas et non comme une absence de préférence.
- Histogramme et radar inchangés.
- Questionnaire, 60 questions, cotations, scoring et formules de calcul inchangés.

### Jalon 3 - identité VPS
- Correction du port historique/proposé `8514` vers le port officiel réservé `8507`.
- Service confirmé : `clarte360-preferences-professionnelles.service`.
- Dossier stable confirmé : `/opt/clarte360/clarte360-outils/clarte360-preferences-professionnelles/`.
