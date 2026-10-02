# INCRÉMENT INTERVENANTS RC2-2 — 01/10/2026

Version applicative : **3.0.0-INTERVENANTS-RC2-2**  
Statut : **candidate de recette**

## Objet

Corriger les anomalies observées en recette RC2-1 sur l’identité des candidats/intervenants, la suppression des dossiers de test, les réanalyses IA successives, les doublons de données structurées, l’interprétation du niveau IA 0/4 et la priorité de la validation humaine.

## 1. Navigation

- **Intervenants / Partenaires** devient une entrée de premier niveau du menu gauche.
- L’entrée est placée immédiatement au-dessus de **Paramètres**.
- Le module n’est plus hébergé comme un simple onglet de Paramètres.

## 2. Identité et profil professionnel

- Le **Prénom** et le **Nom** sont gérés séparément du **Titre professionnel**.
- Une identité historique peut être structurée sans recopier le nom dans le titre professionnel.
- La modification de l’identité met à jour le nom d’affichage et le pont legacy intervenant sans altérer le profil métier.

## 3. Réinitialisation administrateur du dossier professionnel

Une fonction de purge contrôlée est disponible depuis le dossier :

- phrase de confirmation obligatoire `REINITIALISER <professional_person_id>` ;
- vérification du mot de passe de l’administrateur connecté ;
- snapshot JSON préalable avec empreinte SHA-256 ;
- suppression des analyses IA, propositions, qualifications, preuves, expériences, diplômes/formations, certifications, langues, spécialités, CV générés et données professionnelles de profil ;
- conservation de l’identité, du statut CANDIDAT/INTERVENANT, du caractère actif/inactif, des documents déposés, des liaisons externes et des affectations.

## 4. Empreintes SHA-256 et réanalyses IA

- Les documents sont comparés par leur **empreinte SHA-256**.
- Même nom + même empreinte : doublon exact, pas de nouvelle version active.
- Même nom + empreinte différente : nouvelle version du document ; l’ancienne version est archivée.
- Lors d’une réanalyse, les documents inchangés ne sont pas retransmis à l’IA ; leurs faits déjà extraits sont réutilisés.
- Les documents nouveaux/modifiés sont analysés, puis les 26 prestations sont recalculées sur la base factuelle consolidée.
- Les documents retirés sont pris en compte afin de ne pas conserver artificiellement des faits qui ne seraient plus soutenus.

## 5. PDF scannés

- Un PDF disposant d’une couche texte exploitable continue d’être traité en texte afin de limiter les coûts.
- Un PDF sans texte exploitable est transmis à l’API Responses comme **input_file PDF**, permettant l’analyse visuelle des pages par un modèle multimodal compatible.

## 6. Anti-doublon des faits professionnels

Lors de l’acceptation des propositions IA :

- expérience identique : réutilisation/complément de la ligne existante ;
- diplôme/formation identique : réutilisation/complément ;
- certification/habilitation identique : réutilisation ;
- langues et spécialités : maintien de l’unicité existante.

Principe : **un fait professionnel = un enregistrement structuré**, même si plusieurs documents ou analyses le confirment.

## 7. Qualifications et lecture du 0/4

- L’étape **Retenir pour instruction** est supprimée : toutes les prestations actives sont directement disponibles dans Qualifications.
- Un niveau IA 0/4 ne signifie plus automatiquement « aucun rapprochement ».
- Si aucune preuve et aucun critère positif ne sont repérés : **Aucun élément repéré**.
- Si des preuves/critères existent mais que le niveau global reste à 0, notamment à cause d’un critère obligatoire : **Éléments repérés — niveau global bloqué**.
- Le prompt impose désormais à l’IA d’expliquer explicitement les critères bloquants.
- La confiance affichée est décrite comme **confiance dans l’analyse/proposition**, jamais comme un taux d’adéquation.

## 8. Priorité de la validation humaine

Dans la matrice Qualifications :

- **Décision humaine** apparaît avant les informations IA ;
- lorsqu’un niveau humain existe, il constitue la référence opérationnelle ;
- l’analyse IA reste visible comme aide et historique, sans pouvoir remplacer un verrou humain.

## 9. Suppression physique d’un dossier inutilisé

Les données appartenant au dossier ne sont plus considérées comme des dépendances externes : documents, IA, qualifications, expériences, diplômes, certifications, langues, spécialités, historique de candidature, etc. sont supprimés avec un dossier réellement inutilisé.

La suppression reste bloquée lorsqu’une utilisation métier externe existe, notamment : action, affectation action/planning, historique d’affectation, contresignature, qualité, communication, Teams ou liaison fournisseur.

L’interface affiche les dépendances bloquantes au lieu du seul message générique « dossier déjà utilisé ».

## 10. Sécurité Git / données persistantes

Le `.gitignore` est renforcé pour exclure notamment :

- `data/professional_documents/`
- `data/trainer_reports/`
- `data/final_bundles/`
- `data/import_sources/`

Les données réelles du VPS ne doivent jamais entrer dans le package Git.

## Critères de recette prioritaires

1. Corriger le prénom/nom de Christelle sans modifier son titre professionnel.
2. Supprimer physiquement un dossier de test jamais affecté, même s’il contient des analyses/documents internes.
3. Vérifier qu’un dossier affecté à une action reste non supprimable.
4. Purger un dossier avec le mot de passe administrateur et vérifier que l’intervenant reste actif et que ses documents restent présents.
5. Relancer une analyse sans nouveau document et vérifier qu’aucune réanalyse documentaire n’est proposée.
6. Ajouter une nouvelle version d’un fichier portant le même nom et vérifier que l’empreinte différente déclenche une analyse de la nouvelle version.
7. Relancer plusieurs analyses et vérifier l’absence de doublons d’expériences/diplômes/certifications.
8. Tester un diplôme PDF scanné sans couche texte.
9. Vérifier qu’un 0/4 avec preuves apparaît comme « Éléments repérés — niveau global bloqué ».
10. Valider humainement une prestation puis vérifier que la décision humaine est l’information principale dans Qualifications.
11. Vérifier la présence de **Intervenants / Partenaires** dans le menu gauche juste au-dessus de Paramètres.
