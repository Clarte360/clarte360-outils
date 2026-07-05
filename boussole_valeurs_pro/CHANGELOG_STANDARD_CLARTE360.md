# Journal de mise à jour - Boussole Valeurs Pro

Version livrée : V1.4-socle-clarte360  
Socle appliqué : Clarté360 v1.7  
Référence : Moteurs professionnels v1.7.0 référence

## Modifications principales

- Mise à niveau du timeout selon le comportement de référence v1.7 : vérification automatique toutes les 10 secondes via `streamlit-autorefresh`, avec secours par fragment Streamlit ou script de rafraîchissement.
- Passage du motif de fermeture timeout à `timeout_inactivite`.
- Distinction entre battement technique, dernière activité réelle, durée de session et temps cumulé.
- Création d'une nouvelle session lors d'une reprise JSON, sans écraser l'historique existant.
- Ajout des champs de socle dans le JSON : outil, nom de l'outil, version application, version socle, identifiant racine de passation, sessions, sauvegardes, temps cumulé.
- Ajout du bouton latéral `Quitter et télécharger mon JSON`.
- Ajout du formulaire permanent `Contacter Clarté360` dans la barre latérale.
- Ajout des coordonnées officielles et mentions légales Clarté360 dans la rubrique RGPD.
- Ajout d'un pied de page institutionnel discret aux PDF générés.
- Ajout d'un fichier `.streamlit/secrets.example.toml`.
- Ajout de la dépendance `streamlit-autorefresh` dans `requirements.txt`.

## Points volontairement non modifiés

- Questions et logique pédagogique de la Boussole des valeurs professionnelles.
- Calcul des moyennes et cotations.
- Roue graphique principale.
- Module complémentaire Valeurs énergies.
- Textes métier et finalité de l'exercice.

## Tests réalisés dans l'environnement de préparation

- Compilation Python : OK (`python -m py_compile app.py`).
- Vérification de la présence du motif `timeout_inactivite` dans le code : OK.
- Vérification de l'ajout de `streamlit-autorefresh` dans les dépendances : OK.
- Vérification de la présence du formulaire contact et des mentions légales : OK.

## Tests à réaliser manuellement après déploiement Streamlit

- Test complet SMTP avec vrais Secrets Streamlit.
- Test réel d'inactivité : ouvrir une session, saisir quelques réponses, ne plus rien toucher pendant plus de 15 minutes, vérifier l'écran timeout et le JSON proposé.
- Import d'un ancien JSON v1.3 et vérification de la reprise sans perte d'historique.
- Génération des PDF avec pied de page.
