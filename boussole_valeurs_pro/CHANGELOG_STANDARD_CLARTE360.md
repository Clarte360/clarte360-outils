# Clarté360 - Boussole des valeurs professionnelles
## Version V1.5-socle-clarte360

Mise à niveau finale à partir du prompt Clarté360 v3.0, avec reprise stricte du socle de référence Moteurs Professionnels v1.7.0 pour les composants non métier.

## Harmonisation socle

- Barre latérale renforcée avec les boutons permanents du socle :
  - Préparer mon JSON pour reprendre plus tard ;
  - Quitter et télécharger mon JSON ;
  - Contacter Clarté360 ;
  - RGPD et mentions légales ;
  - Réinitialiser la session.
- Ajout de la protection navigateur `beforeunload`, alignée sur Moteurs Professionnels v1.7.0 : alerte du navigateur lorsque l'utilisateur tente de quitter l'onglet sans avoir téléchargé son JSON.
- Maintien du timeout automatique par surveillance technique, avec passage à l'écran de timeout sans attendre un changement de page.
- Motif de fermeture standardisé : `timeout_inactivite`.
- RGPD, mentions légales et formulaire contact structurés selon le socle : Protection des données / Mentions légales / Nous contacter.
- Coordonnées officielles Clarté360 intégrées.
- JSON conservé comme mémoire unique du bénéficiaire.
- Structure de session et historique préservés à la reprise JSON.
- Pied de page institutionnel ajouté aux PDF lorsque techniquement possible.

## Logique métier conservée

Aucune modification volontaire des éléments métier :

- questions ;
- domaines ;
- cotations ;
- calculs ;
- graphiques ;
- roue ;
- Valeurs énergies ;
- interprétation pédagogique ;
- rapport PDF métier.

## Tests réalisés

- Compilation Python : OK.
- Vérification statique de la présence des boutons du socle : OK.
- Vérification statique de la présence de l'alerte navigateur `beforeunload` : OK.
- Vérification statique du motif `timeout_inactivite` : OK.
- Vérification absence de mot de passe SMTP dans le code : OK.

## Tests à réaliser après déploiement Streamlit

- Envoi réel du code bénéficiaire avec les vrais secrets SMTP.
- Notification administrateur réelle.
- Formulaire contact réel.
- Test réel de fermeture d'onglet : vérifier l'apparition de l'alerte navigateur.
- Test réel timeout : attendre plus de 15 minutes sans interaction et vérifier l'écran timeout + JSON + motif `timeout_inactivite`.
