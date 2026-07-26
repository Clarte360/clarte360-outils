# Clarte360 - Recherche de mes valeurs V0.3.1

Application Streamlit complete avec moteur IA RVC360 contraint par le referentiel comportemental V1.1.

## Installation

1. Installer les dependances : `pip install -r requirements.txt`
2. Copier `.streamlit/secrets.example.toml` vers `.streamlit/secrets.toml`
3. Renseigner la cle OpenAI et les parametres SMTP.
4. Lancer : `streamlit run app.py`

## Mode local

Le code maitre local n'est accepte que si la variable d'environnement `CLARTE360_LOCAL=1` est active. Le fichier `.bat` fourni active ce mode uniquement sur le poste de test.

## Architecture IA niveau 2

- preselection locale d'un sous-ensemble du referentiel ;
- appel OpenAI avec sortie JSON structuree ;
- filtrage strict des mots hors referentiel ;
- controle lexical anti-interpretation avant affichage ;
- preuve textuelle obligatoire pour chaque hypothese ;
- validation exclusivement humaine.
