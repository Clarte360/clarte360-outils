# CLARTÉ360 — PIP RIASEC / O*NET — RAPPORT JALON C

Date : 18/09/2026
Base : Jalon B récupéré depuis OneDrive
Périmètre : séparation PUBLIC / ACCOMPAGNEMENT

## 1. Base de travail

Le développement C a été réalisé exclusivement à partir de `CLARTE360_PIP_RIASEC_ONET_JALON_B_20260918.zip`, récupéré depuis le dossier OneDrive officiel du projet.

Aucun retour à la V1.0.10, au Jalon A ou au Jalon A1 n’a été effectué.

## 2. ACCOMPAGNEMENT — affichage lisible

Le contrat de lancement PIP accepte désormais quatre données d’affichage incluses dans le jeton signé :
- prénom bénéficiaire ;
- nom bénéficiaire ;
- numéro d’action lisible ;
- intitulé de l’action.

Elles sont représentées côté PIP par :
- `beneficiary_first_name` ;
- `beneficiary_last_name` ;
- `action_number` ;
- `action_title`.

L’écran d’accueil ACCOMPAGNEMENT n’affiche plus `beneficiary_id` ni `action_id`.

Les identifiants techniques restent utilisés côté serveur pour la persistance et les échanges avec Gestion des Actions.

## 3. Non-régression du connecteur existant

Le Jalon C ne modifie pas Gestion des Actions.

Pendant la transition, un ancien jeton ne comportant pas encore les quatre nouveaux champs d’affichage reste accepté. Dans ce cas, le PIP affiche uniquement :
- `Bénéficiaire Clarté360` ;
- `Action Clarté360`.

Il ne réutilise jamais les IDs techniques comme texte d’affichage.

Cette compatibilité évite de casser l’intégration actuelle avant le chantier dédié côté Gestion des Actions.

## 4. Suppression de la question accompagnateur

La question :

`Souhaitez-vous approfondir certains éléments avec votre accompagnateur ?`

est entièrement supprimée du questionnaire de ressenti.

Le référentiel de ressenti passe de `PIP-FEELING-1.0` à `PIP-FEELING-1.1`.

Il comprend désormais six questions méthodologiques neutres : reconnaissance globale, dominantes, nuances, dimension ressentie trop élevée, dimension ressentie trop faible, utilité.

Le mode `PUBLIC` ou `ACCOMPAGNEMENT` est tracé dans l’enregistrement de ressenti sans modifier le scoring.

## 5. Séparation PUBLIC / ACCOMPAGNEMENT

- PUBLIC conserve son identification, vérification e-mail, intérêts facultatifs, marketing facultatif et étude consentie.
- ACCOMPAGNEMENT ne passe jamais par ces mécanismes PUBLIC.
- ACCOMPAGNEMENT conserve autosave serveur, reprise par prescription et événements de suivi existants.
- Aucune donnée ACCOMPAGNEMENT n’est ajoutée au dataset d’étude PUBLIC.
- Aucun texte utilisateur PUBLIC/ACCOMPAGNEMENT ne contient désormais la question interdite relative à « votre accompagnateur ».

## 6. Non-régression méthodologique

Inchangés :
- 72 items PIP ;
- 12 items par dimension ;
- 30 facettes ;
- tableur maître V0.6 ACTIF ;
- banque `PIP-BANK-0.5` ;
- scoring RIASEC/Holland ;
- O*NET ;
- RGPD, timeout et reprise du Jalon B.

Le contrôle `tableur maître → JSON runtime` reste valide.

## 7. Dépendance identifiée

Pour obtenir l’affichage complet exigé en production, Gestion des Actions devra, dans son chantier séparé, inclure les quatre champs d’affichage dans le jeton signé.

Le PIP est déjà prêt à les consommer. Aucun changement de logique PIP ne sera nécessaire lorsque le producteur du jeton les transmettra.

## 8. Hors périmètre

Ce jalon ne traite pas encore :
- tri final O*NET et restitution comparative enrichie (Jalon D) ;
- rapport PDF professionnel (Jalon E) ;
- ROME/RIASEC (Jalon F) ;
- nouveaux événements PUBLIC CRM / rappel / PDF final (Jalon G).
