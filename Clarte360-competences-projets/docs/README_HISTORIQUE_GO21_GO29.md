Version `0.4.30-go30-dual-candidate` — candidate coordonnée avec Gestion des Actions RC3, dérivée de la dernière recette locale 0.4.29 GO29 non déployée. Statut : candidate de recette, non déployée, GO30 non validé. Voir `docs/GO30_AVIS_INTEGRATION_CP_GDA.md`, `docs/DEPLOIEMENT_GO30_CANDIDAT.md` et `docs/MODE_OPERATOIRE_GO30_CP_GDA.md`.

# CLARTÉ360 — Compétences & Projets professionnels

Version `0.4.29-go29-work` — candidate locale de travail, interfaces **Accompagnateur + Bénéficiaire**, mode **ACCOMPAGNEMENT**, schéma 13. Statut : **non validée, non déployée**. GO21 RC2 reste le dernier jalon officiellement validé. Les quatre familles API France Travail ROME (Métiers, Compétences, Contextes et Fiches métiers) ont des clients indépendants par scope et contrôlent la cohérence du code retourné. En séance, l’accompagnateur et le bénéficiaire retiennent de 1 à 3 métiers dans l’application : la recherche textuelle appelle les opérations officielles d’autocomplétion ROME Métiers `/v1/metiers/metier/requete` et `/v1/metiers/appellation/requete`; les appellations sont reliées au code et à l’intitulé du métier. Si l’API est indisponible ou ne renvoie aucun résultat, l’application utilise le snapshot local v61 daté (1 911 codes, 15/06/2026). Un code exact peut aussi être chargé directement via l’API Fiches métiers, même s’il manque au snapshot. Le snapshot n’est ni la version courante ni une preuve d’exhaustivité : France Travail publie 1 923 fiches en octobre 2026. Le classeur ROME/RIASEC reste un repère d’intérêt, pas le catalogue des attendus. Les mentions d’accès/formation du ROME ne prouvent pas qu’un diplôme est légalement obligatoire. GO24 suit l’ordre A3 : résultats détaillés et conditions, plan d’action, synthèse relue, clôture et suivi à six mois. Les trois livrables finaux existent en PDF et DOCX pour téléchargement ; le retour GDA est encore PDF, le suivi externe et archivage à la clôture restent à faire. La phase 0 conserve des cartes structurées, relie leur provenance, demande leur relecture et enregistre le niveau d’exercice discuté pour chaque expérience. Dans le rapprochement ROME, chaque attendu dispose aussi de son niveau discuté, relié aux preuves du parcours et visible par le bénéficiaire. Le CV relié manuellement peut être analysé après C‑AV3 ; l’IA présente des pistes à confirmer, l’accompagnateur décide lesquelles ajouter au parcours. **330 tests automatisés passent**, compilation Python réussie. Cela ne vaut pas recette navigateur, raccordement live ni validation GO22–GO30. Le kit local de prévisualisation se trouve dans `docs/GO30_RECETTE_HUMAINE.md`; il n’utilise que des données fictives et **ne constitue pas la RC GO30**. Le rapport `docs/GO30_RC_READINESS_REPORT_20261024.md` conclut **NO GO** : le raccordement réel à GDA/Émargement et les essais d’intégration restent à faire avant la recette utilisateur. Les diagnostics live synthétiques IA sont prêts dans docs/GO26_IA_DIAGNOSTIC_LIVE.md; le diagnostic borné des 4 produits est dans tools/test_france_travail_rome_all.py. Aucun appel live n'a encore été exécuté. Le client GDA et le patch CP_V1 sont testés localement; l'installation et les appels réels restent à vérifier. Le catalogue GDA reste inactif tant que le raccordement et les droits ne sont pas testés.

## Investigation accompagnée

La phase 3 affiche une synthèse des propositions IA avant le détail. La phase 4 reprend les seuls points incertains. En phase 5, l’accompagnateur peut confier une question ciblée reliée à un métier ROME ; le bénéficiaire peut enregistrer un brouillon puis transmettre source, date, constat et effet sur le projet. L’accompagnateur débriefe le retour et clôt l’action. Les ressources externes restent disponibles même lorsqu’une API fonctionne.

## Phase 0 — cartes du parcours en séance

