# GO22 RC3J — retour du bénéficiaire sur le parcours partagé

Date : 24/10/2026  
Candidate de travail : `0.4.4-go-work-rc4`, schéma 8  
État jalon : GO22 reste ouvert. Cette tranche ne vaut ni validation GO22 ni recette métier.

## Fonction réalisée

- Après validation et partage de la phase 0, le bénéficiaire peut confirmer le parcours ou demander une correction.
- Une correction exige un commentaire (4 à 1 000 caractères), est enregistrée avec la version concernée, et apparaît dans l'espace de travail de l'accompagnateur.
- La phase 0 est rouverte et redevient l'étape courante. Le parcours précédemment partagé est masqué au bénéficiaire jusqu'à une nouvelle relecture et validation par l'accompagnateur.
- Les cartes passent à « à confirmer ». L'accompagnateur corrige/revoit le parcours en séance puis peut revalider la phase ; la demande ouverte est alors résolue.
- Une confirmation ou une correction ne peut être enregistrée qu'une fois par version partagée. Les réponses périmées sont refusées.
- Le bénéficiaire voit un formulaire simple et les explications associées. L'accompagnateur voit la décision, le commentaire et la consigne de reprise.
- L'audit conserve la décision et la longueur du commentaire, pas son texte. Le commentaire est conservé comme motif du signalement métier.

## Limites connues et suite

- Cette tranche ne branche pas l'accès aux fichiers GDA. Aucun document n'est copié, lu, classé ou relié automatiquement.
- La génération/structuration IA du CV et les clarifications par fait ne sont pas réalisées par cette tranche. Le travail actuel porte sur les cartes de parcours déjà créées ou enrichies par l'accompagnateur.
- Les vrais appels API, la recette navigateur/VPS et la recette avec accompagnateur et bénéficiaire d'essai restent à effectuer aux jalons prévus.
- Ne pas modifier le statut officiel : GO21 RC2 reste la dernière version validée ; GO22 n'est pas déclaré validé.

## Vérifications

- Suite complète : 256 tests réussis, incluant confirmation, correction, blocage de réponse en double/périmée, visibilité du commentaire côté accompagnateur et rendu du formulaire bénéficiaire avec Streamlit AppTest.
- Aucun commit, push, déploiement VPS ou ZIP de recette n'a été effectué.
