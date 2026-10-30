# GO24 — Résultats, synthèse, clôture et suivi (état de la source RC4)

**Candidate de travail au relevé courant :** `0.4.26-go26-work` (travail local; jalon GO24 non validé)  
**État :** fonctions locales construites et testées ; jalon non validé, aucune recette navigateur/VPS ou métier effectuée.

## Fonctions présentes

- Plan d’action versionné de 1 à 12 actions, lié au projet prioritaire publié ; brouillon privé, publication explicite et retour du bénéficiaire par version.
- Résultats détaillés par rubriques : parcours, savoirs, projet, conditions, points de vigilance, formation/certification et obligation de diplôme. Toute obligation indiquée doit comporter une source officielle et une date.
- Publication à la relecture du bénéficiaire, qui peut confirmer ou demander une correction commentée ; versions et retours sont historisés.
- Synthèse finale distincte des résultats détaillés ; sa publication attend la confirmation des résultats, et sa finalisation attend une confirmation explicite du bénéficiaire.
- Préparation du suivi autour de six mois ; clôture bloquée tant que plan publié, résultats confirmés, synthèse finalisée et suivi préparé ne sont pas réunis. Le bénéficiaire peut transmettre son point de situation à partir de la date prévue.
- Contrôle des rôles et scopes, cloisonnement par dossier, événements d’audit minimisés et validations versionnées.

## Limites constatées

- Les PDF du plan confirmé, des résultats confirmés et de la synthèse finalisée sont maintenant générés à la demande. Le binaire est envoyé à GDA sur HTTPS, sans copie durable dans le stockage C&P; le reçu idempotent est conservé côté C&P. Le format Word reste à faire.
- Le choix de traitement documentaire à la clôture est enregistré dans l’événement d’audit ; cette version ne supprime ni n’archive aucun document dans GDA.
- Le rappel externe de suivi et l’archivage/destruction des documents à la clôture ne sont pas raccordés. La remise des livrables est codée, mais reste à tester contre le patch GDA.
- Les services API réels, l’expérience de navigateur sur le VPS, la recette avec un accompagnateur et un bénéficiaire d’essai restent à effectuer.

## Contrôles locaux disponibles

La suite automatise le parcours plan → résultats → confirmation → synthèse → confirmation → finalisation → clôture → retour de suivi, ainsi que les préconditions et l’obligation de source officielle. Ces tests techniques ne valent pas recette fonctionnelle ni validation de GO24.

## Étapes requises avant une recette réelle

1. Vérifier visuellement les PDF générés et tester leur remise/réception dans l’espace GDA avec le patch actif.
2. Brancher les documents du dossier par référence stable, sans copie binaire C&P ; la candidate exige le lien manuel par l’accompagnateur.
3. Vérifier les parcours et la lisibilité avec des comptes/acteurs d’essai puis sur le navigateur et l’environnement VPS visés.
4. Tester les opérations Hub/GDA et API réelles ; distinguer tout échec de service d’un constat métier.
5. Constituer l’archive de recette seulement quand les jalons préalables et le kit d’essai sont prêts.