L’accompagnateur peut ajouter un apport de parcours, puis compléter une carte existante avec le bénéficiaire : contexte, activités ou contenus étudiés, autonomie, résultats, outils et savoirs. Les études sans diplôme et l’apprentissage personnel sont des sources de savoirs recevables. Le niveau 1/2/3 est contextualisé à une expérience et discuté à partir de faits. Toutes les cartes actives doivent être explicitement relues avec le bénéficiaire avant de valider la phase 0. Les modifications sont historisées et rendent les rapprochements ROME à revoir. Les brouillons restent cachés au bénéficiaire jusqu’à validation de la phase 0 ; une modification après validation rouvre la phase et masque de nouveau les cartes jusqu’à revalidation. Le document d’origine reste dans l’espace partagé. Le connecteur GDA et le lien manuel sont implémentés mais pas encore installés/testés contre le vrai GDA ; aucune copie binaire durable n’est créée dans C&P.

## GO23 — comparaison et décision, RC1 de travail

- Les comparaisons sont enregistrées par versions et critères qualitatifs, sans score, total ou classement algorithmique.
- Un brouillon de comparaison demeure réservé à l’accompagnateur. Le partage au bénéficiaire est explicite ; un brouillon ultérieur ne retire pas la dernière version déjà publiée de sa lecture.
- La mention d'un diplôme ou titre obligatoire requiert une source officielle, citée avec sa date. Une exigence d'offre ou d'employeur ne vaut pas obligation d'exercice ; une information non vérifiée reste à vérifier.
- Le projet prioritaire et l'alternative éventuelle sont deux décisions saisies par l'accompagnateur à partir de ce que le bénéficiaire a exprimé en séance. Elles sont conservées séparément et présentées dans son parcours.
- La phase d'investigation permet de publier une vérification au bénéficiaire, de relire son retour et d'enregistrer le débrief.
- Ce code n'achève pas GO23 : la recette navigateur, la recette métier, les API et GDA réels restent à faire. GO22 est toujours non validé.

## GO24 — conclusion et suivi à six mois, RC1 de travail

- Le plan d'action est rattaché au dernier projet prioritaire formalisé et versionné à chaque sauvegarde.
- L'accompagnateur peut garder un brouillon interne ou partager explicitement une version au bénéficiaire.
- Chaque action prévoit étape concrète, échéance, moyens/appui et résultat attendu. Le plan accepte 1 à 12 actions.
- Le bénéficiaire peut confirmer la lecture de la version ou demander un ajustement avec un commentaire obligatoire. Sa réponse est historisée ; une demande d'ajustement ouvre un point à revoir.
- Un nouveau brouillon n'efface pas le dernier plan publié côté bénéficiaire.
- L’ordre d’affichage suit l’A3 : résultats détaillés et conditions, plan d’action, synthèse, clôture et suivi à six mois. Les identifiants internes des phases 8 et 9 restent stables. Trois PDF sont téléchargeables et leur retour GDA idempotent est codé mais pas testé sur le GDA réel ; Word, le rappel externe et l’archivage/destruction GDA restent à raccorder. GO24 reste non validé.

## GO22 RC3H — Règle métier du rapprochement savoirs/diplômes

Le rapprochement porte d’abord sur les savoirs et compétences ROME étayés par le parcours (expérience, études même sans diplôme, formations, apprentissage personnel). Un diplôme n’est qualifié d’obligatoire que si une source officielle applicable le confirme ; les exigences vues dans les offres restent distinctes. La formation n’est envisagée qu’en réponse à une obligation vérifiée ou à un besoin de développement choisi. Cette RC ajoute le parcours de choix ROME, la sélection de plusieurs attendus, la proposition IA, l’association aux expériences et l’enregistrement versionné de la revue humaine. Les appels API sont implémentés côté écran mais leur fonctionnement réel et leur recette navigateur/VPS restent à vérifier.

## GO22 RC3H — Ressources externes pour les investigations

- Les liens issus du support Clarté360 du 18/10/2026 sont intégrés dans `Mes actions`, que les API France Travail soient disponibles ou non.
- Les phases 2, 5 et 8 affichent les liens adaptés à l'exploration des métiers, à la vérification du marché/des entreprises et aux recherches de formation/certification.
- Le bénéficiaire est invité à consulter seulement les ressources utiles à l'action confiée, puis à noter la source, la date, l'information apprise et l'effet sur son projet.
- Le détail des liens, des produits France Travail souscrits et de l’état réel de leur raccordement figure dans `docs/RESSOURCES_EXTERNES_BENEFICIAIRE.md` et `docs/FRANCE_TRAVAIL_ROME_CONNECTEUR.md`.

