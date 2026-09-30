# AUDIT TRANSVERSAL DES TABLEAUX — GESTION DES ACTIONS / ÉMARGEMENTS

Version de travail : RC2-1  
Date : 30 septembre 2026  
Périmètre : application complète, avec priorité immédiate au module Intervenants & partenaires.

## 1. Références appliquées

- CDC directeur Gestion des Intervenants & Partenaires V1.5.
- CDC correctifs parcours métier V1.1 : principe « un tableau de gestion doit être un point d'entrée opérationnel ».
- Framework Clarté360 V4.0 + Addendum V4.1.
- Framework VPS Clarté360 V1.3.
- Retours de recette RC2 du 30/09/2026.

## 2. Inventaire

L'audit statique de `app.py` recense **88 rendus de tableaux** (`st.dataframe`, `st.data_editor` ou équivalent) répartis dans **24 fonctions / écrans**.

L'audit distingue trois natures. Cette distinction est obligatoire : rendre « modifiable » un historique, une preuve d'audit ou une statistique serait une erreur de conception.

### A — Tableaux de restitution / preuve / historique : lecture seule volontaire

Restent en lecture seule lorsqu'ils restituent une trace ou une synthèse et qu'aucune donnée maître ne doit être modifiée depuis ce tableau :
- preuves Teams et durées constatées ;
- statistiques et réponses de questionnaires ;
- journaux d'audit ;
- historiques d'affectation, de qualification, de génération de CV et de versions ;
- diagnostics techniques ;
- aperçus d'import avant validation ;
- résultats d'études ;
- vues bénéficiaire/intervenant destinées à la consultation ;
- synthèses statistiques du pilotage qualité.

Ces tableaux ne sont **pas** considérés non conformes du seul fait qu'ils ne proposent pas « Modifier / Supprimer ».

### B — Tableaux de gestion déjà accompagnés d'actions métier

Les écrans suivants disposent déjà d'un mécanisme de sélection / modification / traitement / suppression ou inactivation à proximité du tableau :
- participants d'une action ;
- intervenants affectés et remplacements ;
- documents d'une action ;
- prescriptions d'outils ;
- campagnes qualité, événements qualité et CAPA ;
- signalements bénéficiaires / intervenants dans l'écran Qualité ;
- organismes ;
- agences / établissements ;
- profils d'import ;
- administrateurs ;
- personnes professionnelles ;
- candidats ;
- expériences, spécialités, diplômes, langues, certifications et documents professionnels ;
- familles de prestations ;
- prestations ;
- critères de compétence ;
- alertes de maintien de qualification.

Ils sont fonctionnels mais plusieurs utilisent encore le schéma « tableau + sélecteur sous le tableau ». Une évolution UX transverse ultérieure pourra normaliser l'ouverture directe par ligne sans changer le modèle de données.

### C — Écarts bloquants constatés dans la RC2_PROVISOIRE

1. **Preuves de qualification** : ajout possible mais aucune modification ni suppression.
   - RC2-1 : corrigé.
   - Modification d'une preuve, changement de critère/document/type, retrait/suppression avec historique.

2. **Prestations proposées par l'IA dans Documents** : bouton Accepter désactivé pour `SERVICE_CANDIDATE`.
   - RC2-1 : corrigé.
   - Une proposition peut être « Retenue pour instruction » ou « Rejetée / classée ».

3. **Résultat IA illisible** : affichage JSON brut et absence de vision exhaustive.
   - RC2-1 : corrigé.
   - Tableau synthétique de toutes les prestations actives, y compris « Aucun rapprochement ».

4. **Matrice Qualifications** : ne montrait quasiment que la validation humaine et masquait le bénéfice de l'IA.
   - RC2-1 : corrigé.
   - Ajout : lecture IA, niveau proposé, confiance, nombre de critères analysés et preuves IA.

5. **Pré-instruction IA trop coûteuse humainement** : obligation d'accepter critère et preuve un par un.
   - RC2-1 : corrigé.
   - Bouton d'acceptation groupée pour la prestation courante ; la validation du niveau global reste une décision humaine distincte.

6. **Remontées des intervenants dans le module Intervenants** : tableau doublon, sans traitement métier complet.
   - RC2-1 : corrigé.
   - Suppression du doublon ; l'écran Qualité redevient le point de gestion unique.

7. **Échec d'une nouvelle analyse laissant croire que le résultat ancien est courant**.
   - RC2-1 : corrigé.
   - L'interface avertit explicitement qu'une tentative a échoué et que les résultats visibles viennent de la dernière analyse réussie.

## 3. Règle transverse retenue

Tout tableau est classé comme :
- **RESTITUTION** : lecture seule justifiée ;
- **GESTION** : consultation + action(s) sur l'objet ;
- **HISTORIQUE / AUDIT** : immutable par conception, sauf mécanisme séparé de correction tracée.

Aucun nouveau tableau de GESTION ne doit être livré comme simple `st.dataframe` sans point d'entrée opérationnel.

## 4. Audit UX global restant après RC2-1

L'application comporte encore plusieurs écrans de gestion où les actions existent mais ne partent pas directement de la ligne du tableau. Ce n'est pas une perte fonctionnelle ou de données, mais l'UX reste hétérogène.

À normaliser dans un chantier transverse dédié :
- Tableau de bord Actions ;
- Organismes / Agences / Profils d'import / Administrateurs ;
- Participants / Planning ;
- Campagnes Qualité / CAPA / Signalements ;
- Documents ;
- Outils / prescriptions ;
- Intervenants / Candidats / Prestations / Critères.

Cible : composant commun « tableau de gestion Clarté360 » avec recherche, filtres, sélection de ligne, ouvrir, modifier, inactiver, supprimer lorsque permis, historique et garde-fous de dépendance.

## 5. Décision RC2-1

Les écarts bloquants de la recette Intervenants du 30/09 sont corrigés dans RC2-1.  
L'audit global des 88 tableaux est enregistré ; les tableaux de restitution restent volontairement en lecture seule, tandis que les tableaux de gestion non uniformisés sont identifiés pour le chantier UX transverse.
