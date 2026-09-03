# Clarte360 – APS beneficiaire – V1.1.0

Application Streamlit destinee au beneficiaire apres son entretien prealable avec Clarte360.

## Positionnement

- Grille d'analyse partagee de situation (APS) de la phase preliminaire.
- Le beneficiaire remplit seul le formulaire de bout en bout.
- Aucun espace administrateur / consultant dans l'application.
- Le formulaire n'est ni un contrat ni une convention.
- Le prix a deja ete evoque lors de l'entretien ; les dispositions financieres seront reprises dans le document contractuel distinct.
- Certaines donnees sont structurees pour permettre une future reprise par une application « Convention BC ».

## Socle Framework integre

- identification beneficiaire ;
- envoi d'un code personnel a 6 chiffres par e-mail ;
- verification du code avant acces ;
- sauvegarde JSON telechargeable ;
- reprise a partir d'un JSON APS avec nouvelle authentification e-mail ;
- PDF APS complet ;
- transmission finale obligatoire du PDF + JSON a `contact@clarte360.com` ;
- confirmation e-mail au beneficiaire ;
- aucune configuration SMTP en dur dans le code.

## Streamlit Community Cloud

1. Deposer ce dossier dans GitHub.
2. Creer l'application Streamlit avec `app.py`.
3. Renseigner les Secrets depuis `.streamlit/secrets.example.toml`.
4. Tester l'envoi du code d'acces.
5. Tester un parcours complet jusqu'a la reception du PDF + JSON sur `contact@clarte360.com`.

## VPS Clarte360

Le meme code peut ensuite etre deploye sur le VPS. Les secrets restent centralises hors GitHub.


## Accès sécurisé / RGPD
Avant tout envoi de code d’accès, le bénéficiaire reçoit l’information RGPD et doit donner un consentement explicite, tracé selon le Framework Clarté360.
