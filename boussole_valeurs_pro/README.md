# Clarté360 - Boussole des valeurs professionnelles

Application Streamlit propriétaire Clarté360 destinée à l'exploration des valeurs professionnelles dans le cadre du bilan de compétences, du coaching professionnel et de l'accompagnement des transitions.

## Version

- Application : V1.4-socle-clarte360
- Socle Clarté360 : v1.7
- Référence socle : Moteurs professionnels v1.7.0 référence

## Lancement local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Secrets Streamlit

Copier `.streamlit/secrets.example.toml` vers `.streamlit/secrets.toml` puis renseigner les accès SMTP réels.

## Points clés du socle

- Accueil JSON / nouvelle session.
- Identification bénéficiaire.
- Consentement RGPD obligatoire.
- Code d'accès par e-mail.
- JSON comme mémoire principale du bénéficiaire.
- Reprise JSON avec nouvelle session sans écrasement de l'historique.
- Timeout automatique après 15 minutes sans activité réelle.
- Bouton `Quitter et télécharger mon JSON`.
- Formulaire permanent `Contacter Clarté360`.
- Mentions légales et coordonnées officielles Clarté360.
- Exports JSON, CSV, PNG et PDF.

## Données

Aucune donnée n'est stockée sur un serveur Clarté360. Le fichier JSON appartient au bénéficiaire et constitue le support de sauvegarde et de reprise.
