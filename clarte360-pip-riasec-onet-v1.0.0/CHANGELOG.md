# Changelog

## 1.0.5-l1-vps — RC3
- Corrige les tests de sécurité VPS afin qu'ils n'ouvrent jamais `.streamlit/secrets.toml` lorsqu'il s'agit du lien symbolique vers le coffre central `/opt/clarte360/secrets/secrets.toml`.
- Le contrôle continue d'inspecter tous les fichiers réellement versionnés du projet.
- Aucun changement fonctionnel, méthodologique, RIASEC, O*NET ou de scoring.
- Ajout d'un test de non-régression sur le comportement attendu avec un lien symbolique de secrets.

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

## 1.0.3-l1-vps — 2026-09-10 — correctif recette réelle L1
- Branding Clarté360 visible avec logo officiel de l'application Gestion des actions.
- Sauvegarde JSON accessible pendant toute la passation et reprise depuis l'accueil.
- Fin de parcours PIP seul : restitution minimale des six indices, code Holland seulement si non ambigu, questionnaire fermé de ressenti, sauvegarde finale.
- Ajout d'un exemple concret séparé pour chacun des 120 items, issu du tableur maître V0.4 de contextualisation ; formulations source et scoring inchangés.
- Le mode accompagné reste préparé mais son authentification/prescription doit être fournie par le connecteur Gestion des actions ; aucun second compte PIP n'est créé.

## 1.0.4-l1-vps — 2026-09-10 — RC2 seconde partie
- Préparation réelle du mode ACCOMPAGNEMENT sans créer de compte PIP parallèle.
- Suppression du scaffold par identifiants URL libres : l'entrée accompagnée exige désormais un jeton HMAC signé et expirant.
- Ajout du contrat de jeton commun Gestion des actions ↔ PIP, sans dépendance externe.
- Ajout d'une persistance serveur atomique des passations accompagnées sous `data/accompanied_runs/`.
- Ajout d'une outbox locale d'événements minimisés `CONSULTE / EN_COURS / TERMINE`, prête pour le transport futur vers Gestion des actions.
- Le mode PUBLIC reste étanche et refuse tout identifiant Clarté360 injecté dans l'URL.
- Export JSON public renforcé : aucun scoring intermédiaire n'est exporté avant complétude du PIP.
- Sauvegarde JSON visible uniquement en PUBLIC ; en ACCOMPAGNEMENT la sauvegarde est automatique côté serveur.
