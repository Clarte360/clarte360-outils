# J10 — Fournisseurs / liaison Gestion Clients

Base : J9 UX opérationnelle.

## Principes
- Gestion Intervenants/GDA reste maître de `professional_person_id`.
- Gestion Clients reste maître de `supplier_id` et de l'identité économique fournisseur.
- Aucune raison sociale, SIREN/SIRET, IBAN ou donnée économique fournisseur n'est dupliquée dans le dossier professionnel.
- La liaison personne ↔ fournisseur est historisée localement et synchronisable via le contrat J8.1 de Gestion Clients.
- Un intervenant interne peut rester sans fournisseur ; un changement de structure conserve l'historique.

## Livré
- table additive `professional_supplier_links` ;
- création/changement/fin de liaison historisée ;
- `GestionClientsSupplierGateway` vers `/api/v1/suppliers/{supplier_id}/professional-links` et projection `/360` ;
- mode dégradé : une indisponibilité CRM ne détruit pas la liaison locale et laisse un statut ERREUR traçable ;
- bloc UX dans `Activité & conformité` ;
- maintien temporaire de `professional_persons.supplier_id` comme projection de compatibilité, sans en faire une source maître.
