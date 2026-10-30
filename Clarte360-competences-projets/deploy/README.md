# D5 — déploiement web VPS

Ce dossier contient l’application web D5 `Clarté360 — Compétences & Projets`. Le service VPS doit lancer le point d’entrée Python `app.py`. Ce README ne constitue ni un lanceur Windows ni une procédure de démonstration locale.

La version suivie est `0.4.30-go30-dual-candidate`. Elle est destinée au VPS Clarté360, avec raccordement à Gestion des Actions par CP_V1. Elle n’est pas encore déployée ni validée en conditions réelles.

Pour la mise en service, suivre le document **FW VPS** déjà utilisé pour Clarté360 et `docs/DEPLOIEMENT_GO30_CANDIDAT.md`. Il définit la configuration VPS, le service, les secrets, le DNS, HTTPS, les vérifications et le retour arrière. Adresse prévue : `https://competences-projets.clarte360.com`.

Ne jamais placer les secrets dans GitHub. Ne pas considérer les tests locaux ou automatisés comme une preuve de connexion réelle à Gestion des Actions, France Travail ou OpenAI.
