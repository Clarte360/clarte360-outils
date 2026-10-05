# RC2-2-2 — P6 CV / finition — 02/10/2026

Base : RC2-2-2-P5.

## Réalisé
- CV interne et client conservés comme deux audiences distinctes.
- Empreinte déterministe des données sources réellement utilisées par chaque audience (`source_sha256`).
- État métier : `CV jamais généré`, `CV à jour`, `CV à régénérer` lorsque les données sources publiables ont changé.
- Les changements purement internes ne rendent pas le CV client obsolète.
- Les propositions IA sans validation humaine restent exclues du CV client ; une qualification humaine modifie bien l'empreinte source.
- Anti-doublon : une génération strictement identique, sur des sources identiques, ne crée pas une nouvelle fausse version.
- Historique rendu plus lisible : date formatée dans le fuseau applicatif, audience lisible, version, fichier et auteur.
- Migration additive de `professional_cv_generations.source_sha256`; les anciennes générations restent conservées et sont signalées à régénérer une fois faute d'empreinte source historique.

## Non-régressions
Aucune modification PIP/IPIP, worker, signatures, planning, Teams, documents ou règles d'affectation.
Aucun déploiement GitHub/VPS.
