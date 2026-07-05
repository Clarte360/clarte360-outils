# CHANGELOG - Standardisation Clarté360

## v1.7-socle-clarte360

Correction de standardisation stricte sur la référence **Clarté360 - Moteurs Professionnels v1.7.0**.

### Corrections principales
- Écran d'accueil repris au format standard Moteurs v1.7 : titre, question, deux boutons `Oui -> Importer mon fichier JSON` et `Non -> Commencer une nouvelle session`.
- Suppression de l'import JSON visible directement sur la page d'accueil : l'import passe désormais par l'écran standard de reprise.
- Barre latérale affichée dès l'accueil, avec les boutons institutionnels permanents `Contacter Clarté360`, `RGPD et mentions légales`, coordonnées, versions et réinitialisation.
- Boutons JSON de session conservés uniquement lorsque la session bénéficiaire est active : `Préparer mon JSON pour reprendre plus tard` et `Quitter et télécharger mon JSON`.
- Suppression de l'import JSON secondaire dans la barre latérale pour éviter un écart avec le standard et éviter une reprise sans écran dédié.
- Conservation de la protection `beforeunload` et du timeout `timeout_inactivite`.

### Logique métier
- Questions, calculs, scores, graphiques, rapports métier et philosophie pédagogique conservés.

### Tests réalisés
- Compilation Python : OK.

### Tests à faire après déploiement Streamlit
- Envoi SMTP réel du code bénéficiaire.
- Notification administrateur.
- Formulaire contact.
- Test réel timeout 15 minutes sans action.
- Test alerte navigateur avant fermeture.
