# GO22 RC3G — C-AV3 alignée sur l'application Recherche de Valeurs

Date : 23 octobre 2026. Statut : candidate technique non validée; GO21 RC2 reste le dernier jalon officiellement validé.

## Référence contrôlée

Application consultée dans OneDrive : `OneDrive - Clarté360/000000GITHUB/clarte360-outils/clarte360-recherche-valeurs-v0_3_1`. Le fichier `app.py` de ce dossier suit la convention `[openai] api_key`, `[openai] model` avec défaut `gpt-5-mini`, repli sur `OPENAI_API_KEY`, client OpenAI avec délai 35 secondes et `max_retries=0`, puis Responses avec `store=False` et JSON Schema strict.

## Alignements appliqués à C-AV3

- Chargement de la clé depuis `[openai].api_key`, puis repli sur `OPENAI_API_KEY` lorsqu'elle manque.
- Chargement du modèle depuis `[openai].model`, avec `gpt-5-mini` par défaut.
- Client OpenAI borné à 35 secondes et zéro retry, conforme au comportement de l'application de référence.
- Vérification `ai_ready()` et bouton de lancement désactivé avec message utile lorsque le secret partagé n'est pas présent dans l'instance.
- Appel Responses `store=False`, schéma JSON strict, contrôle des sources citées, persistance immuable et invalidation liée aux versions R1/R2 conservés.

Le code n'ajoute aucune nouvelle clé IA. Le fichier `secrets.example.toml` donne uniquement la structure attendue, sans valeur réelle.

## Vérifications et limites

- 214 tests Python passent sur la source et sur l'archive RC3G extraite, incluant la lecture du repli d'environnement et les options de client `timeout=35.0`, `max_retries=0` simulées.
- Compilation Python et intégrité du ZIP : PASS.
- Aucun appel API réel, secret réel, commit, push ni déploiement n'a été utilisé ou effectué.
- L'import SOURCE_LIST/SOURCE_GET et les données réelles GDA/Hub restent à raccorder selon GO-14. La recette complète AV1/AV2/AV3 et les phases suivantes GO22/GO23+ restent à accomplir avant V0.
