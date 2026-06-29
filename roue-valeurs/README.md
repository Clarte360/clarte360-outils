# Clarté360 - Roue des valeurs V2.1

## Corrections V2.1

- Correction robuste du chemin du logo avec `Path(__file__).resolve().parent`.
- Affichage du vrai logo Clarté360 dans l’en-tête.
- Application renforcée de la couleur officielle Clarté360 `#008080` sur les titres et boutons.
- Bandeau RGPD/confidentialité conservé.
- Exports horodatés selon la norme : `AAAAMMJJ_HHMMSS_NOM_PRENOM_RoueValeurs.extension`.

## Déploiement

Remplacer le contenu du dossier GitHub `roue-valeurs` par les fichiers de cette version, puis :

1. Commit : `V2.1 - Correction logo et charte Clarté360`
2. Push origin
3. Streamlit redéploie automatiquement.
