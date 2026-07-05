# CHANGELOG STANDARD CLARTÉ360

## v1.10.1-socle-clarte360 — Correction socle Préférences professionnelles

Corrections réalisées après audit de conformité au Prompt officiel Clarté360 v3.0 et au socle validé Moteurs v1.8.

### Barre latérale
- Suppression de l'affichage permanent du temps de session dans la barre latérale.
- Suppression du bouton « Réinitialiser la session » dès l'entrée dans le cœur métier.
- Réorganisation de la barre latérale : navigation métier, session, préparation JSON, sortie JSON, contact, RGPD, versions.
- Conservation du bouton « Réinitialiser la session » uniquement avant entrée dans le cœur de l'application.

### JSON / sauvegarde / sortie
- Mise en place d'une préparation JSON intermédiaire avant téléchargement.
- Le bouton « Préparer mon JSON pour reprendre plus tard » trace une sauvegarde sans fermer la session.
- Le bouton « Quitter et télécharger mon JSON » ferme proprement la session avec motif `sortie_utilisateur_par_bouton`.
- Ajout de l'historique des sauvegardes dans le JSON.
- Ajout de la fermeture de session, du motif de fermeture et de l'horodatage.

### Traçabilité / RGPD
- Ajout d'un bloc de traçabilité visible dans la page « RGPD et mentions légales ».
- Affichage du consentement, de l'identifiant de passation, de l'identifiant de session, du temps cumulé, de l'historique des sessions et de l'historique des sauvegardes.
- Enrichissement de la section RGPD du JSON avec la traçabilité de session.

### Temps / timeout
- Ajout de `streamlit-autorefresh` aux dépendances.
- Ajout du watchdog Streamlit pour permettre le déclenchement automatique du contrôle de timeout.
- Enregistrement du motif `timeout_inactivite` lors d'une expiration de session.

### Logique métier
- Aucune modification des questions, réponses, dimensions, scores, calculs, graphiques métier ou interprétations.
