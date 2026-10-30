# Veille et mise à jour contrôlée du référentiel ROME

## Référence utilisée

La recherche intégrée interroge en premier lieu l’API ROME Métiers pour les intitulés et les appellations. Si l’API est indisponible ou ne renvoie rien, l’application continue avec un snapshot local explicitement daté. La fiche sélectionnée est chargée depuis l’API Fiches métiers lorsque le scope est disponible; la fiche locale reste un secours pour poursuivre le travail hors ligne.

Le classeur `07-rome_riasec_clarte360.xlsx` fournit un repère ROME/RIASEC et ne remplace pas l’export des fiches métier. Le corpus des attendus est reconstruit depuis l’export officiel `RefRomeXml.zip`. Au 24/10/2026, il s’agit de ROME 4.0 version 61 (26M06), publié le 15/06/2026, avec 1 911 codes uniques.

Consulter les publications officielles France Travail et le jeu de données ROME sur data.gouv.fr :

- API ROME 4.0 : https://www.data.gouv.fr/dataservices/api-repertoire-operationnel-des-metiers-et-des-emplois-rome-4-0
- Jeu de données ROME : https://www.data.gouv.fr/datasets/repertoire-operationnel-des-metiers-et-des-emplois-rome

Ne pas déduire la nouvelle version du seul nombre de fiches annoncé sur une page web. Conserver l’archive complète ainsi que la version officielle et sa date de publication.

## Comparer un nouvel export

À partir de la racine du dépôt, exécuter avec l’archive officielle complète :

```bash
python tools/compare_rome_catalog_update.py /chemin/vers/RefRomeXml.zip \
  --version "ROME 4.0 version 62 (MMYY)" \
  --publication-date AAAA-MM-JJ \
  --candidate-output tmp/rome_catalog_candidate.json
```

La version et la date doivent être reprises de la publication officielle. Le rapport indique le nombre d’entrées, les codes ajoutés/retirés et les fiches dont le contenu a changé. La commande vérifie aussi les doublons et la présence, pour chaque fiche, d’un intitulé, d’une définition, des informations d’accès descriptives, d’un bloc de compétences et d’un contexte de travail exploitable. Elle écrit le nouveau catalogue dans un fichier candidat séparé et ne remplace jamais le catalogue embarqué.

## Revue et intégration

1. Examiner les ajouts/retraits et les fiches modifiées; vérifier la source et la date de publication.
2. Comparer manuellement un échantillon couvrant les attendus de savoirs, savoir-faire, contextes et accès descriptif, dont les métiers retenus par les dossiers d’essai.
3. Exécuter les tests ROME, puis la suite complète et la compilation.
4. Après validation des données, remplacer `clarte360_cp/data/rome_catalog.json` par le fichier candidat dans la branche de travail. Le code lit la version, la date et le nombre de fiches depuis le catalogue; il n’est pas nécessaire de modifier l’interface pour les faire correspondre.
5. Traiter les changements de contenu en revue : toute actualisation de fiche change l’empreinte du snapshot et rend les rapprochements dépendants à revoir.
6. Archiver l’export source, son nom, sa date, sa version et le rapport de comparaison avec la recette de cette mise à jour.

À défaut de nouvel export disponible, conserver le snapshot actuel, daté clairement à l’écran, et utiliser les API Métiers et Fiches métiers quand leurs scopes sont accessibles. La recherche API permet d’atteindre le catalogue courant; le snapshot local maintient la continuité si les API sont hors service. Aucun travail de recherche ROME externe n’est demandé au bénéficiaire.
