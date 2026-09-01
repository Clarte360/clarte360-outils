# Clarté360 — Émargements V1.0.0

Application Streamlit autonome pour créer des actions, gérer des participants et des créneaux, recueillir les signatures sur smartphone/ordinateur, automatiser les demandes et relances, générer les feuilles d'émargement/certificats et exporter une archive portable.

## Fonctions V1

1. Connexion administrateur + première mise en service.
2. Création/reprise d'une action.
3. INTRA / INTER / INDIVIDUEL.
4. Saisie manuelle et CSV participants.
5. Import `GESTION OF CLARTE360 EN COURS.xlsm` (onglets CONV ADM + STAGIAIRE).
6. Calendrier avec nombre illimité de dates/créneaux et duplication de journée.
7. Contrôle durée prévue / durée planifiée.
8. Liens individuels de signature + QR code de créneau.
9. Signature tactile/souris.
10. Tableau de suivi.
11. Envois/relances automatiques par `worker.py`.
12. PDF collectif et individuel.
13. Certificat de réalisation calculé sur les créneaux signés.
14. Piste d'audit et archive ZIP.
15. Export JSON portable pour migration vers un autre serveur.

## Données volontairement non importées

Le NIR / numéro de Sécurité sociale n'est **pas importé ni stocké** dans le module d'émargement : il n'est pas nécessaire à la preuve de présence et constitue une donnée à protection renforcée.

## Installation locale

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
streamlit run app.py
```

Au premier lancement, l'application demande la clé `setup_key` définie dans `secrets.toml`, puis crée le premier compte administrateur.

## Worker email

Dans un second terminal :

```bash
python worker.py
```

Le worker vérifie chaque minute les demandes/relances à envoyer. Il ne fait rien si `[smtp].enabled = false`.

## Déploiement VPS

Voir `DEPLOIEMENT_VPS.md` et les exemples systemd dans `systemd/`.

## Base de données

La V1 utilise SQLite (`data/clarte360_emargements.db`) en mode WAL : c'est volontairement simple, persistant et très facile à sauvegarder ou à déplacer sur un autre serveur. Une migration PostgreSQL pourra être faite plus tard si le volume ou la concurrence d'accès le justifie.
