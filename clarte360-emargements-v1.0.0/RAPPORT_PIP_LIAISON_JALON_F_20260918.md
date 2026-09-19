# CLARTÉ360 — Gestion des Actions — Liaison PIP — Jalon F

Date : 2026-09-18
Base : jalon E `PIP-LIAISON-E-RESUME-RESULTATS`.

## Objet
Archivage automatique côté Gestion des Actions du rapport professionnel PDF produit par PIP, en réutilisant strictement le système documentaire existant.

## Réalisation
- Table additive `prescription_documents` : liaison entre une prescription PIP et une `document_reference` existante.
- Service `archive_pip_report_pdf()` : contrôle prescription PIP, PDF uniquement, rattachement action/bénéficiaire/participant, stockage via `store_document()`, SHA-256, audit et idempotence.
- Un rapport identique rejoué retourne la référence existante ; un contenu différent ne peut pas remplacer silencieusement le rapport déjà lié.
- Le document est visible via les mécanismes existants : portail bénéficiaire et Documents de l'action pour l'intervenant autorisé.
- L'administrateur dispose en plus d'un téléchargement direct dans le bloc de résultat PIP.

## Limite volontaire
Le mode de transport sécurisé du PDF depuis l'application PIP (référence sécurisée, récupération serveur-à-serveur ou mécanisme final retenu) n'est pas figé dans ce jalon. Il sera raccordé au contrat PIP validé au jalon H. Aucun format externe incompatible n'est donc imposé ici.

## Non-régression
Aucune modification Calendar/Teams. Aucun changement du secret HMAC existant. Aucun programme PIP modifié.
