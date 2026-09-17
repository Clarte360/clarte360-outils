# Audit validation des saisies — Roue des valeurs V2.8

Entrées contrôlées : identité bénéficiaire, email, consultant, date, JSON de reprise, nombre de valeurs (1–24), nom/définition/couleur des valeurs, cinq domaines de vie, période, exemples, cotes 0–10, sélection des valeurs énergies (3 max), cotation revisitée, commentaires, actions et points d'appui, destinataires email et identifiants Hub.

Règle métier préservée : une cote > 2/10 exige à la fois un exemple concret et une période identifiable. La validation est réappliquée au niveau métier avant import/export/transmission afin qu'un contournement de l'interface ne suffise pas.

Le JSON est limité à 2 Mo, UTF-8, structure contrôlée et compatible avec les JSON V2.7 conformes.
