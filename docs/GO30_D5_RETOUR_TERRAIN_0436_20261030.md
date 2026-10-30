# GO30 D5 — retour terrain et décisions UX pour la suite de la 0.4.36

Date : 30 octobre 2026  
Contexte : essai intervenant après remise à zéro du dossier, version D5 0.4.36.

## Retour observé

Après la RAZ, le dossier GDA contient les sept documents obligatoires attendus. Les propositions de rapprochement tombent juste : le CV est proposé pour le CV et l’APS pour l’APS; l’intervenant constate que les autres associations sont également cohérentes.

L’aperçu intégré est utile si le nom du fichier ne suffit pas, mais il doit rester facultatif. Le téléchargement est facultatif également.

## Comment fonctionne actuellement la proposition automatique

Dans le code de la 0.4.36, le rapprochement initial n’est pas une lecture IA des PDF :

1. D5 récupère l’inventaire des pièces GDA visibles pour l’action.
2. Pour chaque rubrique, le code cherche une pièce publiée dont le nom contient un mot-clé : CV (« cv »), APS (« aps »), Boussole (« boussole », « valeur »), Moteurs (« moteur »), Préférences (« preference », « préférence »), PIP (« pip », « riasec »), IPIP (« ipip », « neo »).
3. Il privilégie le premier mot-clé, puis accepte un autre mot-clé de la rubrique. Une pièce déjà proposée à une rubrique n’est pas proposée une seconde fois dans cette passe.
4. Une association précédemment enregistrée pour cette rubrique est prioritaire sur la suggestion par nom.
5. La correspondance par nom reste une suggestion : elle n’est enregistrée qu’après la confirmation globale de l’intervenant.

Le bon résultat observé vient donc de règles déterministes sur les noms de fichiers et d’une affectation sans doublon. Le contenu des PDF n’est pas analysé pour suggérer les rubriques.

## Ce que montrent les captures

- Le menu de gauche contient **« Vérifier les sources et le CV »**. Cette page affiche les sept rubriques avec leur état « Pas encore relié » et demande de choisir les documents dans GDA. Elle fait donc refaire ou vérifier ailleurs le travail qui est maintenant regroupé dans **Documents**.
- Dans l’écran **Documents**, chaque pavé de rubrique affiche déjà une pièce suggérée, un aperçu facultatif, puis la confirmation de correspondance et la décision d’utilisation.
- Le même pavé contient aussi **« Ne pas sélectionner de pièce pour ce besoin »**. Cette option permet de laisser une rubrique vide et entre en contradiction avec la règle métier confirmée par l’intervenant : les sept pièces sont obligatoires.
- Une rubrique laissée vide ne doit pas être présentée comme un choix normal, ni griser le reste du pavé. L’interface doit exiger le choix d’un document pour chacune des sept rubriques.

## Sens des deux options négatives actuelles

Elles ne veulent pas dire la même chose, mais leur présence simultanée prête à confusion :

- **« Ne pas sélectionner de pièce pour ce besoin »** signifie ne rattacher aucun document à cette rubrique. Exemple : ne choisir aucun fichier dans la case APS.
- **« Ne pas prendre cette pièce en compte dans l’étude ni dans le questionnaire »** signifie choisir et rattacher un document, tout en l’excluant ensuite de l’étude.

Dans le parcours demandé, le premier choix n’a pas lieu d’exister : les sept documents sont obligatoires. Il faut le supprimer complètement. Il ne faut ni le remplacer par un bouton équivalent, ni griser le pavé lorsqu’il est activé, ni autoriser la validation d’un dossier avec une rubrique vide. Si une pièce requise manque, signaler clairement la rubrique à compléter dans GDA et bloquer l’enregistrement global.

## Changements demandés pour la prochaine version

- Faire de **Documents** l’unique écran de sélection, rapprochement, vérification et décision d’utilisation des sept pièces.
- Retirer du menu de gauche **« Vérifier les sources et le CV »** ainsi que sa page de rapprochement redondante, comme le montrent les captures. Toute fonction réellement distincte, par exemple une analyse ultérieure du CV, doit rester à son étape de parcours et ne pas créer une seconde validation des documents.
- Dans chacun des sept pavés, garder seulement :
  1. une confirmation que la pièce sélectionnée correspond à la rubrique affichée;
  2. un choix explicite Oui/Non pour indiquer si la pièce doit être prise en compte dans l’étude et la préparation du questionnaire. Formuler ce choix positivement, sans case négative à double lecture.
- Supprimer définitivement **« Ne pas sélectionner de pièce pour ce besoin »**. Exiger un document pour chacune des sept rubriques; en cas d’absence, nommer la rubrique manquante et indiquer qu’il faut compléter le dossier GDA. Ne pas désactiver ou griser le contenu du pavé.
- Garder l’aperçu intégré facultatif. Le nom de fichier peut suffire à l’intervenant; aucun téléchargement ne doit être requis.
- Enregistrer les sept sélections et décisions en un seul clic. Montrer un message de succès explicite, puis ouvrir directement le brouillon du questionnaire, sans nouvelle sélection des sources ni confirmation intermédiaire.
- Conserver à la fin l’ajout facultatif d’une pièce libre pour analyse IA, seulement après choix Oui et consentement explicite. L’analyse est une aide à examiner, jamais une décision automatique ni une insertion automatique dans le questionnaire.

## Critères de recette

- Les sept rubriques apparaissent dans l’ordre : CV, APS + objectif du bilan, Boussole des valeurs, Moteurs professionnels, Préférences professionnelles, PIP RIASEC, IPIP.
- Les sept documents requis sont pré-suggérés de manière distincte et cohérente lorsque leurs noms sont explicites; l’intervenant peut remplacer une suggestion.
- Aucun chemin d’interface ne permet de laisser volontairement une rubrique vide; une pièce manquante bloque la validation et est signalée clairement.
- Chaque pièce offre exactement la confirmation de correspondance et le choix Oui/Non de prise en compte dans l’étude.
- L’aperçu et le téléchargement restent facultatifs.
- Un seul enregistrement global confirme le succès et ouvre le brouillon du questionnaire, sans saisie répétée des associations.
- Le menu de gauche n’expose plus une seconde page de rapprochement concurrente.
- L’analyse d’une pièce libre reste facultative et soumise au consentement.

Ce PR consigne le retour terrain et le périmètre de la prochaine version. Il ne modifie pas la version 0.4.36 actuellement installée.
