# GO23-5 — recherche et fiche ROME locale

**Candidate :** `0.4.11-go22-go28-work`, schéma 12  
**Statut :** contrôles locaux réussis ; GO22 et GO23 restent ouverts et non validés. GO21 RC2 reste le dernier jalon validé.

## Ce qui est intégré

- Le programme embarque un index compact dérivé du corpus XML fourni `RefRomeXml.zip` : ROME 4.0 version 61 (26M06), publié le 15 juin 2026, soit 1 911 fiches métier uniques.
- L’accompagnateur recherche un métier par code ROME, intitulé ou appellation, puis propose une fiche datée au bénéficiaire. Le métier reste en proposition jusqu’à sa confirmation explicite en séance.
- Le snapshot garde la source, la version, la date d’effet et son empreinte. L’atelier reçoit les attendus ROME (savoirs, savoir-faire et savoir-être) pour le rapprochement accompagné.
- L’API France Travail reste accessible dans le panneau d’actualisation. Une panne ou l’absence de scope ne bloque plus l’usage du corpus local.
- L’interface distingue la description de l’accès/formation donnée par une fiche de l’obligation légale. Le texte ROME ne suffit pas à déclarer un diplôme obligatoire ; cette obligation exige toujours une source officielle distincte.

## Vérifications

- 1 911 codes uniques présents dans l’index local.
- Recherche « comptable » incluant M1203 — Comptable.
- Import local M1203 dans un dossier de test sans configuration ni appel API.
- Test AppTest de l’accompagnateur : recherche par code, proposition de la fiche, sans API.
- Source/date/version et texte d’accès descriptif conservés dans le snapshot.
- Attendues M1203 présentes dans l’atelier de rapprochement, puis confirmation explicite du métier.
- Suite du projet : **295 tests réussis à la clôture de GO23-5**, compilation Python réussie.

## Limite actuelle

Le référentiel intégré est un instantané du 15 juin 2026. Il permet une recherche et une confrontation hors ligne, mais ne constitue qu’un secours daté. Au contrôle du 24/10/2026, la page dataset France Travail mise à jour le 20/10 affichait 1 923 fiches, alors que les métadonnées API data.gouv affichaient encore 1 911. La version exacte du dernier export doit être récupérée et réconciliée avant GO30. Si l’API France Travail est autorisée et joignable, elle peut actualiser la fiche et enregistrer sa propre provenance. Aucun appel API réel n’a été effectué ici.

## Veille et comparaison avant remplacement

Le corpus est stocké sous le nom générique `clarte360_cp/data/rome_catalog.json`; l’écran lit sa version, sa date et son nombre de fiches depuis les métadonnées. `tools/build_rome_catalog.py` reconstruit le JSON depuis l’export XML, et `tools/compare_rome_catalog_update.py` compare un nouvel export au corpus courant sans l’écraser. Le rapport distingue les codes ajoutés, retirés et les fiches modifiées; le constructeur bloque sur les doublons et fiches incomplètes. La procédure opératoire est décrite dans `docs/VEILLE_ET_MISE_A_JOUR_REFERENTIEL_ROME.md`.

Le contrôle de reproductibilité du 24/10 a reconstruit puis comparé le corpus fourni : 1 911 codes de chaque côté, sans ajout, retrait ni contenu modifié. Ce contrôle confirme la fidélité de l’index à cet export v61; il ne résout pas l’écart avec les chiffres plus récents du jeu de données public.
