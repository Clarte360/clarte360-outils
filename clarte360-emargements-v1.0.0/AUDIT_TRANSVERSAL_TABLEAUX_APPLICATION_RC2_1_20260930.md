# AUDIT TRANSVERSAL DES TABLEAUX — GESTION DES ACTIONS / ÉMARGEMENTS

Version : **3.0.0-INTERVENANTS-RC2-1**  
Date : **30 septembre 2026**  
Périmètre : **application complète** — administration, actions, qualité, CRM, contractualisation, intervenants, portails et historiques.

## 1. Références appliquées

- CDC directeur Gestion des Intervenants & Partenaires V1.5.
- CDC correctifs parcours métier V1.1.
- Framework Clarté360 et Addendum applicables.
- Framework VPS Clarté360 V1.3.
- Retours de recette RC2 du 30/09/2026.

Principe métier retenu : **un tableau de gestion doit être un point d'entrée opérationnel**.  
Un tableau de restitution, de preuve ou d'historique reste volontairement en lecture seule lorsque modifier la ligne détruirait la traçabilité.

## 2. Inventaire global

Après suppression d'un doublon de restitution, l'application contient **87 rendus de tableaux** (`st.dataframe`, `st.data_editor` ou équivalent).

Chaque tableau est classé dans l'une des trois familles suivantes :

### A — GESTION

Le tableau doit permettre, selon l'objet :
- ouvrir / étudier ;
- ajouter ;
- modifier ;
- activer / inactiver ;
- annuler / classer ;
- supprimer physiquement uniquement lorsque les dépendances le permettent ;
- conserver une trace lorsque l'objet participe déjà à l'historique métier.

### B — RESTITUTION / PREUVE

Lecture seule volontaire :
- preuves Teams ;
- état des présences et signatures ;
- résultats statistiques ;
- résultats d'études pseudonymisées ;
- synthèses de qualification ;
- tableaux de bord dérivés.

La donnée source se gère depuis son écran métier d'origine.

### C — HISTORIQUE / AUDIT

Lecture seule obligatoire :
- journaux d'envoi ;
- transmissions client ;
- journaux d'export ;
- historiques de versions ;
- audit technique et métier ;
- traces de qualification ;
- historique d'affectation.

Ces lignes ne sont jamais « supprimées pour corriger » : la correction passe par un nouvel événement traçable.

## 3. Corrections transverses réalisées dans RC2-1

### Actions / Tableau de bord
- Le tableau **Actions récentes** permet désormais d'ouvrir directement l'action choisie.
- Les actions restent modifiables, archivables et supprimables selon leurs règles métier.

### Participants / Planning / Intervenants
- Les tableaux disposent déjà de leurs commandes d'ajout, modification, absence, affectation, remplacement et suppression sous garde-fous.
- Les suppressions de participants et créneaux restent protégées par confirmation et mot de passe lorsque des preuves sont concernées.

### Outils Clarté360
- Les prescriptions peuvent être gérées et annulées selon leur propriétaire.
- Le catalogue permet ajout, activation/inactivation et modification.
- **Suppression physique d'un outil** ajoutée lorsqu'il n'existe aucune prescription ni autorisation d'action ; sinon l'inactivation est obligatoire.

### Qualité
- Les campagnes et événements qualité restent traçables.
- Les **actions d'amélioration** sont désormais modifiables et supprimables lorsqu'elles ont été saisies par erreur, avec audit.
- Les **CAPA** peuvent être placées au statut **ANNULEE** afin de corriger une saisie erronée sans détruire l'historique qualité.
- Les **signalements intervenant / bénéficiaire** peuvent être traités directement depuis l'action concernée.
- Le plan d'action général reste une vue consolidée ; la modification se fait dans la CAPA source.

### Documents
- Les documents actifs sont téléchargeables et retirables depuis leur tableau de gestion.
- Les journaux de transmissions client restent volontairement en lecture seule comme preuves d'envoi.

### Organismes
- Ajout et modification conservés.
- Activation/inactivation conservée.
- **Suppression physique ajoutée uniquement si aucune dépendance métier n'existe**.
- Les organismes utilisés doivent être inactivés afin de préserver l'historique.

### Agences / établissements
- Ajout, modification et activation/inactivation conservés.
- **Suppression physique ajoutée lorsqu'aucune action ni événement qualité ne dépend de l'agence**.

### Profils d'import
- Ajout et modification conservés.
- Activation/inactivation conservée.
- **Suppression de configuration ajoutée**, sans suppression du fichier source externe.

### Administrateurs
- Création, activation/désactivation et suppression déjà opérationnelles.

### CRM
- Les contacts disposent déjà d'actions directes d'ouverture et suppression.
- Notes et tâches sont modifiables/supprimables.
- Les liaisons avec les actions sont ajoutables et retirables.

### Contractualisation
- Les dossiers sont sélectionnables et modifiables.
- L'annulation reste un statut métier tracé ; pas de destruction silencieuse d'un dossier contractuel.

### Intervenants / Candidats / Qualifications
- Listes Intervenants et Candidats : ouvrir, inactiver/réactiver, suppression physique si zéro dépendance.
- Expériences, spécialités, diplômes, langues, certifications et documents : modification et suppression.
- Preuves de qualification : **modification et retrait/suppression avec traçabilité**.
- Prestations / familles / critères : CRUD avec protections de dépendances.
- Le tableau doublon « Remontées des intervenants » a été supprimé ; l'écran Qualité est le point de gestion unique.

## 4. Analyse IA — articulation avec les tableaux

RC2-1 impose :
- **100 % du dossier professionnel exploitable × 100 % des prestations actives** ;
- chaque prestation reçoit un résultat, y compris **Aucun rapprochement / niveau IA 0** ;
- aucune prestation ne disparaît silencieusement ;
- l'onglet Qualifications affiche la proposition IA, la confiance, les critères IA et les preuves IA ;
- acceptation groupée des critères/preuves possible pour une prestation ;
- la validation humaine du niveau global reste distincte et souveraine.

## 5. Garde-fou automatisé ajouté

Le test `test_all_application_tables_are_actionable_or_explicitly_read_only` parcourt le code de l'application.

Il échoue si un tableau n'a :
- ni commande métier à proximité ;
- ni justification explicite de lecture seule / historique / traçabilité.

Ce test transforme la règle « tableau vivant » en règle de non-régression.

## 6. État de sortie RC2-1

L'audit transversal est **clos pour la RC2-1** :
- tableaux de gestion : commandes métier présentes ;
- historiques / preuves : lecture seule justifiée ;
- suppressions physiques : uniquement lorsque juridiquement et techniquement compatibles avec les dépendances ;
- corrections d'erreur sur données historiques : annulation, classement ou nouvel événement plutôt que destruction de la trace.

La prochaine étape est la campagne complète de tests sur la version GitHub RC2-1 avant constitution du ZIP de recette.
