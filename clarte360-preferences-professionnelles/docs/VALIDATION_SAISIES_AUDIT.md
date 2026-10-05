# Audit des validations — Préférences professionnelles 1.9.6

## Entrées recensées
- identité bénéficiaire : prénom, nom, e-mail ;
- code d'accès à six chiffres ;
- formulaire de contact : prénom, nom, e-mail, téléphone, objet, message ;
- import JSON de reprise ;
- banque XLSX interne des 60 questions ;
- contexte futur de lancement Hub I9-H1 ;
- secrets SMTP et futur secret HMAC Hub.

## Règles ajoutées
- noms Unicode acceptés avec espaces, apostrophes et tirets ; chiffres/emoji/HTML incohérents refusés ;
- e-mail RFC simplifié, 254 caractères max, CR/LF et multi-adresses refusés ;
- téléphone international souple, 7 à 15 chiffres ;
- textes libres bornés et contrôlés contre les caractères de contrôle ;
- code d'accès exactement 6 chiffres ;
- JSON UTF-8, non vide, 2 Mo maximum, structure/identifiants/questions/options bornés ;
- reprise JSON 1.9.4 conservée ; JSON final déjà terminé refusé pour une reprise ;
- identifiants Hub sans traversal `..`, longueur bornée ; jeton signé HMAC, durée maximale 7 jours ;
- banque de questions contrôlée : 60 questions actives, 10 dimensions x 6, IDs uniques, champs texte présents, valeurs numériques finies.

Aucun calcul de score, coefficient, ordre métier ou interprétation n'a été modifié.
