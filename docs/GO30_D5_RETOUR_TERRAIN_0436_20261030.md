# Mini-cahier des charges — prochaine version du parcours D5 Documents

Date : 30 octobre 2026  
Base terrain : essai intervenant après RAZ sur D5 0.4.36 et captures/PDF fournis.

## 1. Objectif

Permettre à l’intervenant de sélectionner, vérifier et qualifier une seule fois les sept documents obligatoires du dossier, puis d’ouvrir directement le brouillon du questionnaire. La consultation d’une pièce doit rester facultative et ne doit pas déformer ni répéter la page.

## 2. Parcours des sept pièces

Écran unique **Documents**, dans cet ordre :

1. CV
2. APS + objectif du bilan
3. Boussole des valeurs
4. Moteurs professionnels
5. Préférences professionnelles
6. PIP RIASEC — accompagnement
7. IPIP — profil de fonctionnement professionnel

Pour chaque rubrique :

- proposer automatiquement le document GDA dont le nom correspond, sans empêcher l’intervenant de remplacer cette proposition;
- exiger une pièce : supprimer entièrement **« Ne pas sélectionner de pièce pour ce besoin »**. Les sept pièces sont obligatoires. Si une pièce manque, nommer la rubrique à compléter dans GDA et bloquer l’enregistrement. Ne pas griser le pavé et ne pas permettre une rubrique vide;
- conserver seulement deux décisions explicites :
  1. confirmer que le document choisi correspond à la rubrique;
  2. répondre **Oui/Non** à : « Prendre ce document en compte dans l’étude et la préparation du questionnaire ? »;
- garder l’aperçu et le téléchargement facultatifs.

Le terme « besoin » signifie ici la rubrique documentaire du bilan. Éviter ce terme seul dans les libellés, car il est compris comme un besoin du bénéficiaire.

## 3. Aperçu d’une pièce

Les captures fournies montrent que l’aperçu actuel est ajouté directement dans le long écran Documents, au milieu des sept pavés. Cela allonge et perturbe la page; l’utilisateur signale que la visualisation fait doublon avec le questionnaire et ramène l’affichage en haut.

Comportement attendu :

- Le bouton **Voir l’aperçu** ouvre une fenêtre modale centrée, par-dessus la page.
- La fenêtre affiche uniquement la pièce sélectionnée dans le pavé concerné, dans une zone de taille limitée à l’écran. Le PDF est consulté page par page (commandes précédente/suivante et indication « page x sur y »), sans afficher toutes ses pages à la suite dans la page principale.
- La zone de défilement du document reste dans la fenêtre; elle ne fait pas défiler l’écran de sélection derrière.
- La fenêtre comporte une fermeture visible **×** et un bouton **Fermer**. La fermeture ramène à la même rubrique et à la même position de défilement.
- Ouvrir puis fermer l’aperçu ne duplique pas le questionnaire, ne répète pas les pavés, ne modifie aucune sélection/coche et ne valide/enregistre rien.
- Le téléchargement reste facultatif, accessible depuis la fenêtre d’aperçu.
- Une seule fenêtre de prévisualisation est ouverte à la fois. Pour un format non prévisualisable, afficher un message dans cette fenêtre et garder le téléchargement facultatif.

## 4. Navigation et enregistrement

- **Documents** est le seul écran de sélection et de validation des sept pièces.
- Retirer du menu de gauche **« Vérifier les sources et le CV »** et sa page de rapprochement redondante. Les captures montrent que cette page affiche les sept rubriques « Pas encore relié » et renvoie vers GDA alors que le travail documentaire est regroupé dans Documents. Toute analyse ultérieure du CV qui demeure nécessaire doit se trouver à son étape de parcours, sans redemander le lien ni la validation.
- Enregistrer ensemble les sept associations, les confirmations de correspondance et les réponses Oui/Non à l’utilisation.
- Afficher un succès explicite, par exemple **« Les 7 documents sont enregistrés »**, puis ouvrir directement le brouillon du questionnaire. Ne pas reposer la sélection documentaire et ne pas ajouter une question intermédiaire pour accéder au questionnaire.
- Garder à la fin l’ajout facultatif d’un autre document pour une analyse IA, avec choix Oui/Non et consentement explicite. L’analyse produit des pistes à examiner; elle ne décide pas et n’insère rien automatiquement dans le questionnaire.

## 5. Critères de recette

- Les sept rubriques et leur ordre sont ceux définis ci-dessus.
- Avec sept pièces publiées dans GDA, les sept propositions sont distinctes et cohérentes; chacune peut être remplacée.
- Une rubrique sans document bloque l’enregistrement avec un message précis; aucun contrôle ne permet de l’ignorer.
- Chaque pavé contient seulement la confirmation de correspondance, puis le choix Oui/Non de prise en compte.
- L’aperçu apparaît dans une fenêtre modale fermable, page par page; fermer la fenêtre restitue le même écran, les mêmes coches et la même position.
- L’ouverture de l’aperçu ne répète ni le questionnaire ni les pavés et ne provoque pas de retour en haut.
- Un clic global enregistre les sept décisions, donne un message de succès et ouvre directement le brouillon, sans nouvelle sélection des sources.
- Le menu ne propose plus une seconde page de rapprochement.
- L’analyse d’un document complémentaire reste facultative, consentie et sans insertion automatique.

## 6. Explication du rapprochement actuel en 0.4.36

La suggestion actuelle est déterministe, pas une lecture IA des PDF : D5 récupère les pièces GDA publiées, puis recherche dans leur nom des mots-clés propres à chaque rubrique (CV, APS, Boussole/valeur, moteur, préférence, PIP/RIasec, IPIP/NEO). Il privilégie le premier mot-clé, ne repropose pas une pièce déjà affectée dans cette passe et donne priorité à un lien déjà enregistré. L’intervenant confirme ensuite les choix groupés. Le contenu du PDF n’est pas lu pour proposer les associations.

Ce cahier des charges consigne les retours pour la prochaine version; il ne modifie pas la 0.4.36 actuellement installée.
