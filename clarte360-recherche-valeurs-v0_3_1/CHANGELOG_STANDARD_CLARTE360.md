# Journal applicatif RVC360

## 1.3.0-preproduction – 27 juillet 2026

- Synchronisation avec `RVC360_REFERENTIEL_OFFICIEL_V1.2`.
- Framework Clarté360 conservé sans modification de principe.
- Correction de la lecture vocale en boucle : une action utilisateur produit une seule lecture.
- Suppression du double déclenchement lié à `onvoiceschanged` et au temporisateur concurrent.
- Verrouillage du bouton pendant la lecture et annulation de la lecture précédente.
- Refonte du cycle d'enregistrement vocal : contrôle des octets, type de fichier adapté, transcription vide détectée, nouvelle prise réellement recréée.
- Ajout des actions `Transcrire`, `Réenregistrer` et `Réenregistrer ma réponse`.
- Audio non conservé ; seul le texte relu et validé peut être envoyé au moteur et exporté.
- Enregistreur affiché dans une colonne réduite et consigne explicite sur le carré d'arrêt.
- Renforcement du prompt métier : approfondissement de la situation présente, absence d'enchaînement négatif, variation des époques et contextes.
- Questions de secours diversifiées conformément au référentiel RVC360 V1.2.
- Référentiel Excel métier remplacé par la version officielle du ZIP RVC360 V1.2.

## 1.2.1-preproduction

- Correction de l'import `html` pour la carte des valeurs fondamentales.
- Réduction de la carte latérale et de l'avatar.
