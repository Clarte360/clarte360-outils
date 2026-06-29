# Clarte360 - Roue des valeurs V1.1

Application Streamlit locale pour aider un beneficiaire ou un coache a construire sa roue des valeurs, sans interpretation automatique.

## Installation

Si les dependances ont deja ete installees une fois, il n'est pas necessaire de relancer cette commande.

```bash
pip install -r requirements.txt
```

## Lancement

Double-cliquer sur :

```text
lancer_roue_valeurs.bat
```

ou lancer manuellement :

```bash
python -m streamlit run app.py
```

## Donnees demandees

- Prenom du beneficiaire
- Nom du beneficiaire
- Date de realisation automatique, modifiable si besoin

Le mail n'est pas demande en V1.1, car il n'est pas utile pour construire la roue et limite les donnees personnelles collectees.

## Fonctionnalites

- Creation d'un questionnaire vierge
- Import d'un JSON existant pour modifier ou dupliquer une roue
- Nombre de valeurs libre
- Couleur personnalisable par valeur
- 5 domaines de vie : Personnel, Travail, Famille, Social, Couple / intimite
- Action ou reaction concrete obligatoire pour justifier la cotation
- Si aucun exemple concret n'est donne, la cote maximale recommande est 2/10
- Une valeur peut etre cotee a 0 et ne sera alors pas coloriee sur la roue
- Export JSON, CSV, PNG et PDF

## Important

Le lien `localhost:8501` fonctionne uniquement sur l'ordinateur qui lance l'application.
Pour une version permanente accessible a distance, il faudra deployer l'application sur un hebergement type Streamlit Cloud, OVH, Render ou serveur Clarte360.
