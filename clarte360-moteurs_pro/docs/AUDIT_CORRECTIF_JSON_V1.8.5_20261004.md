# Audit et correctif JSON — Moteurs professionnels v1.8.5

Date : 2026-10-04

## Constat

La v1.8.4 possédait déjà un garde-fou plus robuste que Boussole/Roue : toute réponse validée invalidait le JSON préparé. Cependant, la barre latérale conservait encore une copie binaire figée dans `st.session_state.exit_json_bytes`.

Le bouton « Télécharger le JSON préparé » pouvait donc dépendre d'une ancienne photographie si une évolution future oubliait d'invalider `exit_json_ready`. Le callback de téléchargement recalculait aussi l'empreinte depuis l'état courant au lieu de lier explicitement la sauvegarde au contenu réellement rendu.

## Correctif v1.8.5

- suppression de `exit_json_bytes` comme source de téléchargement ;
- reconstruction du payload depuis l'état courant lors de chaque rendu du bouton ;
- conservation uniquement du préfixe de nom de fichier pour distinguer sauvegarde et sortie ;
- passage de l'empreinte exacte du contenu rendu au callback de téléchargement ;
- même liaison d'empreinte sur le JSON final et le JSON de timeout ;
- aucun changement de schéma JSON métier ;
- compatibilité des anciens JSON conservée.

## Scénarios de recette

1. Préparer un JSON, télécharger, modifier/valider une réponse, puis télécharger à nouveau sans utiliser une ancienne copie.
2. Déplacer un curseur sans le valider : le garde-fou doit rester actif même après téléchargement du dernier état validé.
3. Valider le curseur, télécharger, réimporter : la dernière réponse doit être présente.
4. Télécharger le JSON final puis le réimporter.
5. Laisser expirer une session, télécharger le JSON timeout puis le réimporter.
6. Importer un ancien JSON V1.8.0/V1.8.4 et poursuivre normalement.

## Déploiement

Avant production :
- compilation Python ;
- campagne `PYTHONPATH=. .venv/bin/python -m pytest -q` ;
- contrôle du service systemd ;
- recette métier réelle après redémarrage.
