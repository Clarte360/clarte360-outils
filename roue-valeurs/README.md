# Clarté360 - Roue des valeurs V2.2

## Corrections V2.2

- Ajout d'un accès bénéficiaire par code obligatoire.
- Envoi du code d'accès au bénéficiaire par email via SMTP Streamlit Secrets.
- Notification automatique au consultant Clarté360 lors de la génération d'un code.
- Ajout de l'adresse email et du consultant dans les données bénéficiaire.
- Information explicite du bénéficiaire sur l'utilisation du JSON dans le cadre de l'accompagnement.
- Ajout d'un bouton de transmission du JSON final au consultant Clarté360.
- Conservation des exports JSON / CSV / PNG / PDF existants.

## Streamlit Secrets

A configurer dans l'app Streamlit au format TOML :

```toml
[email]
smtp_server = "ssl0.ovh.net"
smtp_port = 465
smtp_user = "contact@clarte360.com"
smtp_password = "MOT_DE_PASSE"
from_email = "contact@clarte360.com"
to_email = "contact@clarte360.com"
```

## Déploiement

Remplacer le contenu du dépôt GitHub de l'application par les fichiers de cette version.

Commit conseillé :

`V2.2 - Ajout code d'accès et transmission JSON consultant`

## V2.3
- Correction lisibilite des boutons Clarte360.
- Ajout / suppression de valeurs directement depuis l'onglet Valeurs et domaines de vie.
- Ajout de l'espace consultant Valeurs energies, verrouille par code consultant, avec selection de 3 valeurs porteuses, cotation revisitee, actions ou points d'appui, seconde roue et export JSON/PDF.


## Version V2.6 - Socle Clarté360

Cette version ajoute le socle Clarté360 récent : accueil import/nouvelle session, RGPD, mentions légales, contact, JSON enrichi, traçabilité, gestion de session, timeout et rapport PDF institutionnel avec logo première page et footer Clarté360.


### Correction V2.6
La navigation depuis Contact / RGPD est alignée sur la Boussole : sélectionner une page métier dans la barre latérale ferme la page institutionnelle et revient dans l’application.
