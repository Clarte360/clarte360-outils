# Clarté360 - Préférences professionnelles

Version 1.9.0 - online avec code d'accès obligatoire.

## Fonctionnement

1. Le bénéficiaire renseigne prénom, nom et email.
2. L'application envoie un code d'accès au bénéficiaire.
3. L'application envoie aussi une notification à contact@clarte360.com indiquant que cette personne va réaliser le test Préférences professionnelles.
4. Le questionnaire ne démarre qu'après saisie du code correct.
5. À la question 60, le JSON final est généré.
6. Le JSON final est envoyé automatiquement à Clarté360 si les Secrets SMTP sont configurés.
7. Le bénéficiaire peut télécharger son JSON final et son rapport PDF.

## Secrets Streamlit Cloud

Dans Streamlit Cloud > Settings > Secrets, renseigner :

```toml
[email]
smtp_server = "ssl0.ovh.net"
smtp_port = 465
smtp_user = "contact@clarte360.com"
smtp_password = "VOTRE_MOT_DE_PASSE"
from_email = "contact@clarte360.com"
to_email = "contact@clarte360.com"
```

Ne jamais mettre le vrai mot de passe dans GitHub.

## Questionnaire

Le questionnaire est piloté par :

- `data/questions_preferences_professionnelles_v1.xlsx`
- `data/questions_preferences_professionnelles_v1.json`

Le bénéficiaire ne peut pas modifier le questionnaire.

## Reprise

Le bénéficiaire peut interrompre la passation et télécharger un JSON de sauvegarde. À la reprise, l'ordre initial des questions est conservé et l'application reprend à la première question non répondue.
