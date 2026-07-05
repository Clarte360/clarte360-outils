# Clarte360 - Moteurs professionnels v1.7.0 Reference

## Statut
Version candidate de reference pour le Socle Clarte360.

## Corrections majeures
- Remplacement du timeout dependant uniquement de `st.fragment` par un watchdog plus robuste base en priorite sur `streamlit-autorefresh`.
- Controle automatique toutes les 10 secondes, meme sans clic utilisateur.
- Fermeture apres 15 minutes sans activite utilisateur explicite.
- Motif de fermeture standardise : `timeout_inactivite`.
- Separation nette entre :
  - battement technique automatique ;
  - activite reelle du beneficiaire.
- Les reruns automatiques ne prolongent plus artificiellement la session.

## Donnees conservees dans le JSON
- Historique des sessions.
- Debut, derniere activite, dernier battement, fin.
- Duree de session.
- Duree totale cumulee.
- Motif de fermeture.
- Evenements de sauvegarde.

## Socle Clarte360 conserve
- Accueil commun.
- Reprise JSON.
- RGPD et mentions legales.
- Formulaire Contacter Clarte360.
- Notifications e-mail.
- Export JSON.
- Pied de page Clarte360 dans les PDF.

## Point a tester avant gel definitif
- Laisser l'application ouverte sans action pendant plus de 15 minutes.
- Verifier l'apparition de l'ecran de timeout.
- Telecharger le JSON de reprise.
- Verifier que la derniere session porte le motif `timeout_inactivite`.
