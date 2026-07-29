# Journal des modifications - V2.1.3.5

## Base exclusive
Version construite exclusivement depuis `clarte360-recherche-valeurs-v2.1.3(2).zip`.

## Lot 1 - Appels IA
- Ajout d'un identifiant déterministe par demande.
- Ajout d'un registre technique minimal `ai_request_log`.
- Mise en cache de session des réponses réussies pour éviter un nouvel appel identique lors d'un rerun.
- Suppression des boucles de reprises imbriquées.
- Désactivation des retries automatiques du SDK (`max_retries=0`).
- Comptabilisation séparée de la transcription vocale.

## Lot 2 - Voix
- Empreinte SHA-256 de l'audio en mémoire de session.
- Une même donnée audio n'est transcrite qu'une seule fois.
- Affichage de `Transcription en cours...`.
- Conservation immédiate de la transcription avant le nettoyage.
- Suppression du changement de clé audio avant l'affichage du résultat.
- Conservation du résultat et affichage de l'erreur après rerun.

## Lot 3 - Ergonomie
- Conservation du composant unique de question ouverte.
- Ajout de la précision demandée à la première question de `Faisons connaissance`.
- La précision est intégrée au texte lu par le bouton vocal.

## Lot 4 - RGPD
- OpenAI est nommé explicitement.
- Distinction entre l'API OpenAI et le service grand public ChatGPT.
- Mention de l'absence d'entraînement par défaut des données API, sauf partage explicite.
- Précision prudente sur `store=False` et les journaux techniques/anti-abus.
- Version RGPD portée à `RGPD-Clarte360-RVC360-v2.1.2-2026-07`.

## Lot 5 - Tests
- Compilation Python réussie.
- 13 tests automatisés réussis.
- Contrôle statique des appels IA, des retries, du RGPD et de la question de présentation.
- Cache Python et cache pytest exclus du ZIP livré.
