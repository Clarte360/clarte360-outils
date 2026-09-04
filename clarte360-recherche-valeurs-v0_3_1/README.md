## Version actuelle

**V2.2.0-preproduction-4**

# Clarté360 – Recherche de mes valeurs

Application Streamlit de recherche, clarification et validation progressive des valeurs selon le référentiel RVC360 et le Framework Clarté360.

## Architecture métier actuelle

- le Module 3 permet d’examiner volontairement une hypothèse conservée ;
- le Module 4 recherche et formule des hypothèses sans jamais valider une valeur ;
- les hypothèses acceptées sont enregistrées exclusivement dans le **Panier Hypothèses** ;
- aucun transfert automatique vers « Valeurs à examiner » n’est autorisé ;
- les pistes à clarifier, les hypothèses et les valeurs à examiner sont synchronisées sans doublon actif.

## Correctif 9E1

Cette version corrige l’audit de la 9E :

- véritable raccourci **Ctrl + Entrée** sur les réponses écrites pour déclencher le même traitement que « Préparer et comparer » ;
- application immédiate de la distinction **texte identique / correction légère / reformulation réelle** lors de la première saisie écrite ;
- même distinction appliquée dès la première transcription vocale ;
- une correction purement grammaticale ou typographique n’est plus présentée comme une reformulation différente ;
- tests dédiés au raccourci clavier et au classement réel des différences ;
- suppression des mentions documentaires devenues incompatibles avec le Panier Hypothèses.

## Installation

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Secrets requis

Copier `.streamlit/secrets.example.toml` vers `.streamlit/secrets.toml`, puis renseigner la clé et le modèle OpenAI, le modèle de transcription, le code de déblocage, les paramètres SMTP et la durée maximale de session.

Ne jamais publier le fichier réel `secrets.toml`.

## Contrôles locaux

```bash
python -m py_compile app.py
python -m pytest -q
```

## Versions déclarées

- Application : **2.2.0-preproduction-4**
- Référentiel RVC360 : 2.1
- Framework déclaré : 4.0

## Correctif 9E2

- Le bénéficiaire peut toujours conserver sa formulation initiale, y compris pour le nom d’une valeur, à l’écrit comme à l’oral.
- Ctrl + Entrée est disponible sur tous les champs écrits. Il déclenche le bouton principal visible, avec ou sans comparaison Clarté360.
- Deux tests comportementaux ciblés vérifient ces règles.

## Évolutions 9E4

- Consignes adaptées au type de question : développement encouragé pour les questions ouvertes ; possibilité explicite de répondre « Je ne sais pas » ou « Je ne vois pas » seulement lorsqu’un mot ou une courte expression est attendu.
- Quatre orientations distinctes après la saisie et l’analyse d’un terme dans le Module 3 : poursuivre maintenant, conserver dans Valeurs à examiner, envoyer vers À explorer — Module 4, ou placer dans À revoir en séance.
- Transitions atomiques entre les paniers actifs, incluant désormais les pistes du Module 4 et le nettoyage des états de reprise.
- Résolution renforcée des pistes provenant d’anciennes sauvegardes : suppression par identifiant source et par alias afin d’empêcher la réapparition d’un ancien terme comme « Sécurité financière ».
- Présentation des modules restructurée : numéro du module, titre sur une ligne distincte, statut et alignement homogènes.

## Version 2.2.0-preproduction-4 — 4 septembre 2026

Cette version applique le référentiel conversationnel RVC360 V2.6 : qualité d'expression structurée (correction / reformulation / clarification / échec technique) et sélection multi-hypothèses dans le Module 4. Voir `CHANGELOG_V2.2.0.md`.


La preproduction-2 renforce spécifiquement la **proposition d’expression réellement réutilisable** : une simple suppression de tics de langage n’est plus suffisante si la formulation reste vague ou maladroite.