## GO22 RC3C — correctifs de recette du 18/10/2026

La consigne « Je souhaite préciser » désigne maintenant la zone **Autres informations sur cette piste ou son contexte**, située en bas de la fiche du métier concerné. L'éditeur distingue la remarque privée et la question 6 publique ; l'aperçu complet fonctionne avant et après validation. Modifier une piste conserve sa position.

Le lien de lancement doit être utilisé pendant sa validité maximale de 900 secondes. Une session déjà ouverte reste utilisable au-delà tant que ses interactions reçues par le serveur respectent le délai d'inactivité configuré, au minimum 60 minutes (60 par défaut, 240 maximum). Une nouvelle ouverture avec un lien expiré reste refusée. Les contrôles automatiques ne prolongent pas la session.

Le questionnaire sauvegarde les changements valides reçus du navigateur. Quitter une zone de texte transmet son contenu ; un texte resté uniquement dans le navigateur ne peut pas être garanti après une interruption. Les boutons de fin d'étape et la transmission finale restent explicites. Une réponse modifiée invalide la confirmation précédente. Les conflits entre fenêtres sont bloqués jusqu'au rechargement volontaire de la version enregistrée.

Les passages rapides entre champs utilisent un accusé de sauvegarde reprenable et la configuration `runner.fastReruns = false` fournie dans `.streamlit/config.toml`. Lancer l'application depuis son répertoire, comme dans le kit, pour charger cette configuration et éviter deux transactions issues de rendus simultanés du même écran.

Le contrat détaillé et les limites sont dans `docs/GO22_RC3C_CORRECTIFS_ET_REPRISE.md`. La suite comporte **198 tests**, dont des tests avec le moteur Streamlit AppTest et une collision réelle entre deux transactions SQLite. Les preuves finales de l'archive, de la recette Chromium locale et les limites Windows/VPS sont livrées avec le rapport RC3C.

## Historique du socle

Ce package reprend le socle GO-19 validé et l'interface Accompagnateur GO-20 validée visuellement par Dominique. Le GO-21 ajoute l'interface Bénéficiaire responsive définie au GO-06 ainsi qu'un mécanisme de synchronisation légère multi-session par fragments Streamlit relisant la source serveur.

## Références
- Framework Clarté360 V5 + Addendum V4.2.
- GO-04 référentiel fonctionnel détaillé.
- GO-05 UX/UI Accompagnateur.
- GO-06 UX/UI Bénéficiaire.
- GO-07 états, droits et validations.
- GO-14 contrat GDA/Hub V1.0.
- GO-15 architecture technique V1.0.
- GO-16 identité VPS V1.0.
- GO-17 sécurité/RGPD/conservation V1.0.
- GO-18 plan de tests V1.0.

## GO-20 — validé fonctionnellement

L'interface Accompagnateur `0.2.0-go20 RC2` a été jugée visuellement satisfaisante par Dominique le 13/10/2026. Le correctif RC2 concernait uniquement le helper de recette et conservait intact le garde-fou de sécurité des jetons `<= 900 s`.

## GO-21 — Interface Bénéficiaire

La version `0.3.0-go21-rc2` ajoute et corrige :
- accueil avec synthèse `À lire / À faire / À valider / Terminé`, sans en faire toute la navigation ;
- navigation principale Bénéficiaire `Accueil / Mon parcours / Mes actions / Mes documents` ;
- `Mon parcours` permet de parcourir les 12 résultats en lecture seule, y compris les étapes à venir ;
- `Mes actions` regroupe uniquement les travaux réellement confiés au bénéficiaire hors séance ;
- carte `Ma prochaine action` prioritaire ;
- navigation sans exposition des phases techniques 0 à 11 ;
- progression simple `Explorer → Vérifier → Choisir → Agir → Finaliser` ;
- espace `Mes documents` limité aux versions explicitement publiées au bénéficiaire ;
- écrans B-P0 à B-P11 et B-IS-01 selon le Framework GO-06 ;
- phase 0 explicitement matérialisée comme `Mon parcours professionnel enrichi`, préparé en séance avec assistance IA, puis publié pour relecture/confirmation ;
- contrat visuel PDF / Word / Impression pour le parcours enrichi ;
- côté Accompagnateur, chaque phase distingue désormais travail de séance, résultat publié au bénéficiaire et validation ;
- langage courant, aucune donnée technique, aucun score/podium/classement ;
- responsive mobile/tablette/ordinateur ;
- auto-rafraîchissement ciblé des zones de synchronisation via `st.fragment(run_every=2.0)` ;
- sonde de synchronisation synthétique disponible uniquement si `CLARTE360_GO21_SYNC_PROBE=1` pour la recette simultanée Accompagnateur/Bénéficiaire.

