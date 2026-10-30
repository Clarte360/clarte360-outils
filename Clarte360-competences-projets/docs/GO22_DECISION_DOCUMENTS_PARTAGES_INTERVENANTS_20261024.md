# GO22 — Décision de reprise : documents dans l'espace partagé

Date : 24 octobre 2026  
Statut : décision fonctionnelle nouvelle de Dominique, à appliquer aux GO22, GO27 et suivants.  
La liste officielle des GO n'est pas modifiée.

## Décision

Compétences & Projets est lancé depuis Gestion des Actions / Hub et travaille sur les documents communs rattachés au même dossier bénéficiaire et à la même action. Cela concerne les sources amont (APS, Boussole, Moteurs, Préférences, IPIP, PIP), le CV et les documents produits pendant le bilan.

Depuis l'écran C&P concerné, l'application recherche d'abord le document dans l'espace commun, avec une liste filtrée au dossier et au rôle. L'utilisateur choisit la bonne référence; C&P conserve sa référence stable, sa version, son type, sa provenance, son MIME, sa taille et son empreinte. Le binaire reste dans le stockage documentaire maître. C&P n'en crée pas de copie persistante.

Si le document n'existe pas déjà dans cet espace, chacune des trois parties prenantes — bénéficiaire, intervenant ou administrateur — peut déposer un document depuis l'écran de C&P, selon ses droits sur le dossier. Le dépôt peut être de tout type; il est d'abord enregistré comme document non associé, sans reconnaissance automatique du contenu ni classement automatique. L'écran envoie le fichier à GDA dans l'espace documentaire commun, rattaché au bon dossier. GDA effectue le stockage, le versionnement, la déduplication SHA-256 et les contrôles d'accès, puis renvoie la référence; C&P n'en conserve que le lien et les métadonnées utiles. L'utilisateur ne doit pas basculer vers une application ou un espace C&P séparé pour déposer le fichier.

## Lecture par C&P

- C&P utilise les opérations documentaires génériques `SOURCE_LIST` et `SOURCE_GET` prévues par GO-14, après vérification des droits, de l'action, du bénéficiaire, de la prescription et de l'audience.
- Le dépôt depuis l'écran C&P vers l'espace commun passe par une opération GDA authentifiée `SOURCE_PUT` (ou l'opération générique équivalente de l'espace documentaire), contrôlée côté serveur et rattachée au dossier courant. Elle renvoie la référence/version GDA; elle n'écrit pas de binaire dans le stockage C&P.
- Aucun OCR, extraction automatique, interprétation IA, reconnaissance du type ou rattachement automatique à une rubrique métier n'est réalisé à cette étape.
- Les nouveaux fichiers non associés apparaissent dans une file « Documents à relier ». L'intervenant les examine et choisit explicitement le besoin métier C&P correspondant (CV source, APS, Boussole, Moteurs, Préférences, IPIP, PIP, ou autre document de parcours). Ce lien humain est versionné, attribué à l'intervenant et modifiable avec historique; le document d'origine reste inchangé.
- Un document déposé par le bénéficiaire ou l'administrateur ne devient pas une source d'analyse avant que l'intervenant l'ait relié au besoin concerné et confirmé qu'il peut être utilisé dans le bilan.
- Le contenu est récupéré à la demande pour l'affichage ou l'analyse. Les octets et les textes extraits ne sont pas enregistrés comme une seconde archive C&P; les résultats structurés du travail de bilan restent, eux, des données métier C&P versionnées.
- L'original reste intact. Une nouvelle version est une nouvelle référence/version GDA; les analyses indiquent exactement la source et la version utilisées.
- Les autorisations d'ajout dans GDA ne donnent pas automatiquement un droit de lecture des contenus. L'administrateur peut verser un document sans accéder aux résultats confidentiels du bilan.
- Le bénéficiaire ne peut ajouter un document qu'à son propre dossier; un intervenant doit être actif/affecté à l'action; l'administrateur agit via son habilitation de dépôt. Les règles d'accès sont réévaluées par GDA à chaque opération.
- Aucun document d'un autre bénéficiaire, d'une autre action, d'une autre prescription, non publié ou de type exclu ne doit apparaître. `ONET_REPORT` et le rapport PIP PUBLIC restent exclus.

## Correction de la décision GO-14 antérieure

La section GO-14 « CV local C&P » du 11 octobre est supersédée par cette décision du 24 octobre : le CV source est choisi ou ajouté dans l'espace documentaire commun. La feuille `LISTE DES GO NE PAS TOUCHER.docx` reste inchangée. Le contrat maître GO-14 reste conservé comme historique; ses opérations `SOURCE_LIST`/`SOURCE_GET` et ses règles de contrôle s'appliquent, complétées par le droit générique d'ajout partagé ci-dessus.

Le CV enrichi n'écrase pas le CV source. C'est un livrable métier distinct, versionné par C&P et publié dans l'espace commun avec son lien de provenance. Son ajout/retour respecte le contrat documentaire générique GDA.

## Conditions de recette

1. Un accompagnateur affecté voit les documents autorisés du dossier et peut sélectionner Boussole ou CV sans téléverser une deuxième fois le fichier.
2. Depuis C&P, chacune des trois parties prenantes peut déposer un document autorisé dans l'espace commun, selon ses droits GDA.
3. Le document déposé reste non associé et n'est pas interprété jusqu'à la liaison manuelle explicite par l'intervenant.
4. La lecture d'un document sélectionné passe par GDA; aucune copie binaire persistante n'apparaît dans le stockage C&P.
5. L'empreinte, la référence/version, le déposant, la date et la liaison humaine sont conservés dans le dossier métier C&P.
6. Les refus d'accès, versions nouvelles, documents absents et indisponibilités GDA sont lisibles et ne sont jamais interprétés comme un résultat négatif.
7. Les règles d'administration ne donnent pas à l'administrateur un accès métier individuel implicite.

