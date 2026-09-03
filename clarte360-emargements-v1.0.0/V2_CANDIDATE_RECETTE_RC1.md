# CLARTÉ360 ÉMARGEMENTS & QUALITÉ — V2 CANDIDATE DE RECETTE RC1

## Statut
Candidate complète destinée à la recette métier du directeur de l'organisme. Ce ZIP est le premier jalon à installer pour test humain, après sauvegarde de la V1/V1.1.1 et de sa base.

## Périmètre consolidé
- émargements individuels/collectifs, QR et liens personnels, codes, absences, reports, rattrapages, contresignature intervenant, clôture et justificatifs ;
- six types de prestations : Formation, Bilan de compétences, VAE, Coaching, Mentorat, Autre ;
- modules activables par action : émargement, qualité à chaud, qualité à froid, retour intervenant ;
- organisme et agences/établissements paramétrables ;
- archivage, recherche et purge ;
- questionnaires qualité versionnés à codes analytiques stables ;
- campagnes, échéances, relances, réponses et PDF ;
- difficultés/réclamations et actions d'amélioration ;
- import Clarté360 et ADCA, y compris action historique qualité sans émargement ;
- tableau de pilotage qualité ;
- worker protégé contre le renvoi automatique d'un SMTP dont la livraison est ambiguë après crash ;
- sauvegarde et utilitaire de restauration.

## Finition RC1
- version candidate figée `2.0.0-rc1` ;
- notices RGPD et emails manuels rendus dépendants de l'organisme configuré ;
- documents d'émargement/certificat utilisent désormais l'identité et les mentions de l'organisme configuré ;
- fuseau du contrôle de complétude aligné sur celui de l'organisme ;
- contrôle supplémentaire de génération PDF sous une identité fictive.

## Limites connues avant recette
- la validation SMTP réelle dépend des secrets OVH du VPS et doit donc être faite pendant la recette ;
- le rendu tactile et les QR doivent être validés sur de vrais smartphones ;
- la migration finale doit être faite avec sauvegarde préalable et idéalement testée sur une copie de la base VPS avant bascule définitive ;
- les valeurs de repli Clarté360 présentes dans le code servent à préserver la compatibilité du déploiement actuel lorsque l'organisme n'est pas encore paramétré ; elles ne doivent pas apparaître pour un organisme correctement configuré.
