# I9-H2.3 — Preuves Teams, signatures et ergonomie portails

- Microsoft Graph reste la source externe des attendance reports ; copie persistante sur le VPS.
- Rapprochement rapport/créneau limité à la fenêtre métier du créneau ±30 minutes.
- Conservation du JSON Graph brut et de son SHA-256 pour les nouveaux rapports/enregistrements.
- Vue administrateur : réunion réellement constatée, connexions, entrées/sorties, durée exacte, rapprochement, références techniques, PDF par réunion et PDF complet action.
- Vue intervenant : mêmes informations métier, sans exposer les identifiants Graph techniques.
- Vue bénéficiaire : durée de sa présence Teams uniquement lorsqu'un rapprochement a été confirmé/exact, consultation de sa feuille d'émargement et certificat définitif uniquement après clôture administrative.
- La clôture administrative n'annule pas les campagnes qualité à froid programmées.
- Blocage serveur des créneaux qui se chevauchent au sein d'une même action.
- Signature manuscrite : refus du canvas vide, des taps/points et micro-tracés ; IP et User-Agent réels récupérés derrière le reverse proxy lorsque disponibles.
- Les preuves historiques restent indépendantes par slot et ne sont jamais réécrites par une séance future.
