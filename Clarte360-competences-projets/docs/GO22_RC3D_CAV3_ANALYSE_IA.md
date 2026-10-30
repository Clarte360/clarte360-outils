# GO22 RC3D — C-AV3 après R1 / R2 (historique, remplacé par RC3F)

Date : 23 octobre 2026. Statut : candidate technique non validée. GO21 RC2 reste le dernier jalon officiellement validé.

## Règles appliquées

- L'analyse est déclenchée manuellement par l'Accompagnateur après transmission définitive R1. Aucun appel IA n'est effectué pendant le questionnaire Bénéficiaire.
- L'analyse utilise les réponses et les repères de source déjà enregistrés dans le questionnaire Q. Elle n'ouvre aucun CV, PDF, dossier Hub ou pièce employeur et ne les envoie pas au fournisseur IA.
- Le fournisseur doit renvoyer un objet JSON borné : directions de discussion avec éléments associés, points à éclaircir et incertitudes. L'app affiche la sortie comme une proposition interne, jamais comme recommandation, diagnostic ou score.
- Chaque analyse est enregistrée dans une table append-only avec fournisseur, modèle, version de réponses et empreinte exacte du questionnaire, des réponses et des sources.
- Après une modification de R2, l'analyse R1 devient immédiatement obsolète. L'Accompagnateur peut relancer l'analyse sur le brouillon R2; cette sortie reste provisoire jusqu'à confirmation conjointe. Elle ne reste utilisable que si l'empreinte des réponses confirmées correspond exactement.
- Si les réponses changent pendant l'appel réseau, l'analyse est rejetée et n'est pas enregistrée.

## Raccordement fournisseur — état de RC3D

Cette description correspond à l'état initial RC3D. Elle a été remplacée en RC3F par le contrat partagé Clarté360 `[openai] api_key` / `model`, le bouton de lancement Accompagnateur et un adaptateur Responses avec `store=False`. Voir `GO22_RC3F_CAV3_RACCORDEMENT_IA_20261023.md`.

## Vérifications effectuées

- Tests synthétiques du client générique : configuration HTTPS, refus si contexte/format invalide, minimisation de la charge transmise, validation de la structure, absence d'exposition de clé ou de corps de réponse en erreur.
- Tests applicatifs : R1 produit une analyse interne, modification R2 invalide l'analyse R1, analyse sur brouillon R2 marquée provisoire, confirmation R2 conserve l'analyse si son empreinte est identique.
- La recette avec le fournisseur IA réel, le parcours navigateur/VPS temporaire et la validation métier restent à effectuer avant toute validation de GO22/V0.

## Limites fonctionnelles

Cette étape ferme le contrat applicatif de conservation et de péremption des propositions C-AV3. Elle ne raccorde pas l'écran au client IA commun, les sources GDA/Hub ni l'import réel des cinq rapports; seuls les repères déjà inclus dans Q sont transmis au client lorsqu'il sera branché. Il faut terminer ces raccordements et effectuer l'appel réel en recette avant de considérer C-AV3 bouclé ou d'ouvrir la V0. Aucun déploiement, commit, push ou changement de données de production n'a été fait.
