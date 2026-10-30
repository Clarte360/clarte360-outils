# GO23-1 — investigations reliées aux métiers étudiés

Candidate : `0.4.5-go23-1-work`, schéma 9  
Statut officiel : GO22, GO23 et GO24 restent ouverts. GO21 RC2 reste le dernier jalon validé.

## Changements

- Une mission d’investigation peut être reliée par clé au métier ROME actif concerné. Le lien s’affiche dans les interfaces accompagnateur et bénéficiaire et reste stable si la formulation de la mission change.
- La validation de phase 5 exige au moins un retour d’investigation transmis puis débriefé pour chaque métier ROME actif. Les missions encore ouvertes continuent de bloquer la phase.
- Une mission générale sans métier associé reste possible pour les dossiers sans métier ROME actif.
- Migration additive vers le schéma 9 : le lien est nullable et les missions historiques sont conservées sans association déduite de leur texte. Il n’y a ni suppression, ni réécriture de l’historique.
- Création d’une nouvelle investigation : le métier associé doit être actif et appartenir au même dossier.

## Contrôles

- Test AppTest du parcours complet : choix du métier, publication de la mission, réponse du bénéficiaire et retour visible pour le débrief.
- Test de migration depuis un schéma 8 : mission historique conservée sans altération, nouvelle colonne disponible et migration 9 enregistrée.
- Test de progression : la phase 5 reste bloquée jusqu’à la clôture d’une investigation pour chaque métier actif.
- Suite complète après ce jalon : 258 tests réussis; compilation Python réussie.

## Limites

- Les missions ne sont pas encore créées automatiquement à partir des incertitudes de la phase 3/4. L’accompagnateur formule chaque mission après l’échange de séance.
- Les connexions réelles France Travail, IA et GDA/Hub, ainsi que la recette sur navigateur et VPS restent à faire dans les jalons dédiés.
- Ce travail ne vaut pas recette métier ni validation de GO23.
