# Checklist de recette finale I9

## 1. Socle
- [ ] Application démarre sans erreur.
- [ ] Diagnostic I9 accessible à l'administrateur.
- [ ] Aucun secret n'est affiché.
- [ ] F5 conserve la session ADMINISTRATEUR.
- [ ] F5 conserve la session INTERVENANT.
- [ ] F5 conserve la session BÉNÉFICIAIRE.

## 2. Action / calendrier / import
- [ ] Création et modification d'action.
- [ ] Modalité contrôlée et lieu/précision séparés.
- [ ] Import date Excel numérique correctement converti.
- [ ] Créneau affiché par date + heure, sans ID technique.
- [ ] Ajout/report/suppression synchronise les fonctions dépendantes sans casser les autres modules.

## 3. Emails
- [ ] Journal des communications lisible.
- [ ] Envoi réel code participant.
- [ ] Planning/convocation réel.
- [ ] Activation espace bénéficiaire.
- [ ] Lien émargement.
- [ ] Contresignature intervenant.
- [ ] Qualité.

## 4. Émargement / contresignature
- [ ] Signature participant PC.
- [ ] Signature participant smartphone/tablette.
- [ ] Contresignature immédiate si tous statuts définitifs avant fin.
- [ ] À l'heure de fin, email intervenant si signatures/statuts manquants.
- [ ] Signature intervenant manuscrite responsive.
- [ ] PDF final intègre la contresignature.

## 5. Teams / Graph / Entra
- [ ] teams@clarte360.com reste organisateur technique central.
- [ ] Création automatique des réunions depuis le calendrier.
- [ ] Modification/report/suppression synchronisés.
- [ ] Bouton manuel uniquement comme secours administrateur.
- [ ] Prochaine réunion Teams affichée métier.
- [ ] Identité Microsoft intervenant recherchée avant toute création/invitation.
- [ ] Aucune donnée Graph/Meeting ID/Entra visible bénéficiaire.
- [ ] Présence Teams récupérée et jamais transformée automatiquement en émargement.
- [ ] Email Teams différent → rapprochement manuel explicite.

## 6. Hub / PIP
- [ ] Catalogue central visible et générique.
- [ ] Prescription PIP créée depuis bénéficiaire/action.
- [ ] Accès sécurisé PIP RC5 signé.
- [ ] CONSULTÉ / EN_COURS / TERMINÉ remontent idempotemment.
- [ ] Une panne PIP ne bloque pas calendrier/Teams/action.

## 7. Études
- [ ] Seules données consenties recherche sont visibles/exportables.
- [ ] Export CSV pseudonymisé.
- [ ] Export XLSX pseudonymisé.
- [ ] Aucun nom/prénom/email/téléphone dans l'export études.

## 8. CRM / Contractualisation
- [ ] Consentement marketing distinct du consentement recherche.
- [ ] Révocation marketing tracée.
- [ ] Conversion prospect → bénéficiaire sans doublon exact.
- [ ] Contexte Contractualisation préparé sans dupliquer son moteur PDF/juridique.

## 9. Robustesse
- [ ] Panne PDF n'empêche pas Calendrier/Teams.
- [ ] Panne Teams n'empêche pas Calendrier/action.
- [ ] Panne email n'empêche pas l'enregistrement métier.
- [ ] Aucun traceback Python/Streamlit dans les portails.
- [ ] Les incidents affichent une référence courte et sont journalisés côté audit.