Les mutations métier détaillées des phases et formulaires restent volontairement branchées aux GO-22 à GO-24. Les boutons concernés sont donc présents comme contrat UX mais désactivés dans cette RC2 afin de ne pas simuler une validation ou une sauvegarde qui n'existe pas encore.

## Lancer les tests

```bash
PYTHONPATH=. pytest -q
```

## Jeu synthétique GO-21

```bash
PYTHONPATH=. python tools/go21_demo_seed.py \
  --db /tmp/go21-demo.sqlite3 \
  --signing-key "<CLE_FICTIVE_DE_RECETTE>"
```

Le script produit deux jetons temporaires, `ACCOMPAGNATEUR_TOKEN` et `BENEFICIAIRE_TOKEN`, pour le même dossier synthétique. Leur durée reste conforme au contrat de sécurité : `<= 900 s`.

## Secrets

La source de vérité de production reste `/opt/clarte360/secrets/secrets.toml`. Le fichier `.streamlit/secrets.example.toml` ne contient que les noms de clés attendus.

---

## GO22 — Orientation avant l'étude du CV — RC1 de travail (13/10/2026)

**Version candidate : `0.4.0-go22-orientation-rc1` ; schéma 2 additif. GO22 complet NON VALIDÉ.**

Les trois écrans métier `Mes idées à moi` → `Mes repères professionnels` → `Mes premières directions` sont disponibles dans le menu ENTRÉE Accompagnateur, avant `Sources et CV` et l'actuelle phase 0. Le CV ne conditionne plus la discussion initiale, mais reste nécessaire pour l'analyse des expériences.

- Expression libre des idées avec origine conservée, formulation initiale immuable et décisions **à prendre par le bénéficiaire**. Les nouvelles idées et directions sont `À décider ensemble`, jamais activées automatiquement.
- Perspective éventuelle de l'entreprise stockée dans un bloc **séparé** (provenance, décision du bénéficiaire, absence de partage à l'entreprise). Aucun espace ni compte employeur créé.
- Relecture des cinq outils : Boussole (maximum trois valeurs explicitement choisies), Moteurs (les dix moteurs), Préférences, IPIP (conditions de réussite, jamais verdict de métier), PIP RIASEC (intérêts distincts des compétences). Les notes de résultats sont à vérifier en séance ; **pas d'import automatique des rapports dans cette RC1**.
- Liste de directions choisies, sans sélection des métiers ROME ni score de compatibilité.
- Sauvegarde versionnée sur serveur ; publication explicite ; bénéficiaire en lecture seule, avec réponse personnelle `CONFIRME` ou `CORRECTION_DEMANDEE` et journal de preuve.
- Pas de transmission employeur, de partage automatique, d'IA qui déciderait, de génération de rapport fictive.

Le nouveau parcours d'entrée est un **choix propre à l'application D5**, et non une modification du référentiel maître A3 du BC ou du dossier 12.

### Périmètre non livré dans cette candidate

- Connexion GDA/APS/rapports des cinq outils : **aucune synchronisation réelle ni extraction des résultats automatique**. La saisie des repères est une retranscription accompagnée, identifiée comme telle.
- Enrichissement IA du CV limité au PDF texte, DOCX et TXT ; extraction temporaire, coordonnées courantes retirées, propositions par expérience et questions de séance. Les scans, formats supplémentaires, validation métier et publication/export Word restent à recetter et compléter dans GO22.
- Les phases métier 0 à 11 hors sas initial conservent les contrats visuels GO21 et leurs fonctions non encore connectées ; un bouton affiché désactivé n'est pas une fonction livrée.
- E2E navigateur Streamlit et liaison Hub/GDA réels : non testés localement. Aucun passage en production, aucune migration de base existante sur VPS.

