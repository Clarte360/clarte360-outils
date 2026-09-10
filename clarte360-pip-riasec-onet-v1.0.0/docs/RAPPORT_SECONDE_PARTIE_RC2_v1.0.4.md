# Rapport court — Seconde partie PIP RIASEC RC2 v1.0.4

- Base cumulative : v1.0.3 RC1, elle-même dérivée de v1.0.2 VPS.
- Fonctionnel/méthodologique : scoring et 120 formulations source inchangés ; contextualisation V0.4 conservée.
- Mode PUBLIC : JSON/reprise conservés ; aucun score intermédiaire exporté.
- Mode ACCOMPAGNEMENT : entrée désormais exclusivement par jeton signé, persistance serveur automatique, outbox d'événements minimisés.
- Gestion des actions reste source de vérité de l'identité. Aucun compte ni mot de passe PIP n'est créé.
- Limite volontaire : Gestion des actions I8/I9 devra produire le jeton et consommer l'outbox ou fournir le transport du connecteur.
- Reprise accompagnée : un index de prescription permet de retrouver automatiquement la dernière passation du même bénéficiaire/action/prescription, sans fichier JSON utilisateur.
- Événement `TERMINE` : publié uniquement à la fin d'un parcours PIP seul ; un parcours PIP+O*NET reste `EN_COURS` après la fin du PIP.
