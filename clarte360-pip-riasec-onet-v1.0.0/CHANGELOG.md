# Changelog

## 1.0.1-l1-vps — 2026-09-10
- Mise en conformité technique avec le FRAMEWORK VPS CLARTÉ360 V1.0.
- Aucun changement fonctionnel ou méthodologique PIP/RIASEC/O*NET.
- Dossier de production stable documenté: `clarte360-pip-riasec-onet-v1.0.0`.
- Ressources runtime versionnées déplacées de `data/` vers `resources/`.
- `data/` réservé aux données persistantes hors Git; temporaire par défaut sous `/tmp`.
- `.gitignore`, secrets d'exemple et configuration Streamlit renforcés.
- Documentation VPS/systemd et tests techniques de conformité ajoutés.


## 0.2.0-l1b — 2026-09-10
- Pipeline contrôlé tableur maître -> ressource runtime JSON versionnée.
- Intégration des 120 items pilotes sans réécriture.
- Validation automatique banque, IDs, dimensions, facettes, blocs et échelle.
- Moteur de questionnaire déterministe par session, mélange RIASEC dans les blocs.
- Interface de passation 1–5, navigation précédent/suivant, aucun feedback intermédiaire.
- Tests L1-B ajoutés.

## 0.1.0-l1a
- Socle et architecture initiale Clarté360.

## 0.3.0-l1c — L1-C
- Scoring déterministe RIASEC (moyennes, indices 0–100, égalités exactes, préparation code Holland).
- Complétude obligatoire avant résultat final.
- Sauvegarde/reprise métier schema `clarte360.pip.run.v1`.
- Parcours PIP seul / PIP puis O*NET 60 et verrou anti-influence.
- Structure versionnée du questionnaire fermé de ressenti.
- Tests L1-C scoring, parcours, persistance et non-régression.

## 1.0.0-l1 — L1-D — 2026-09-10
- Consolidation finale du Livrable 1 cumulatif A+B+C+D.
- Version applicative et libellés d'interface alignés sur L1-D.
- Audit banque runtime, parcours, verrou anti-influence, sauvegarde/reprise et absence de secrets.
- Ajout des tests de consolidation L1-D.
- Ajout de la checklist de recette utilisateur du Livrable 1.
