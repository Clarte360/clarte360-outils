# Journal des modifications - Clarté360 Moteurs professionnels v1.8.0

## Version livrée
- Application : v1.8.0-socle-clarte360
- Socle Clarté360 : 1.8
- Base métier conservée : Moteurs professionnels v1.7.0 référence

## Modifications réalisées
- Harmonisation de la barre latérale selon le socle Clarté360 le plus récent :
  - avant l'entrée dans l'application : éléments institutionnels uniquement ;
  - après validation du code : navigation / état métier en haut, puis sauvegarde JSON, sortie JSON, Contact et RGPD.
- Suppression du bouton « Réinitialiser la session » dès l'entrée dans le cœur de l'application afin d'éviter toute perte accidentelle.
- Suppression de l'affichage direct de l'adresse contact@clarte360.com dans la barre latérale : le formulaire de contact devient le canal d'échange visible.
- Page RGPD enrichie avec l'onglet « Protection des données et traçabilité ».
- Ajout d'un bloc de traçabilité compatible avec la structure des sessions Moteurs : session en cours, nombre de sessions, temps cumulé, consentement RGPD et sauvegardes.
- Ajout d'un bouton de retour en haut des pages Contact et RGPD pendant la passation.
- Correction de la logique de retour : l'utilisateur peut revenir au questionnaire sans devoir quitter ni télécharger un JSON.
- Harmonisation du rapport PDF : logo Clarté360 centré en tête de rapport, pied de page institutionnel conservé.

## Non modifié
- Questions du questionnaire.
- Curseurs.
- Calculs métier.
- Scores.
- Libellés métier.
- Interprétations existantes.
- Données Excel source.

## Tests techniques réalisés
- Vérification de syntaxe Python par compilation.
- Vérification de présence des fichiers essentiels dans le ZIP.

## Tests à réaliser après déploiement Streamlit Cloud
- Envoi réel du code par SMTP avec les secrets Streamlit.
- Notification administrateur réelle.
- Formulaire contact réel.
- Timeout réel après 15 minutes sans activité.
- Téléchargement JSON après timeout.
- Génération d'un PDF complet depuis une passation réelle.

## 1.8.1 — Validation saisies / VPS / Hub ready
- validation métier renforcée et reprise JSON sécurisée ;
- compatibilité explicite des JSON 1.8.0 Streamlit Cloud ;
- préparation VPS et URL cible ;
- contrat I9-H1 admin/intervenant vers bénéficiaire ;
- questionnaire et algorithme de scoring inchangés.


## 1.8.2 — Garde-fou sortie / rafraîchissement
- remplacement du simple booléen de téléchargement par une empreinte de l'état métier ;
- F5, fermeture d'onglet et navigation protégés si le travail a changé depuis le dernier JSON ;
- téléchargement JSON = nouveau point de sauvegarde de référence ;
- toute nouvelle réponse validée réarme automatiquement la protection ;
- déplacement du curseur courant non encore validé détecté comme travail non sauvegardé ;
- import d'un JSON = état de référence sauvegardé ;
- traces techniques de session/heartbeat exclues de l'empreinte pour éviter les fausses alertes ;
- questionnaire, scoring et interprétations inchangés.

## V1.8.3 — Rapport moteurs enrichi

- Base conservée : V1.8.2 VALIDATION-SAISIES-VPS-HUB-READY-GARDE-FOU.
- Aucun changement du questionnaire, des curseurs, des calculs, du JSON métier ou du fichier Excel source.
- Ajout, uniquement dans la restitution bénéficiaire à l'écran et dans le rapport PDF téléchargeable, d'une définition développée pour chacun des 10 moteurs.
- Présentation des moteurs dans l'ordre décroissant des résultats.
- Pour chaque moteur : verbe, pourcentage obtenu, lecture obtenue, définition enrichie, puis lectures basse, moyenne et haute.
- Conservation de la précaution de lecture : outil déclaratif d'exploration, non psychométrique et non diagnostique.

## V1.8.4 — Correctif reprise JSON / continuité Streamlit Cloud → VPS

- Base : V1.8.3 réellement présente dans GitHub au 21/09/2026.
- Correction bloquante : `import_json_screen()` utilisait `active` sans le recevoir, provoquant `name 'active' is not defined`.
- La fonction reçoit désormais explicitement `active` depuis `main()`.
- Compatibilité maintenue avec les JSON V1.8.0 Streamlit Cloud : le JSON reste le support de continuité et évite une nouvelle validation de code lorsqu'il est valide.
- Aucun changement du questionnaire, des 60 curseurs, du scoring ni des définitions enrichies du rapport.
- Ajout de tests de non-régression sur l'import d'un JSON historique et sur le câblage de l'écran de reprise.
- `app_identity.json` passe en V1.8.4 et statut `production`.
- Exemple systemd corrigé pour refléter le déploiement VPS réel.


## V1.8.5 — Fiabilisation sauvegardes JSON

- suppression de la copie JSON figée `exit_json_bytes` comme source de téléchargement de la barre latérale ;
- « Préparer mon JSON » et « Quitter et télécharger mon JSON » n'enregistrent plus une ancienne photographie binaire réutilisable ;
- le JSON de la barre latérale est reconstruit depuis l'état courant à chaque rendu du bouton ;
- le téléchargement est lié à l'empreinte métier exacte contenue dans le fichier rendu ;
- les téléchargements JSON de résultats et de timeout utilisent le même principe d'empreinte ;
- le garde-fou conserve la détection d'un curseur déplacé mais non validé ;
- compatibilité des JSON historiques V1.8.0 à V1.8.4 conservée ;
- questionnaire, 60 curseurs, scoring, définitions et rapports métier inchangés.

## V1.8.6 — UX navigation / retour / audio — 05/10/2026
- Ajout du logo Clarté360 dans la barre latérale pendant la passation.
- Écran questionnaire compacté et hiérarchisé : progression, situation, propositions, curseur, navigation.
- Lecture vocale conservée et rendue plus compacte sans rerun Streamlit.
- Ajout du bouton `Question précédente` sans suppression des réponses validées.
- Une réponse déjà validée est retrouvée lors du retour sur la question et peut être modifiée puis revalidée.
- Le garde-fou tient compte des curseurs non validés déjà affichés même après navigation arrière.
- Aucun changement des 60 curseurs, du scoring, des restitutions, du JSON métier ou du rapport.
