# FRAMEWORK VPS CLARTÉ360 --- V1.0

**Statut : Référentiel technique transverse Clarté360**\
**Date : 10 septembre 2026**\
**Périmètre : toutes les applications Clarté360 déployées ou destinées
au VPS**

## 1. Objet

Ce framework fixe une méthode unique et durable pour l'hébergement, le
versionnement, le déploiement, la maintenance et l'évolution des
applications Clarté360 sur VPS.

Il complète le FRAMEWORK CLARTÉ360 général sans remplacer les règles
métier propres à chaque application.

Objectifs : éviter les interférences entre applications ; protéger
données, secrets et environnements ; garantir qu'une nouvelle version
n'écrase pas une correction ou des données ; utiliser le même processus
GitHub → VPS ; simplifier PowerShell/SSH ; préparer l'arrivée de
nombreuses applications.

## 2. Architecture de référence

Dépôt GitHub commun : **Clarte360/clarte360-outils**.

Racine VPS :

`/opt/clarte360/clarte360-outils/`

Chaque application possède un dossier autonome et stable, par exemple :

-   `clarte360-emargements-v1.0.0/`
-   `clarte360-contractualisation-v1.0.0/`
-   `clarte360-aps-beneficiaire-v1.1.0/`

**Règle fondamentale : une application = un dossier stable sur le VPS.**

Les incréments I8, I9, I10, etc. ne créent pas de nouveau dossier de
production. La version est portée par le code, le CHANGELOG et les
rapports de tests.

## 3. Séparation code / environnement / secrets / données

### Code suivi par Git

Fichiers Python, tests, configuration non sensible, dépendances,
documentation, CHANGELOG, migrations et ressources statiques
nécessaires.

### Environnement Python

Chaque application possède son propre `.venv/`. Il reste sur le VPS et
n'est jamais suivi par Git. Une application n'utilise jamais le `.venv`
d'une autre.

### Secrets

Ne sont jamais suivis par Git : `.streamlit/secrets.toml`, clés API,
mots de passe, certificats privés, secrets Microsoft/Entra/Graph, SMTP,
tokens et identifiants.

### Données persistantes

Bases SQLite, `data/` métier, signatures, documents générés, exports,
pièces bénéficiaires et sauvegardes ne doivent jamais être écrasés par
un `git pull`.

## 4. `.gitignore` racine obligatoire

Le dépôt commun doit disposer d'un `.gitignore` racine protégeant toutes
les applications.

``` gitignore
**/.venv/
**/venv/
**/__pycache__/
**/*.py[cod]
**/.pytest_cache/
**/.streamlit/secrets.toml
**/*.pem
**/*.key
**/*.pfx
**/*.p12
**/*.bak
**/*.tmp
**/*~
**/.DS_Store
**/data/
```

Si une application doit versionner une ressource située dans `data/`,
une exception explicite est créée sans affaiblir la règle globale.

## 5. Services systemd

Convention :

`clarte360-<application>.service`

Processus secondaire :

`clarte360-<application>-worker.service`

Chaque service pointe vers le dossier stable de son application et
utilise son propre `.venv`.

## 6. Cycle unique de déploiement

Chaîne de référence :

**Développement → tests → GitHub → VPS → tests VPS → compilation →
redémarrage → recette métier.**

Le PUSH GitHub est la source de vérité de la version à déployer.

Procédure VPS standard :

``` bash
cd /opt/clarte360/clarte360-outils/<application>
git status
git pull origin main
PYTHONPATH=. .venv/bin/pytest -q
.venv/bin/python -m py_compile <fichiers_python_principaux>
sudo systemctl restart <service> [<worker>]
sudo systemctl is-active <service> [<worker>]
```

## 7. Règle absolue sur les correctifs VPS

**Aucune correction définitive ne doit exister uniquement sur le VPS.**

Une modification VPS peut servir temporairement au diagnostic. Si elle
doit être conservée, elle est reproduite dans le code source, testée,
poussée dans GitHub puis redéployée normalement.

Le VPS n'est pas la source de vérité du code.

## 8. Gestion des versions

I8, I9, I10, etc. servent à tracer l'évolution du logiciel. Ils ne
doivent pas entraîner le renommage du dossier de production, la création
d'un nouveau `.venv`, la duplication des secrets ou des données, ni la
réécriture des services systemd.

## 9. Tests

Chaque application dispose progressivement d'un dossier unique `tests/`.

Les tests ne doivent pas être dupliqués à la racine et dans `tests/`.

Commande standard VPS :

``` bash
PYTHONPATH=. .venv/bin/pytest -q
```

Les doublons de noms de modules de test sont interdits.

## 10. Protection contre la pollution inter-applications

Le dépôt est un monorepo : `git status` peut voir plusieurs
applications. Le `.gitignore` racine doit empêcher que les `.venv`,
secrets, caches et données d'une application polluent le travail sur une
autre.

Avant tout déploiement, `git status` doit permettre de distinguer
immédiatement un vrai changement de code d'un élément local du VPS.

## 11. Checklist obligatoire pour toute nouvelle application

1.  Dossier stable dans `clarte360-outils`.
2.  Compatibilité avec le `.gitignore` racine.
3.  `.venv` propre.
4.  Dépendances installées.
5.  Secrets configurés hors Git.
6.  Emplacement des données persistantes défini.
7.  Service(s) systemd créé(s).
8.  Tests définis.
9.  Commande de compilation définie.
10. Déploiement documenté.
11. Redémarrage et persistance testés.
12. Vérification qu'un `git pull` n'altère ni secrets ni données.

## 12. Automatisation future

Objectif : un script standard, par exemple :

`./deploy.sh clarte360-emargements-v1.0.0`

Il devra vérifier Git, effectuer le pull, vérifier le `.venv`, lancer
tests et compilation, redémarrer les services, vérifier leur état et
produire un résumé. Il ne devra jamais afficher les secrets ni supprimer
automatiquement les données de production.

## 13. Sauvegarde et retour arrière

Les données persistantes ont une stratégie de sauvegarde indépendante de
Git. Avant une migration destructive : sauvegarde, identification du
commit/version et procédure de retour arrière.

Un retour arrière Git du code n'est jamais assimilé à un retour arrière
des données.

## 14. Microsoft 365 / Graph et services externes

Les paramètres Microsoft 365, Graph, SMTP et autres services externes
sont séparés du code. Les secrets et certificats privés restent sur le
VPS. Une mise à jour applicative ne doit pas obliger à recréer des
secrets toujours valides.

## 15. Journal de déploiement

Pour les applications critiques, conserver : application,
version/incrément, commit Git, date, résultat des tests et état des
services après redémarrage.

## 16. Règle de conception future

Toute nouvelle fonctionnalité destinée au VPS doit répondre clairement à
quatre questions :

**Où est le code ? Où sont les données ? Où sont les secrets ? Quel
service l'exécute ?**

Si ces quatre éléments ne sont pas séparés clairement, le développement
n'est pas prêt pour le VPS.




**Fin --- FRAMEWORK VPS CLARTÉ360 V1.0**
