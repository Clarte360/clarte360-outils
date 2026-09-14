# Audit validation des saisies — Boussole des valeurs v1.8.3

Périmètre : identité, contact, import JSON, valeurs, définitions, périodes, exemples, cotations 0–10, valeurs énergie, actions/points d'appui, identifiants Hub.

Renforcements : validation métier réutilisable dans `validation.py`, JSON UTF-8 limité à 2 Mo, structure bornée à 30 valeurs, trois valeurs énergie maximum, textes bornés, e-mail unique sans injection d'en-tête, téléphone plausible, scores finis et entiers, identifiants techniques sans traversée de chemin.

La logique métier de la Boussole (deux points d'appui, limitation de la cote sans exemple/période, roue, espace Valeurs énergies, PDF/CSV/PNG/JSON) n'est pas modifiée.
