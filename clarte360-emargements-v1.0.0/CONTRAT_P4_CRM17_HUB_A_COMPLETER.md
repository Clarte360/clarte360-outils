# CONTRAT DE FRONTIERE - P4 / CRM17 / CONTRACTUALISATION / HUB

Version P4 RC1 du 09/10/2026. **Note de cadrage, PAS contrat API CRM17 deja implemente.**

## Proprietaires de donnees

| Objet | Propriete actuelle / cible | P4 |
|---|---|---|
| Action, NO_CLAR, statut, planning, beneficiaires, prescriptions | Gestion des Actions | Lecture contextuelle et autorisations |
| Contact CRM0 | GDA transitoire | Identite de rattachement du compte, non dupliquee |
| Client, Etablissement, hierarchie, prescripteur, fournisseur, contrat, facture | Gestion Clients n°17 (cible) | **Hors perimetre d'ecriture P4** |
| Comptes du portail Client, invitations, grants, partages | GDA | Proprietaire des droits operatoires sur action |
| Devis/conventions/contrats et signature documentaire commerciale | Contractualisation | Pas de second moteur ni exposition par defaut |
| Investigations, analyses, snapshots, resultats individuels d'outil | Chaque application outil | Pas de lecture Client automatique |

## Interfaces GDA -> CRM17 a figer quand CRM17 sera disponible

- ID Client canonique, ID entite et ID prescripteur stables, sans utiliser un nom/societe comme cle.
- Validation serveur du statut actif, du perimetre d'action, des rattachements et changements d'organisation; renouvellement/revocation des droits.
- API versionnee avec scopes, comportement degrade, idempotence, audit et correspondance NO_CLAR / action_id.
- Document commercial : autorisation explicite de remise, statut final/verrouille, proprietaire, identifiant origine, version, SHA-256 et horodatage. Aucun acces aux fichiers financiers via un simple lien sans controle CRM17.
- Tant que ces interfaces ne sont pas livrees par CRM17, la rubrique commerciale signale une disponibilite future et n'affiche pas d'objet financier fictif.

## Regles de lancement d'outils - non regressions / GO14

- Les connecteurs existants PIP RIASEC/NEO restent inchanges.
- La source de verite des actions, beneficiaires et prescriptions demeure GDA.
- Le futur lancement signe et les importations documentaires generiques exigeront des scopes explicites, les IDs stables, controle SHA-256, versions et journalisation.
- GO-14 Compétences & Projets : **NON OUVERT**. Aucune integration specifique P4.

## Securite recette

- Client A ne peut lire aucun document Client B, meme avec le meme NO_CLAR.
- Un contact CRM lie a une action n'obtient aucun compte ou grant automatiquement.
- Un document simplement sauvegarde ou publie n'est pas remis avant partage nominatif.
- Les reponses BC/coaching et preuves individuelles ne sont jamais disponibles via les acces Client P4.
- La révocation d'une action retire les partages correspondants, sans restauration implicite.
