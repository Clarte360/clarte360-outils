# Clarté360 - Compétences & Projets

Application Streamlit propriétaire Clarté360 destinée au bilan de compétences.

Version application : 1.3.0  
Socle : Clarté360 Socle v1.8

## Lancement local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Secrets Streamlit

Copier `.streamlit/secrets.example.toml` vers `.streamlit/secrets.toml` en local et renseigner les paramètres SMTP.
Ne jamais déposer le fichier `secrets.toml` dans GitHub.

## Données nécessaires

Les fichiers suivants doivent rester dans `/data` :

- `RefRomeXml.zip`
- `rome_riasec_clarte360.xlsx`
- `site_icon.png`

## Standard Clarté360

Cette version intègre le socle commun Clarté360 : accueil JSON/nouvelle session, RGPD, contact, mentions légales, gestion des sessions, temps cumulé, timeout, JSON de reprise et rapport PDF institutionnel.


## Contrôle timeout

Version 1.3.1 : le timeout automatique de 15 minutes distingue l’activité réelle du bénéficiaire et le rafraîchissement technique Streamlit.
