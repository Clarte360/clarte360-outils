# CLARTÉ360 — Candidat GO4 Qualité 1

Version : **3.0.0-P5-RC2-GO4-CANDIDAT-1**, préparée le 19 octobre 2026.

Ce répertoire contient l’application complète issue de la RC2 officielle, augmentée du seul incrément GO4 et des raccordements nécessaires. Il s’agit d’un **candidat hors production**, soumis à une décision de validation séparée. Le bandeau de l’application identifie explicitement cette version candidate.

## Références

- RC2 officielle : `clarte360-gestion-actions-v3.0.0-P5-RECETTE-RC2.zip` ; SHA256 `a7b802c3f2f4f676d5773798d8f52124e710a9813296f7f9f0afa0f448292cc9`.
- CDC Qualité V1.0 et maquette HTML V1.1 du kit du 18 octobre 2026, validés au GO3. SHA256 du kit : `e2a56ce305ff54e41b21efa6ba993f782e2f1a1dd6d8ce5a2013be1efff87c5c`.
- Framework CLARTÉ360 V5, Addendum V4.2, Framework VPS V1.5 et décisions Qualité applicables. L’inventaire de livraison identifie les fichiers modifiés ; les anciens documents de recette RC2 restent des documents historiques.

## Comportement de l’incrément

Le plan repose sur la ligne `quality_events` existante. Une prévention, une réclamation, un audit, une amélioration ou une action issue de veille utilise le même plan. Une nouvelle prévention n’exige ni incident ni formation. Les étapes facultatives n’ajoutent pas une deuxième action à clôturer.

La clôture demande le travail réalisé et son résultat. Toutes les étapes encore ouvertes sont présentées dans le même dialogue, sans issue prédéfinie. Une issue manquante, un abandon sans motif ou un échec de transaction empêche toute clôture partielle. Une réouverture garde la référence et les anciens bilans dans l’historique. Une sauvegarde identique n’invente pas de transition ; une version ancienne ne peut écraser une modification récente.

L’affectation utilise les personnes existantes et leurs droits actuels. Elle comprend acceptation, refus, réaffectation, échéance et retour pour validation. Une affectation seule n’autorise pas un intervenant à clôturer ni à lire les échanges personnels d’un demandeur. Les droits nominatifs d’un référent sont gérés sur la fiche, y compris la révocation d’un compte devenu inactif. Les dossiers marqués à accès restreint ne sont pas ouverts à tous les administrateurs. Aucun organigramme ni rôle de sous-administrateur n’est ajouté.

Les espaces ADMIN, INTERVENANT, BÉNÉFICIAIRE et CLIENT utilisent le même service avec leur contexte authentifié. Un client accède à ses propres demandes ; deux contacts d’une même entreprise ne partagent pas implicitement leurs échanges. Les lectures, recherches, exports, pièces et notifications revérifient les droits.

Les enquêtes HOT/COLD, leurs réponses et les circuits existants sont conservés. La méthode V1 distingue les questionnaires des réponses à des items, les invitations réellement envoyées des invitations futures et les personnes distinctes des questionnaires. Les versions de questions sont figées pour chaque nouvelle campagne. La publication Client d’un agrégat requiert une politique confirmée et des contrôles de confidentialité ; le calendrier d’une formation d’un seul inscrit reste indépendant de ces seuils. Voir `QUALITE_METRIQUES_V1.md`.

La veille possède un registre de technologies et de sources, un calendrier mensuel et un contrôle manuel. Ses sources sont validées explicitement ; la collecte est bornée et défendue contre les destinations privées, redirections dangereuses et contenus non fiables. Une information peut devenir une action unique ou une décision motivée sans tâche fictive. Les versions restent conservées. Voir `QUALITE_VEILLE_GO4.md` pour les formats et limites réels.

## Adaptations de données et reprise

`db.init_db` ajoute les colonnes, tables, index et contraintes GO4. Cette initialisation ne transforme pas silencieusement les demandes historiques et ne purge aucune donnée. Les nouveaux champs de qualification du patrimoine commencent à `A_EXAMINER`.

La reprise administrative utilise les correspondances RC2 explicites. Les cas sans organisme demandent un choix explicite ; une ressemblance de titre ne fusionne pas deux demandes. Une mesure rattachée à une ancienne affaire devient une étape de celle-ci. Les auteurs, dates, réponses et références d’origine sont conservés ; un auteur non enregistré reste signalé comme inconnu. Les anciennes pièces de signalement restent liées à leur source ; leur téléchargement contrôle le répertoire serveur `data/trainer_reports`, sans exposer de chemin au navigateur. Une pièce absente ou située hors de ce répertoire est signalée à l’administration, sans recherche libre sur le disque.

