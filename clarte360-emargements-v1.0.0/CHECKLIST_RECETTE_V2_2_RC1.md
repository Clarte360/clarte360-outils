# CHECKLIST RECETTE MÉTIER — V2.2-RC1

## Avant recette
- [ ] `git pull origin main` terminé sans conflit.
- [ ] `.venv/bin/pip install -r requirements.txt` terminé.
- [ ] `.venv/bin/python -m pytest -q` affiche 75 tests réussis.
- [ ] Si un seul test échoue : STOP, ne pas redémarrer les services.
- [ ] Les deux services sont `active (running)` après redémarrage.

## Administration
- [ ] Aucun affichage DeltaGenerator / Python / objet Streamlit.
- [ ] Import Excel conservé entre plusieurs actions.
- [ ] Contacts qualité et mise en place repris depuis l'import.
- [ ] Action ACTIVE toujours modifiable.
- [ ] Reports, rattrapages et absences toujours opérationnels.

## Intervenant
- [ ] Invitation reçue et création du mot de passe.
- [ ] Mot de passe oublié testé.
- [ ] Seules les actions affectées sont visibles.
- [ ] Calendrier complet et prochaine séance visibles.
- [ ] QR, présences, absences, rattrapages et contresignature fonctionnent.
- [ ] Code personnel du stagiaire visible uniquement pour ses propres actions.
- [ ] Renvoi du code par email journalisé.
- [ ] Signalement / incident / document vers administration fonctionnel.

## Bénéficiaire
- [ ] Création d'espace facultative et décochée par défaut.
- [ ] Rapprochement Nom + Prénom + date de naissance sans fusion automatique.
- [ ] Changement d'email conserve le même bénéficiaire et son historique.
- [ ] Planning, documents, questionnaires et ZIP accessibles.

## Documents
- [ ] Dépôt par numéro d'action.
- [ ] Même contenu sous deux noms = une seule copie physique SHA-256.
- [ ] Retrait d'une référence ne détruit pas le fichier s'il est encore référencé.
- [ ] Journal et compteur de stockage cohérents.

## Fin d'action
- [ ] Clôture impossible si dossier incomplet.
- [ ] ZIP final généré au format `AAMMJJ NO_ACTION DOCS STAGIAIRES.zip`.
- [ ] Sous-dossier par stagiaire en collectif.
- [ ] Feuille, certificat et HOT PDF présents lorsque disponibles.
- [ ] Envoi client réel reçu avec ZIP joint et mail explicatif.
- [ ] Transmission visible dans le journal.

## Qualité
- [ ] HOT / COLD / intervenant toujours déclenchés selon paramétrage.
- [ ] PDF professionnel téléchargeable après réponse.
- [ ] COLD est envoyé séparément après complétion.
- [ ] NPS, satisfaction, rubriques, difficultés, réclamations et améliorations lisibles dans le pilotage.

## Portail après 12 mois
- [ ] Avertissement envoyé avant purge.
- [ ] Le mail permet de revenir au portail pour télécharger le ZIP.
- [ ] Aucune purge avant le délai d'avertissement.
- [ ] Une nouvelle action empêche la purge.
- [ ] Les archives réglementaires internes sont préservées.
