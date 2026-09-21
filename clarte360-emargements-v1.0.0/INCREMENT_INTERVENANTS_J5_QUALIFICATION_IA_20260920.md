# CLARTÉ360 — Intervenants — J5 Qualification IA assistée

Date : 20/09/2026
Socle : J4 Qualification humaine

## Objet
Ajout d'une couche IA facultative d'assistance à l'adéquation compétences / prestations, sans décision automatique.

## Référence technique IA
Le mécanisme de secrets et d'appel a été aligné sur l'application officielle « Recherche de mes valeurs » : section `[openai]`, clés `api_key` et `model`, lecture via les secrets Streamlit/VPS, aucun secret embarqué dans le code ou le ZIP.

## Réalisé
- `QualificationAIGateway` isolé du métier et du fournisseur.
- API OpenAI Responses avec sortie JSON structurée.
- Prompt versionné `qualification_intervenant_v1_20260920`.
- Proposition IA : niveau 0–4, confiance, justification, preuves factuelles repérées, points manquants, propositions par critère.
- Analyse possible sur données structurées du dossier 360 et texte extrait des PDF/DOCX/TXT/MD/CSV explicitement sélectionnés.
- Confirmation explicite avant envoi des documents à l'IA.
- Minimisation : coordonnées de contact non transmises dans le payload métier ; chemins serveur retirés avant appel.
- Historisation des runs IA : provider, modèle, prompt, hash de requête, résultat, tokens et auteur.
- Séparation stricte `ai_*` / `human_*`.
- Une validation humaine verrouillée n'est jamais écrasée, y compris lors d'une réanalyse ultérieure.
- Mode manuel J4 totalement fonctionnel si l'IA est absente ou indisponible.

## Ergonomie
Dans l'onglet Qualifications, pour la prestation choisie : sélection des documents à analyser, confirmation, bouton d'analyse, puis affichage séparé de la proposition IA, confiance, justification, preuves et points manquants. La validation humaine reste dans son bloc distinct.

## Non réalisé / jalons ultérieurs
- Aucun automatisme d'affectation à une action.
- Aucune décision automatique candidat/intervenant.
- Aucun raccordement Gestion Clients.
- Aucun déploiement VPS dans ce jalon.