Les anciens chemins de mutation Qualité refusent de modifier une ligne déjà prise en charge par GO4 : la clôture et les réponses passent par le plan canonique. Les autres modules conservent leurs services.

Les fichiers historiques d’origine et les documents partagés ne sont jamais effacés par la reprise. La suppression unitaire demeure désactivée tant que la conservation n’a pas été configurée. Lorsqu’elle est explicitement autorisée, elle retire les données propres au dossier et conserve un reçu minimal ; elle ne supprime ni la formation ni les documents partagés. Les fichiers physiques hérités du répertoire de signalements ne font pas l’objet d’un nettoyage automatique : leur cycle de conservation et les copies de sauvegarde doivent être examinés séparément.

## Notifications et tâches de fond

Les événements métier et la file de notifications sont enregistrés dans la même transaction. Les avis dans l’application réutilisent la boîte existante. Le courriel reste désactivé par défaut au niveau de l’organisme et nécessite aussi l’activation SMTP globale. TEST et `A_EXAMINER` ne déclenchent pas de courriel automatique GO4. Les délais de rappel doivent être renseignés explicitement.

Un courriel contient seulement une invitation à se connecter. **ACCEPTED** signifie accepté par le fournisseur, jamais lu ou reçu avec certitude. **RETRY** désigne un refus explicite avant acceptation ; **UNKNOWN** conserve un résultat ambigu sans renvoi automatique. Le suivi de ces états est visible dans la fiche administrative. Une modification d’échéance, une clôture ou une suppression retire les alertes devenues obsolètes. L’activation et les droits sont relus avant chaque prise en charge.

Le worker RC2 appelle `quality_jobs.run_quality_jobs`. La veille et les envois GO4 utilisent chacun une tâche de fond unique ; un fournisseur lent ne bloque pas Teams ou les autres traitements RC2. Les réservations de base empêchent une prise en charge concurrente. Un blocage durable du transport SMTP conserve une remise en cours ou incertaine : il nécessite un diagnostic du fournisseur, sans relance aveugle. Aucun nouveau service, port ou URL de production n’a été installé.

## Vérification sur une copie fictive

Le ZIP ne contient aucune base réelle, données ESSAI2, fichier de secrets opérationnel, environnement virtuel ou cache. Les pièces d’un ancien environnement ne sont pas des fichiers de code et ne sont pas embarquées. Les essais de livraison ont utilisé Python 3.12, SQLite et les dépendances identifiées dans les preuves ; `requirements.txt` RC2 est conservé.

Extraire le candidat dans un nouveau répertoire. Pour les tests automatisés, créer un environnement dédié, installer les exigences puis exécuter depuis la racine de cette copie :

```bash
python3 -m venv .venv-go4
.venv-go4/bin/python -m pip install -r requirements.txt
PYTHONPATH=tests:. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv-go4/bin/python -m pytest -q -p go4_network_lock -p no:cacheprovider tests/test_go4_*.py
```

Le module de test `go4_network_lock` bloque les connexions et résolutions réseau avant la collecte des tests. Chaque scénario utilise sa base fictive. Le rapport et la matrice de livraison donnent les commandes, résultats et réserves ; des passages intermédiaires existent et ne doivent pas être additionnés comme des cas uniques.

Pour une recette interactive séparée, le modèle `.streamlit/secrets.go4-recette.example.toml` donne une base locale distincte, MAIL et Graph désactivés. Il ne contient aucun secret réel. Le copier vers `.streamlit/secrets.toml` uniquement dans la copie de recette neuve, puis générer localement une clé de mise en place fictive si le parcours d’initialisation en demande une. Le navigateur peut être lancé localement avec :

```bash
.venv-go4/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

Cette commande est une indication de recette locale ; elle n’a pas été exécutée sur le VPS. La recette fournie n’a lancé aucun worker réel ni envoyé de message à des personnes.

## Décisions restant distinctes de cette livraison

Le propriétaire réalise la première utilisation prévue au CDC, notamment R01, R02, R05 et R07. Les sources réelles, droits fournisseurs, heure/fuseau, règles de conservation, référents concernés et publication des résultats sont à renseigner dans leur environnement réel avant activation. Le collecteur n’atteste pas l’exhaustivité réglementaire ni l’accès aux sources protégées ou non configurées.

Aucun commit, push GitHub, déploiement VPS ou purge de données réelles n’a été réalisé. L’intégration GitHub Desktop reste au propriétaire. Avant une éventuelle mise en service autorisée séparément, préparer une sauvegarde cohérente du code, de la base et des documents. Après l’enregistrement de données GO4, remplacer seulement le code par RC2 ferait perdre la prise en charge du nouveau suivi : un retour arrière doit restaurer un ensemble cohérent et traiter explicitement les écritures postérieures. Aucun script de migration destructive ou de retour automatique n’est livré.
