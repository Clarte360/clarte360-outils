# Clarté360 - Préférences professionnelles

Version : **v1.9.8-ux-navigation-retour**

Application bénéficiaire Clarté360 d'exploration des préférences professionnelles.

## Métier préservé
- 60 questions actives ;
- 10 dimensions x 6 questions ;
- ordre des questions et propositions aléatoire ;
- scoring, calculs, interprétation et restitution inchangés ;
- rapport PDF et JSON final conservés.

## Nouveautés 1.9.5
- validation centralisée des identités, e-mails, téléphones, textes et codes ;
- validation forte des JSON de reprise (UTF-8, 2 Mo max, structure, questions/options/identifiants) ;
- compatibilité explicitement testée avec les JSON 1.9.4 Streamlit Cloud ;
- validation renforcée de la banque XLSX sans modification de son contenu ;
- préparation VPS Clarté360 ;
- URL cible : `https://preferences-professionnelles.clarte360.com` ;
- service proposé : `clarte360-preferences-professionnelles.service` ;
- préparation du contrat Hub I9-H1 (Administrateur/Intervenant -> bénéficiaire d'une action existante) ;
- HMAC et secrets SMTP exclusivement hors Git.

## Déploiement
Aucun déploiement n'est réalisé par ce ZIP. Le cycle attendu reste : développement -> tests -> GitHub -> VPS -> tests VPS -> compilation -> redémarrage -> recette métier.

Voir `docs/` pour l'audit de validation, le contrat Hub et le rapport VPS.


## Nouveautés 1.9.6
- Garde-fou navigateur homogénéisé : F5, fermeture et navigation averties tant que le travail a changé depuis le dernier JSON sauvegardé.
- Le garde-fou se réarme après toute nouvelle réponse ou sélection en cours.
- Les JSON 1.9.4/1.9.5 conformes restent compatibles.


## Nouveautés 1.9.7
- Le JSON proposé dans la barre latérale est reconstruit depuis l'état validé courant à chaque rendu : aucune préparation antérieure ne peut être téléchargée comme photographie obsolète du travail.
- Le garde-fou est lié à l'empreinte exacte de l'état réellement sérialisé ; une sélection radio non validée reste donc signalée comme non sauvegardée.
- Le bouton de sortie place l'application sur un écran de sortie dédié jusqu'au téléchargement du JSON.
- Restitution enrichie à l'écran et dans le PDF : détail des 10 dimensions, question explorée, repères des pôles bas/haut issus du référentiel XLSX et position sur le continuum.
- Les 60 questions, le scoring, les formules de calcul et les deux graphiques sont inchangés.

## Identité de déploiement VPS
- `tool_id` : `preferences-professionnelles`
- URL : `https://preferences-professionnelles.clarte360.com`
- port : `8507`
- service : `clarte360-preferences-professionnelles.service`
- dossier stable : `/opt/clarte360/clarte360-outils/clarte360-preferences-professionnelles/`

Le registre central du Framework VPS prévaut sur toute ancienne valeur de port présente dans une archive ou une documentation historique.


## Nouveautés 1.9.8
- Ergonomie du questionnaire allégée : les blocs d'objectif, de confidentialité et de présentation des 10 dimensions ne sont plus répétés à chaque question.
- Logo Clarté360 et repère de navigation ajoutés dans la barre latérale pendant la passation.
- Écran question retravaillé : question mise en évidence, propositions plus lisibles et progression compacte.
- Bouton **Question précédente** ajouté sans suppression des réponses déjà validées.
- Lorsqu'une question déjà répondue est revisitée, la réponse validée est automatiquement présélectionnée et peut être conservée ou modifiée.
- Le garde-fou distingue désormais une réponse simplement préaffichée d'une modification non encore validée.
- Questionnaire, ordre aléatoire, cotations, scoring, rapport et logique JSON métier inchangés.