### Tests

Depuis le dossier extrait :

```bash
PYTHONPATH=. python -m pytest -q
PYTHONPATH=. python -m compileall -q .
```

GO21 75 tests, deux attentes historiques adaptées à la nouvelle entrée métier. GO22 ajoute 18 scénarios. Migration GO21 schéma 1 → GO22 schéma 2 testée sur une base locale issue du code GO21, sans perte des données de démonstration. Voir rapport de recette dans le dossier GO22 officiel.


---
## GO22 — RC2, préparation avant séance C-AV1 / C-AV2 (14/10/2026)

**Nouveau jalon CANDIDAT : `0.4.0-go22-preparation-rc2`, base SQL additive `3`.**

### Circuit métier implémenté

1. **Accompagnateur** : prépare une première version du questionnaire individuel avec un tronc fixe, des idées APS non validées et des références de sources autorisées. Dans cette candidate, le contenu métier des résultats est saisi sous contrôle humain ; le raccordement réel au Hub/GDA n'est PAS actif.
2. **Accompagnateur** : relit et modifie les formulations, options et rubriques puis **verrouille** définitivement la version du questionnaire Q ; cette version devient immuable au niveau SQL (triggers SQLite).
3. **Bénéficiaire** : le questionnaire verrouillé devient visible depuis l'accès signé. **ZÉRO IA** pendant la saisie, autosauvegarde explicite, puis transmission finale personnelle R1, immuable.
4. **En entretien partagé** : l'accompagnateur voit R1, peut corriger réponses et observations avec la personne ; la confirmation expressément recueillie puis la validation professionnelle produisent R2 **si et seulement si des réponses ont changé**. R1 est toujours préservée ; les brouillons n'alimentent pas C-AV3.
5. **C-AV3** : l'écran Accompagnateur lit la **dernière version validée** comme contexte factuel de préparation. **Aucun service IA réel C-AV3 n'est livré à ce stade.** La recette IA réelle est un jalon ultérieur indispensable.

### Formulaires C-AV2

- Boussole : jusqu'à **3 valeurs essentielles au futur travail**, librement choisies, jamais précochées (ni par score ni par ancien travail sur les valeurs-énergies).
- Moteurs : **3 essentiels** + **2 appréciables**, choix explicites non contradictoires.
- Préférences : **3 conditions à rechercher**, **3 situations à éviter** ; listes distinctes pour chaque pôle du continuum.
- IPIP-NEO-120 : jusqu'à **2 conditions favorables / 2 vigilances**, exprimées au conditionnel, pas d'aptitude/décision métier.
- PIP RIASEC : jusqu'à **5 activités attirantes / 3 à éviter**, intérêts déclarés et non compétences.
- Métier cité : questions fixes à choix multiples sur le sens de la piste, le cadre professionnel, les attraits et les conditions d'accès. **Absence de piste acceptée.** Les idées APS ne sont pas cochées par défaut ; elles sont reprises sous forme de choix à confirmer.
- Entreprise / financeurs : perspective employeur présentée dans un volet distinct, sous réserve de l'autorisation et du contexte tripartite approprié, y compris cofinancement. La présence d'une entreprise familiale ne crée pas de tripartite.

### Démonstration technique, données FICTIVES seulement

```bash
PYTHONPATH=. python tools/go22_rc2_demo_seed.py --db /tmp/go22-rc2-demo.sqlite3 --signing-key "CLE_FICTIVE_RECETTE_SEULEMENT" --stage ready
```

