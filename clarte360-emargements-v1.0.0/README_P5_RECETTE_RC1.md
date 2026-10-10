# CLARTÉ360 - Gestion des Actions - P5 RECETTE RC1

Date : 09/10/2026. **CANDIDATE LOCALE - NON AUTORISÉE EN PRODUCTION.**

## Référence de départ

`clarte360-gestion-actions-v3.0.0-P4-ESPACE-CLIENT-RC1.zip`, SHA-256 : `b07633046dda25c4da85e672caa0d19e672927453e7a827035c220875578e702`.

## Changement correctif P5

Dans `client_portal.py`, les droits documentaires Client/DRH sont revérifiés à chaque opération contre la **nature courante** de l'action. Une action qui devient Bilan de compétences, coaching ou accompagnement individuel ne donne plus accès aux documents ou ZIP antérieurement partagés, même si le Client avait un ancien grant de téléchargement ou de dépôt. La liste des dépôts reçus est également bloquée dans ce cas. Les métadonnées de suivi autorisées restent consultables selon les grants historiques.

`tests/test_p5_final_receipt.py` teste 4 scénarios de requalification sur des identités et fichiers fictifs. La correction ne modifie pas le schéma SQLite ni les données existantes.

## Recette technique

- Tests historiques P0-P4 et P5 contrôlés depuis le ZIP final extrait à neuf ; journaux et matrice de recette classés dans `11 EMARGEMENTS/02 AUDITS ET RECETTES/P5/`.
- Migration test RC2 -> P5 sur une **base fictive**, conservation des enregistrements et intégrité SQLite ; elle NE remplace PAS une migration en environnement de préproduction sur une copie cohérente de la base VPS de 1,2 Go.
- Livraison ZIP code seul, sans bases, documents, signatures ni secrets d'exploitation.

## Portes non levées / interdiction de Go Production

1. E2E **Streamlit navigateur** sur les 4 rôles, dont mobile et droits négatifs ; Streamlit n'était pas disponible dans le conteneur de recette.
2. Recette authentifiée Teams/Microsoft Graph/Entra, SMTP, signatures/émargements, outils PIP/NEO et Contractualisation sur environnement isolé ; jamais sur la production sans mandat distinct.
3. CRM17 n'est pas encore interconnecté ; rester sur contacts CRM0 transitoires sans prétendre que le CRM autonome est opérationnel.
4. GO-14 Compétences & Projets reste fermé : socle générique et échanges bidirectionnels documentaires non encore testés de bout en bout.
5. Restauration **isolée** depuis PRA OneDrive `99 BACKUP VPS CLARTE360`, déchiffrement, cohérence SQLite en charge, preuve de retour arrière.
6. Arbitrage formel du cycle de destruction du dossier BC (Code du travail), durées de conservation RGPD et déontologie, contrôle Qualiopi applicable.

Le propriétaire détient exclusivement les opérations GitHub Desktop et le pouvoir d'autoriser toute installation VPS. **NE JAMAIS écraser le dossier `data/` du VPS.**
