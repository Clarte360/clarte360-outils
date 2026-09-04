# Clarté360 – Contractualisation V1.0.0

Pilote Streamlit Community Cloud pour préparer les contrats Clarté360 sans Word.

## V1.0.0

Fonctionnel de bout en bout pour :
- import de la base `GESTION OF CLARTE360_CONTRACTUALISATION_V1.xlsm` ;
- import d'une APS JSON Clarté360 ;
- détection de la première action CLA libre ;
- préremplissage du bénéficiaire ;
- saisie du prix et de plusieurs financeurs ;
- contrôle `somme des financements = prix TTC` ;
- écriture dans `CONV ADM` et `FINANCEMENTS` ;
- téléchargement d'une nouvelle base XLSM ;
- conservation du projet VBA et des composants internes du classeur par modification XML ciblée ;
- recalcul Excel forcé à l'ouverture ;
- génération PDF du **Contrat de prestation de bilan de compétences – particulier bipartite** ;
- export du dossier contractuel JSON.

Les moteurs Coaching / Formation / Tripartite sont prévus par le sélecteur, mais leur PDF reste volontairement désactivé tant que les clauses correspondantes ne sont pas auditées et validées.

## Déploiement Streamlit Cloud

1. Copier ce dossier dans le dépôt GitHub Clarté360.
2. Créer une application Streamlit avec `app.py` comme Main file.
3. Dans **Settings > Secrets**, ajouter :

```toml
[security]
admin_password = "VOTRE_MOT_DE_PASSE"
```

4. Ne jamais mettre un vrai mot de passe ni une clé API dans GitHub.

## API OpenAI

Aucune clé OpenAI n'est requise pour cette V1. C'est volontaire : le texte juridique est déterministe et versionné.
Une API pourra être ajoutée plus tard uniquement pour des aides rédactionnelles non juridiques (par exemple proposer une synthèse courte des objectifs à partir d'une APS), toujours avec validation humaine.

## Limite Streamlit Cloud V1

Aucune base n'est stockée sur le serveur. À chaque session :
**UPLOAD XLSM → travail → DOWNLOAD XLSM**.
La persistance sera traitée lors du passage sur le VPS.

## Correctifs V1.0.2
- suppression de tous les calendriers, dates, prix et montants de financement codés en dur pour un bénéficiaire ;
- seules les données réellement présentes dans l'APS sont préremplies ;
- affichage dans l'application d'une table de correspondance APS JSON -> CONV ADM ;
- les dates, la durée, le planning et le prix sont demandés à l'administrateur s'ils n'existent pas déjà dans CONV ADM ;
- validation de l'onglet FINANCEMENTS sans réécriture automatique de sa structure ;
- contrôle d'intégrité XLSM avant téléchargement : même liste de composants, VBA strictement inchangé, seules CONV ADM, FINANCEMENTS, la table FINANCEMENTS et le réglage de recalcul peuvent évoluer ;
- aucun fichier XLSM n'est proposé au téléchargement si le contrôle d'intégrité échoue.

Sur Streamlit Cloud, un fichier chargé depuis le navigateur ne peut pas être modifié directement sur le disque local de l'utilisateur. La copie mise à jour doit donc être téléchargée. Ce comportement disparaîtra lors du passage à une base persistante sur VPS.