Choix de `--stage` : `empty` (l'accompagnateur construit Q), `ready` (Q verrouillé, visible, R1 non transmise), `answered` (R1 transmise) ou `reviewed` (R2 revalidée, R1 conservée). Le script **réinitialise la base spécifiée** et affiche des jetons temporaires pour deux rôles. N'utiliser **JAMAIS** une base réelle ni la clé de signature du VPS. Le lancement Streamlit temporaire doit respecter le Framework VPS et la vérification de non-collision d'URL/port.

### Tests et limites

- 110 scénarios PyTest en local (sources), compilation Python, migration additive depuis la VRAIE base de démonstration GO21 RC2 (schéma 1 → 3), validation SQL des snapshots immuables.
- À effectuer : lancement navigateur réel Streamlit sur VPS de recette isolé (Streamlit indisponible dans l'environnement local), tests de navigation mobile, Hub/APS cinq outils sans ressaisie, invitations et rappels calendrier, IA C-AV3 avec appels réels et données synthétiques, droits partage et confirmation humaine, tests de non-régression du parcours complet.
- **Aucun code GitHub, VPS production, GDA/D12/D13/D17, ni référentiel A3 maître modifié.** GO21 RC2 demeure la dernière version validée.

## GO22 RC3 — Questionnaire unique C-AV1 → C-AV2 (candidate de recette)

- En mode ACCOMPAGNEMENT, l'Accompagnateur crée, revoit et fige UNE Q contenant
  C-AV1 et C-AV2 avant d'ouvrir l'accès au bénéficiaire.
- C-AV1 : zéro/une/plusieurs pistes, ajout ou retrait sans effacer la provenance
  historique, remarques ciblées sur le contexte, question neutre sous toute
  piste retenue. Les remarques ne sont jamais attribuées au bénéficiaire.
- C-AV2 : valeurs (3 max, libre choix), moteurs (3 max), Préférences (3
  dimensions et pôles vérifiés, importance personnalisée, situation à éviter
  distincte). Si une source manque : question libre, aucun faux résultat.
- IPIP/PIP : rapports SOURCES, aucun mini-test répété ni jugement sur profil;
  toute simulation FICTIVE est marquée comme telle.
- Bénéficiaire : C-AV1 obligatoire avant C-AV2, sauvegardes de brouillon,
  validation définitive unique R1. ZÉRO appel IA pendant la passation.
- En séance : R1 historique conservée; correction R2 sous confirmation et
  contrôle professionnel; C-AV3 IA réelle NON LIVRÉE dans cette RC3.
- Source de vérité serveur, schéma SQL 3 de RC2 préservé, format Q/R métier
  V2 versionné et coexistence des dossiers RC2 historiques.

**Limites connues** : ni lecture automatique Hub/GDA des PDF, ni e-mails,
calendrier/rappels, accès direct aux PDF par lien sécurisé, ni vrais appels IA
C-AV3. Les champs Accompagnateur de source sont des références et libellés
contrôlés ; les pièces ne sont pas réimportées. Une recette sur VPS isolé
avec Streamlit réel et deux sessions reste obligatoire avant validation.
Le contenu client réel (ex. Fabienne) est strictement absent du package.


## GO22 RC3A — Correctif de visibilité Bénéficiaire du 16/10/2026

- Parcours questionnaire unique en deux étapes C-AV1 puis C-AV2 inchangé.
- Un seul clic Accompagnateur `Valider définitivement et mettre à disposition`
  fige la version Q ET active sa disponibilité dans le même COMMIT SQL.
  Les deux événements de traçabilité sont conservés.
- Accueil Bénéficiaire : questionnaire prioritaire sur les anciennes tâches de
  recette, lien explicite pour commencer, suivi après transmission R1.
- Ancien dossier de RC3 resté verrouillé mais non publié : le bouton de
  rattrapage `Rendre le questionnaire disponible maintenant` reste proposé.
- Compatible dossiers RC2 : leur circuit historique de publication reste inchangé.
- Test sur corpus entièrement fictif ; aucune intégration mail, Hub ou IA réelle.
- Tokens de lancement = 15 minutes maximum (contrat signé); cela concerne le lien initial, pas la durée d'une session active. Le délai d'inactivité de la session est d'au moins 60 minutes. Rouvrir avec
  les raccourcis renouvelle le lien. Serveur temporaire = maximum 3 heures.
- La candidate RC3A ne remplace pas GO21 RC2 officiellement validée.

## GO22 RC3B — Refonte de la passation C-AV1 / C-AV2 (candidate non validée)

Cette candidate corrige les problèmes constatés par le propriétaire en recette
RC3A : disparition des sous-questions dans un formulaire à rafraîchissement
tardif, « Select all », absence de repères pédagogiques chiffrés et pauvreté
des restitutions PIP/IPIP. Voir GO22_RC3B_RAPPORT_ET_RECETTE_20261017.md.

- La base RC3A est conservée : publication/validation Q en un acte, versions
  R1/R2 immuables, origine APS et droits séparés, C-AV1 puis C-AV2, zéro IA
  pendant les réponses.
- C-AV1 : toutes les sous-questions visibles directement sur chaque fiche ;
  les réponses conditionnelles réagissent sans cliquer sur Enregistrer ; les
  choix multiples sont clairement affichés. Les idées nouvelles disposent de
  leur champ de contexte dès leur saisie. Absence de piste admise.
- C-AV2 : repères pédagogiques par source et unités natives, choix personnels
  toujours à zéro au départ ; maximum 3 valeurs, moteurs, dimensions de
  Préférences, aucune sélection globale ; vrais libellés des pôles.
- PIP / IPIP : lecture des dimensions et résultats vérifiés *si* fournis par
  une source autorisée. Le PIP porte son code exactement tel que la source
  le donne (3 lettres dans le PIP fictif utilisé), avec explication ROME.
  Aucun nouveau test, aucun matching ROME, aucune interprétation IA.
- Données de recette : résultats et sources TOUS SYNTHÉTIQUES, différents
  d'un dossier client. La structure ``result_summary`` est un contrat
  d'entrée **non encore raccordé au Hub/GDA**. Absence de source => pas de
  score inventé. Les PDF ne sont pas encore ouverts directement depuis D5.
- Le rendu Streamlit sur navigateur/VPS réel doit être recetté par le
  propriétaire ; tests Python et contrôles de logique seuls ne la remplacent pas.
- Aucun code production/GitHub/VPS stable modifié. GO21 RC2 dernière version
  officielle validée ; GO22 RC3B candidate de travail NON VALIDÉE.

## GO22 RC3D/RC3G — C-AV3 assistée après R1 / R2 (candidate technique non validée)

- Lancement volontaire depuis l'espace Accompagnateur uniquement, après R1.
  La passation Bénéficiaire reste sans IA.
- Les entrées sont les réponses C-AV1/C-AV2 et les repères/références déjà
  déclarés dans Q. Aucun CV ni PDF externe n'est envoyé par ce connecteur.
- Les propositions doivent citer des repères, poser des questions de séance
  et signaler les incertitudes. Elles ne calculent aucun score et ne choisissent
  ni projet ni métier à la place de la personne.
- Les sorties sont conservées en historique interne immuable, associées à une
  empreinte de Q, réponses et sources. Toute différence rend l'ancienne sortie
  obsolète. Une analyse sur un brouillon R2 est provisoire jusqu'à confirmation.
- Le bouton de lancement Accompagnateur utilise le contrat déjà partagé dans
  Clarté360 : `[openai] api_key` (avec repli sur `OPENAI_API_KEY`) et `model`
  (défaut `gpt-5-mini`). Le client a un délai de 35 s et aucun retry; l'adaptateur
  appelle Responses avec `store=False` et un schéma JSON strict. Aucun nouveau
  nom de secret n'est introduit. Le bouton reflète la disponibilité du secret.
- Le snapshot conserve aussi la version de consigne, les références citées,
  le nombre de jetons disponible et l'empreinte SHA-256 de la sortie.
- La disponibilité et les droits des vraies sources Hub/GDA ne sont pas
  changés : l'IA ne reçoit que les repères déjà présents dans Q. Des appels
  synthétiques vérifient le contrat, pas le fournisseur ni les accès réels.
- GO21 RC2 reste le dernier jalon officiellement validé. RC3G est une candidate
  de travail ; l'appel IA synthétique valide le raccordement logiciel, pas la
  disponibilité du secret, l'appel réel, le test navigateur/VPS temporaire ou
  la recette métier.

## GO22 RC3E — correction de la réponse « à affiner »

- Les trois sections de priorités C-AV2 distinguent désormais une absence de
  priorité identifiée de l'impossibilité de hiérarchiser pour le moment.
- Cette réponse est proposée que les résultats structurés soient présents ou
  que la personne réponde librement faute de source.
- Les choix de priorités et une réponse d'absence restent mutuellement exclusifs.
- Les écrans précisent qu'un rapport peut être référencé sans que ses résultats
  aient été importés. Les références et résultats saisis manuellement ne sont
  pas présentés comme une récupération Hub/GDA vérifiée.
- GO21 RC2 reste le dernier jalon validé. Aucun import réel des rapports, appel
  IA réel, recette VPS ou validation métier n'est revendiqué.
