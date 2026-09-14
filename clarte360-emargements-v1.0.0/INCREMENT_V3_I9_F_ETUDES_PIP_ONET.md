# I9-F — Études PIP/O*NET + exports pseudonymisés

Base : I9-E validée. Ce lot ajoute l'espace administratif de pilotage méthodologique prévu au CDC I9 §18 sans déplacer le moteur PIP/O*NET dans Gestion des actions.

## Réalisation
- Lecture en lecture seule des enregistrements `clarte360.pip.public-study.v1` produits par PIP RC5.
- Défense en profondeur : suppression récursive des champs d'identité avant traitement.
- Filtres parcours, timing PRE/POST, banque, statut et consentement recherche.
- Synthèse PIP seul / PIP+O*NET / PRE / POST / terminés / commencés / abandons observables.
- Qualité item sur réponses 1–5 : distribution, moyenne, dispersion, taux de réponse, indicateur descriptif de consensus.
- Comparaison PIP/O*NET uniquement lorsque les deux instruments sont présents ; PRE et POST restent séparés ; aucun recalcul/fusion de scores.
- Exports CSV et XLSX pseudonymisés, limités aux enregistrements avec consentement recherche.
- Journal additif de chaque export : utilisateur, date, filtres, schéma, finalité, format, volume.
- Aucun nom, prénom, email, téléphone, participant_id, beneficiary_id ou passation_id dans les exports.
- Les indicateurs de fatigue non présents dans le schéma RC5 ne sont pas inventés ; ils restent à enrichir lorsque PIP les émettra.

## Configuration future VPS
`pip_connector.study_dir` doit pointer vers le dossier persistant `public/study` de PIP. Aucun secret n'est nécessaire pour cette lecture locale protégée.
