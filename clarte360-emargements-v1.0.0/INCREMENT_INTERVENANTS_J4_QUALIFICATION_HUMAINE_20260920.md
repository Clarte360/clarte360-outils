# CLARTE360 - Intervenants J4 - Qualification humaine / adequation competences-prestations

Date : 20/09/2026
Socle : J3.1 - CREATION DIRECTE

## Objet
Construire l'adequation manuelle entre une personne professionnelle et les prestations Clarte360, sans dependance a l'IA.

## Livraisons
- Matrice individuelle de toutes les prestations actives du referentiel.
- Qualification humaine globale par prestation sur l'echelle 0 a 4.
- Evaluation humaine critere par critere, avec niveau attendu et niveau constate.
- Verrou humain au niveau prestation et critere.
- Commentaires, auteur, date de validation et date de revision facultative.
- Preuves de qualification rattachees a la prestation et, si utile, a un critere.
- Possibilite de rattacher une preuve a un document deja present dans le dossier professionnel.
- Historique immuable des validations, reevaluations et ajouts de preuves.
- Fonction utilisable aussi bien sur un CANDIDAT que sur un INTERVENANT.

## Ergonomie
Ajout d'un onglet `Qualifications` directement dans le dossier professionnel 360.
A l'ouverture : tableau synthese des prestations, niveaux humains, nombre de criteres, nombre de preuves, date de revision et verrou humain.
Le detail d'une prestation montre ensuite les criteres, les preuves et la validation finale.

## Regles structurantes
- L'humain peut qualifier directement sans IA.
- Une qualification IA future ne doit jamais ecraser une valeur humaine verrouillee.
- Le niveau global ne se deduit pas automatiquement des criteres : l'administrateur garde la decision finale.
- Les criteres obligatoires sous leur niveau attendu restent visibles comme ecarts ; aucune decision automatique n'est prise.
- Les preuves sont tracees et sourcees ; aucune competence n'est inventee.

## Modele de donnees ajoute
- `person_service_qualifications`
- `qualification_criterion_assessments`
- `qualification_evidence`
- `qualification_history`

Les colonnes IA de la qualification globale sont preparees mais restent vides en J4. Leur alimentation releve du jalon IA ulterieur.
