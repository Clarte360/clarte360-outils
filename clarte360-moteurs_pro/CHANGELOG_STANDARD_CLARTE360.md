# Journal des modifications - Clarté360 Moteurs professionnels v1.8.0

## Version livrée
- Application : v1.8.0-socle-clarte360
- Socle Clarté360 : 1.8
- Base métier conservée : Moteurs professionnels v1.7.0 référence

## Modifications réalisées
- Harmonisation de la barre latérale selon le socle Clarté360 le plus récent :
  - avant l'entrée dans l'application : éléments institutionnels uniquement ;
  - après validation du code : navigation / état métier en haut, puis sauvegarde JSON, sortie JSON, Contact et RGPD.
- Suppression du bouton « Réinitialiser la session » dès l'entrée dans le cœur de l'application afin d'éviter toute perte accidentelle.
- Suppression de l'affichage direct de l'adresse contact@clarte360.com dans la barre latérale : le formulaire de contact devient le canal d'échange visible.
- Page RGPD enrichie avec l'onglet « Protection des données et traçabilité ».
- Ajout d'un bloc de traçabilité compatible avec la structure des sessions Moteurs : session en cours, nombre de sessions, temps cumulé, consentement RGPD et sauvegardes.
- Ajout d'un bouton de retour en haut des pages Contact et RGPD pendant la passation.
- Correction de la logique de retour : l'utilisateur peut revenir au questionnaire sans devoir quitter ni télécharger un JSON.
- Harmonisation du rapport PDF : logo Clarté360 centré en tête de rapport, pied de page institutionnel conservé.

## Non modifié
- Questions du questionnaire.
- Curseurs.
- Calculs métier.
- Scores.
- Libellés métier.
- Interprétations existantes.
- Données Excel source.

## Tests techniques réalisés
- Vérification de syntaxe Python par compilation.
- Vérification de présence des fichiers essentiels dans le ZIP.

## Tests à réaliser après déploiement Streamlit Cloud
- Envoi réel du code par SMTP avec les secrets Streamlit.
- Notification administrateur réelle.
- Formulaire contact réel.
- Timeout réel après 15 minutes sans activité.
- Téléchargement JSON après timeout.
- Génération d'un PDF complet depuis une passation réelle.
