# Point de reprise — PIP H3.3-D-RC3 — 18 octobre 2026

## Décision et livraison
GO utilisateur : terminer le lot PIP P1–P5 limité, documenter les réserves GDA ; livrer le ZIP candidat dans la racine 14 à côté du ZIP actuel.
Archive source officielle : `CLARTE360_PIP_RIASEC_ONET_H33D_PRODUCTION_75af19d_20261017.zip` (archive globale du dépôt).
Candidate : `CLARTE360_PIP_RIASEC_ONET_H33D_RC3_CANDIDATE_CLOTURE_20261018.zip` (application PIP complète uniquement).
Version applicative : H3.3-D-RC3. Aucune modification de questionnaire, scoring, modèle PDF ou parcours initial masqué.

## État des systèmes
GitHub : aucune écriture pendant ce lot ; Dominique doit intégrer le ZIP puis commit/push.
VPS : aucune intervention pendant ce lot ; dernier déploiement connu dans le fil = 75af19d, pas de nouvelle lecture SSH revendiquée.
GDA : aucun code livré/modifié. Compatibilité vérifiée localement avec le récepteur 75af19d.
Données : aucune suppression/réinjection, aucun changement BRIETO ou Fabienne.

## Travail fait
Publication des PDF par document/empreinte, PDF accompagnés immuables, garde de reprise en échec, protection du rattachement et des réponses plus avancées, conservation des permissions, ressenti sauvegardé avant finalisation, destinataire PUBLIC validé côté serveur, relance e-mail explicite bornée, erreurs expurgées, persistance pseudonymisée indépendante.
Nouveaux suivis locaux PIP : `data/delivery/accompanied/`, `data/public/report_delivery/`, verrous `.locks/`. Aucun changement du schéma GDA, des noms PDF techniques, des clés SMTP/ONET/HMAC.

## Tests
270 tests PIP réussis localement ; 4 cas de compatibilité GDA réussis sur copie et SQLite jetables ; interface simulée et transport SMTP/API simulés ; PDF réels produits ; contrôle navigateur/VPS et messagerie réelle restant à faire après déploiement.

## Réserves
R-GDA-01 à R-GDA-05 dans le fichier joint : historique affiché/versions remplacées, un rapport de chaque type par prescription, noms fixes du récepteur, notifications, autre appel IPIP à examiner séparément. Ne pas promettre cinq boutons de rapports visibles grâce à PIP seul.

## Références consultées
Framework Clarté360 V5 ; Addendum V4.2 du 10/10/2026 (secrets centralisés) ; Framework VPS V1.5 ; protocole propriétaire du 09/10/2026 ; audit de clôture du 18/10/2026. Les marqueurs techniques historiques framework_version 4.0 / VPS 1.3 de l'application ne constituent pas une migration des frameworks ; ce lot ne change pas ces contrats.

## Prochaine action exacte
Dominique copie la livraison PIP dans sa branche locale `main`, vérifie le périmètre PIP seul, commit et push. Ensuite seulement : comparer le commit publié, contrôler le registre VPS et préparer la mise à jour PIP dans son dossier/service existant. Ne pas redéployer GDA. Ne pas créer de branche distante ou de dossier de production supplémentaire sans autorisation.
