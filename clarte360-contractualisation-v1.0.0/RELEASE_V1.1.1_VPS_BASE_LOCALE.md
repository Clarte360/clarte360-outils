# V1.1.1 VPS / Base locale

- Application destinée au VPS Clarté360.
- La base Excel reste sur le poste administrateur.
- Aucun fichier `.xlsm` n'est stocké de façon persistante sur le VPS.
- Upload ponctuel de la base, traitement en mémoire, puis téléchargement de la base mise à jour.
- Injection `APS JSON + saisie administrative` dans `CONV ADM`.
- Financeurs multiples dans `FINANCEMENTS`, clé `NO_CLAR`.
- BC particulier bipartite : contacts de mise en place laissés vides.
- `SPEC_BPF = Autres`.
- Seul `INTRA_HT` reçoit le montant total HT.
- `CALENDRIER`, dates, durée, horaires et accompagnateur proviennent uniquement du masque ou de l'action existante.
- Contrôle d'intégrité du `.xlsm` et conservation du projet VBA.
- Bouton de purge de la session après récupération des fichiers.
