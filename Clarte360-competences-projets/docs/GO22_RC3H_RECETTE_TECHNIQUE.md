# GO22 RC3H — recette technique locale

**Version testée :** `0.4.0-go22-rome-matching-rc3`  
**Statut produit :** candidate GO22, non validée, non déployée. GO21 RC2 reste la dernière version officiellement validée.

## Contrôles réalisés

- Compilation de tous les modules Python et des tests : réussie.
- Suite complète : **235 tests réussis** (`pytest -o addopts='' -q`).
- Rapprochement ROME dans `Streamlit AppTest` : le test charge une fiche synthétique, coche un savoir, associe des études sans diplôme comme preuve de parcours, puis enregistre une revue humaine en « à confirmer ».
- Boucle d’investigation dans `Streamlit AppTest` : le test crée une action d’enquête sur les offres, saisit un retour bénéficiaire avec source, date, constat et effet sur le projet, puis vérifie son état « à débriefer » côté accompagnateur.
- Archive ZIP locale : intégrité contrôlée ; aucun secret, fichier `.env`, cache Python ou cache pytest n’est inclus.
- Dossier de jalon SharePoint : archive déposée et métadonnées relues après dépôt.
- Seed de prévisualisation VPS : crée une nouvelle base fictive avec une fiche ROME synthétique M1203, emploi/études/formation sans diplôme, une enquête offres et deux jetons temporaires Accompagnateur/Bénéficiaire. Il refuse d’écraser une base existante.

Les scénarios d’interface utilisent des données entièrement synthétiques. Aucun dossier réel ni appel live n’est utilisé par ces tests.

## Lancement possible sur VPS de recette isolé

Le dossier `deploy/README.md` cadre la distinction entre prévisualisation temporaire et mise en service. Après synchronisation du commit candidat depuis GitHub dans une copie temporaire, les commandes suivantes sont à adapter au chemin unique et au port libre retenus dans la plage 8610–8650 :

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export CLARTE360_CP_DATA_DIR="/tmp/clarte360-go22-rome-rc3h-<id>/data"
mkdir -p "$CLARTE360_CP_DATA_DIR/db"
```

Créer dans cette copie un `.streamlit/secrets.toml` temporaire avec une clé fictive de recette dans `[COMPETENCES_PROJETS_CONNECTOR].LAUNCH_SIGNING_KEY` et `session_timeout_minutes = 60`. Pour tester les API sans recopier leurs secrets, ajouter au `config.toml` temporaire :

```toml
[secrets]
files = ["/opt/clarte360/secrets/secrets.toml", "/tmp/clarte360-go22-rome-rc3h-<id>/.streamlit/secrets.toml"]
```

La première source fournit les sections France Travail et OpenAI du coffre VPS ; le fichier local apporte la clé fictive de signature de la base de démonstration. La configuration de recette ne doit jamais afficher ni recopier les valeurs. Pour une prévisualisation sans appel API, la ligne `[secrets]` est facultative et seule la fiche ROME fictive du seed est utilisée. Puis créer la base neuve et lancer l'application au port temporaire choisi :

```bash
.venv/bin/python tools/go22_rome_demo_seed.py \
  --db "$CLARTE360_CP_DATA_DIR/db/competences_projets.sqlite3" \
  --signing-key 'CLE_FICTIVE_DE_RECETTE_SEULEMENT_40_CARACTERES'
.venv/bin/streamlit run app.py \
  --server.address 127.0.0.1 \
  --server.port <PORT_TEMPORAIRE_LIBRE> \
  --server.headless true
```

Le seed affiche deux jetons valables 15 minutes. Ouvrir chacun dans le navigateur via le tunnel SSH avec `?mode=accompagnement&launch=<JETON>` ; le rôle vient du jeton signé, le paramètre de mode reste toujours `accompagnement`. Pour l'essai live, charger une fiche France Travail depuis l'écran Accompagnateur, puis lancer l'analyse IA avec le parcours fictif du seed ; ne saisir aucune donnée réelle. Si un scope ou une clé manque, conserver le message de disponibilité/erreur et utiliser les liens de ressources externes intégrés. Cette procédure n’active ni systemd ni Nginx et n’utilise pas le port 8514. Après arrêt du processus, la candidate reste une recette, sans transfert vers le dossier stable.

### Essai C-AV3 séparé

Le seed ROME précédent ne crée pas les réponses C-AV1/C-AV2 nécessaires à C-AV3. Pour vérifier l'écran C-AV3 sur des réponses R1 fictives, créer une **autre** copie de recette avec son propre chemin temporaire, sa propre base neuve et un autre port libre de 8610–8650, puis définir son répertoire de données :

```bash
export CLARTE360_CP_DATA_DIR="/tmp/clarte360-go22-cav3-<id>/data"
mkdir -p "$CLARTE360_CP_DATA_DIR/db"
.venv/bin/python tools/go22_rc3_demo_seed.py \
  --db "$CLARTE360_CP_DATA_DIR/db/cav3_synthetic.sqlite3" \
  --signing-key 'CLE_FICTIVE_DE_RECETTE_SEULEMENT_40_CARACTERES' \
  --stage answered --scenario two
```

Ce seed prépare une R1 entièrement fictive. Depuis l'espace Accompagnateur, lancer C-AV3 avec le coffre IA déjà déclaré dans `secrets.files`, puis vérifier les pistes, questions et incertitudes produites. Ne pas mélanger cette base avec celle du seed ROME : le seed C-AV3 initialise sa propre base. L'appel réel IA n'a pas encore été exécuté ni validé par cette recette locale.

## Étapes après cette prévisualisation synthétique

1. Importer le dépôt dans GitHub selon la procédure Clarté360 ; le commit et le push sont pilotés par Dominique.
2. Utiliser uniquement la base synthétique créée par le seed, la clé de signature fictive temporaire et les deux jetons affichés. Ne pas utiliser de données bénéficiaire réelles.
3. Parcourir avec les deux rôles le workflow Accompagnateur/Bénéficiaire : rapprochement des savoirs ROME, preuves par emploi/études/formation, retour d’investigation et débriefing.
4. Si les accès API existent dans le coffre central, tester France Travail et l’IA avec les jeux synthétiques dédiés : seed ROME pour la fiche/rapprochement et seed R1 pour C-AV3. Vérifier les scopes et routes France Travail correspondant aux produits réellement souscrits ; aucun endpoint ni scope non vérifié n’a été inventé. Pour l’IA, contrôler les propositions, références d’expérience et statuts, et confirmer l’absence de décision automatique. Si un accès échoue, garder les ressources externes utilisables et noter le code HTTP ou le message fonctionnel sans copier de secret ni de réponse brute.
5. Consigner les observations métier, notamment la lisibilité des cartes, les liens de ressources et la navigation de retour. Cette prévisualisation ne vaut pas validation de mise en service.

Les données statistiques d’accès à l’emploi sont présentées comme des tendances concernant une population et une période. Elles ne prédisent pas les chances individuelles et ne remplacent ni l’enquête du bénéficiaire ni la vérification officielle d’une obligation de diplôme.
