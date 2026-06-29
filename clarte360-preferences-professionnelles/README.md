# Clarté360 - Préférences professionnelles

Application Streamlit destinée au bénéficiaire.

## Lancement local

```bash
pip install -r requirements.txt
streamlit run app.py
```

En local, si les emails ne sont pas configurés, l'application affiche le code d'accès à l'écran pour les tests.

## Déploiement Streamlit Cloud

1. Déposer ce dossier sur GitHub.
2. Créer une application Streamlit Cloud en pointant vers `app.py`.
3. Dans Streamlit Cloud : `Settings > Secrets`, coller :

```toml
[email]
smtp_server = "ssl0.ovh.net"
smtp_port = 465
smtp_user = "contact@clarte360.com"
smtp_password = "REMPLACER_PAR_LE_MOT_DE_PASSE"
from_email = "contact@clarte360.com"
to_email = "contact@clarte360.com"
```

Le vrai mot de passe ne doit jamais être mis dans GitHub.

## Questionnaire

Le questionnaire officiel est dans :

`data/questions_preferences_professionnelles_v1.xlsx`

Il n'est pas modifiable depuis l'interface bénéficiaire. Pour publier une nouvelle version :

1. Modifier le fichier Excel dans `data/`.
2. Vérifier que les 60 questions actives sont conformes.
3. Commit/push sur GitHub.
4. Streamlit Cloud redéploiera l'application.

## Fonctionnement bénéficiaire

- Prénom, nom et email obligatoires.
- Un code d'accès est envoyé au bénéficiaire.
- Clarté360 reçoit une notification de génération du code.
- Le questionnaire se déroule sans retour arrière.
- Le bénéficiaire peut interrompre la passation et télécharger un JSON de sauvegarde.
- À la reprise, l'application reprend automatiquement à la première question non répondue.
- À la fin : génération du JSON final et du PDF.
- Si SMTP configuré : transmission automatique du JSON final à `contact@clarte360.com`.
