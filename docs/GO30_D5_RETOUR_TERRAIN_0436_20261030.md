# GO30 D5 — retour terrain sur le parcours documentaire 0.4.36

Date : 30 octobre 2026  
Contexte : essai intervenant après remise à zéro du dossier, version D5 0.4.36.

## Retour observé

Après la RAZ, le dossier GDA contient les sept pièces attendues. Les propositions de rapprochement affichées dans D5 tombent juste : le CV est proposé pour CV et l’APS pour APS; l’intervenant constate que les associations proposées correspondent aux fichiers.

L’aperçu à l’écran est utile quand le nom ne suffit pas, mais reste facultatif : un nom de fichier explicite peut suffire à l’intervenant pour vérifier la pièce. Le téléchargement doit rester facultatif.

## Comment fonctionne actuellement la proposition automatique

Dans le code de la 0.4.36, ce n’est pas une lecture IA des PDF :

1. D5 récupère l’inventaire des pièces GDA visibles pour l’action.
2. Pour chaque rubrique documentaire, le code cherche une pièce publiée dont le nom contient un mot-clé attendu : CV (« cv »), APS (« aps »), Boussole (« boussole », « valeur »), Moteurs (« moteur »), Préférences (« preference », « préférence »), PIP (« pip », « riasec »), IPIP (« ipip », « neo »).
3. Il privilégie une correspondance avec le premier mot-clé, puis accepte l’un des autres mots-clés. Il ne repropose pas une pièce déjà affectée à une rubrique pendant cette passe.
4. Une association déjà enregistrée pour cette rubrique est prioritaire sur la suggestion par nom.
5. Le nom ne valide rien à lui seul : l’intervenant confirme le rapprochement. La sélection, les validations et le choix d’utilisation sont enregistrés ensemble avec le bouton global.

Ainsi, le bon résultat observé vient d’une règle déterministe sur les noms et de l’affectation sans doublon. Le contenu du PDF n’est ni lu ni classé automatiquement pour proposer le CV ou l’APS. L’aperçu est chargé uniquement si l’intervenant le demande.

## Clarification du terme « besoin »

Dans ce formulaire, « besoin » désigne la rubrique documentaire du bilan à laquelle on rattache une pièce (CV, APS, Boussole, etc.). Ce n’est pas un besoin supplémentaire du bénéficiaire ni une question à lui poser. Le libellé « pour ce besoin » prête à confusion et doit disparaître de l’interface.

## Changements demandés pour la prochaine version

- Faire de **Documents** l’unique écran de sélection, rapprochement, vérification et décision d’utilisation des sept pièces.
- Supprimer le contrôle en doublon **« Ne pas sélectionner de pièce pour ce besoin »**. Le parcours attendu ici est celui des sept pièces requises; s’il manque une pièce, signaler clairement la rubrique manquante au lieu de demander une décision redondante.
- Garder seulement les deux décisions par pièce :
  1. confirmer que la pièce sélectionnée correspond à la rubrique affichée;
  2. indiquer clairement si elle doit être prise en compte dans l’étude et la préparation du questionnaire. Préférer une formulation positive et un choix Oui/Non à une case négative ambiguë.
- Garder l’aperçu intégré facultatif et le téléchargement facultatif. Afficher le nom comme repère, sans obliger à ouvrir ou télécharger une pièce lorsque le nom est suffisamment clair.
- À la validation globale, afficher une confirmation explicite « 7 pièces enregistrées » et poursuivre directement vers le brouillon du questionnaire. Ne pas reposer la sélection des sept sources ni ajouter une confirmation intermédiaire pour accéder au questionnaire.
- Retirer du menu de gauche **« Vérifier les sources et le CV »** et sa page si elle répète la vérification documentaire. Toute fonction utile qui lui est propre (par exemple l’analyse ultérieure du CV) doit intervenir à son étape de parcours, sans redemander le rapprochement déjà validé.
- Conserver à la fin la proposition facultative d’ajouter une pièce libre pour analyse IA, avec choix Oui/Non et consentement explicite. L’analyse reste une aide à examiner, jamais une décision ou une insertion automatique.
- Vérifier qu’un message de succès visible confirme bien l’enregistrement des décisions; aucun clic ne doit sembler sans effet.

## Critères de recette

- Les sept rubriques s’affichent dans l’ordre : CV, APS + objectif du bilan, Boussole des valeurs, Moteurs professionnels, Préférences professionnelles, PIP RIASEC, IPIP.
- Avec sept pièces publiées correctement nommées, les sept propositions initiales sont distinctes et cohérentes; un nom ambigu peut être contrôlé dans l’aperçu.
- Une pièce n’est pas formellement validée avant la confirmation de l’intervenant.
- Les deux décisions demandées sont accessibles sans commande « ne pas sélectionner » répétée.
- Un seul enregistrement global donne un retour de succès et ouvre directement le brouillon du questionnaire, sans nouvelle saisie des associations.
- Le menu ne présente pas une seconde page de rapprochement concurrente.
- Le choix d’analyse d’une pièce libre reste facultatif et soumis au consentement.

Ce PR consigne le retour terrain et le périmètre de la prochaine itération. Il ne modifie pas la version 0.4.36 actuellement installée.
