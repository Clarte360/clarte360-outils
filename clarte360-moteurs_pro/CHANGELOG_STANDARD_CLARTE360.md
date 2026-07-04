# Journal des modifications – Clarté360 Moteurs professionnels

Version livrée : 1.4.0-standard-clarte360
Date : 04/07/2026

## Audit synthétique

### ✅ Compatible
- Application Streamlit monofichier simple, adaptée à Streamlit Cloud.
- Données métier centralisées dans un fichier Excel `data/moteurs_professionnels_curseurs_v0_1.xlsx`.
- Logique pédagogique conservée : 60 curseurs actifs, positionnement gauche/droite, calculs par moteurs, résultats en pourcentage, interprétation par niveaux.
- Exports existants conservés : JSON, PDF, graphique barres, radar.
- Charte visuelle Clarté360 déjà présente : logo, vert canard `#008080`, encadrés, cartes, curseur sans valeur numérique visible.
- Dépendances simples et compatibles Streamlit Cloud : Streamlit, pandas, openpyxl, matplotlib, reportlab.

### ⚠️ À modifier / harmonisé
- Ajout d’un écran d’accueil commun avant toute autre page.
- Ajout de l’import JSON dès l’accueil.
- Reprise JSON créant une nouvelle session de connexion, avec compteur de temps remis à zéro pour la nouvelle session.
- Conservation des anciennes sessions dans le JSON et recalcul du temps cumulé.
- Ajout d’un bloc/page RGPD avec consentement obligatoire avant génération du code.
- Enregistrement dans le JSON du consentement, date, heure et version du texte RGPD.
- Ajout d’un historique de génération/régénération du code d’accès.
- Ajout du bouton : « Je n'ai pas reçu mon code → Générer un nouveau code ».
- Ajout du journal des sessions : identifiant unique, début, dernière activité, fin, durée, motif de fermeture, version application, fuseau horaire disponible.
- Ajout de la limitation de durée de session et de l’écran de téléchargement JSON en cas d’expiration.
- Renforcement du message RGPD dans l’e-mail de code.

### ❌ Points sensibles restant à surveiller
- L’envoi e-mail dépend toujours de la configuration SMTP dans les secrets Streamlit.
- Le fuseau horaire exact du navigateur n’est pas disponible côté serveur Streamlit ; la valeur conservée indique cette limite.
- La déconnexion automatique est contrôlée lors des interactions/réexécutions Streamlit ; un arrêt navigateur brutal ne déclenche pas toujours une fermeture explicite côté serveur.
- Le fichier Excel doit conserver ses colonnes actuelles, notamment les colonnes obligatoires des curseurs.

## Corrections et harmonisations apportées
- Version application passée à `1.4.0-standard-clarte360`.
- Intégration du socle Standard Clarté360 sans modification des calculs ni de la philosophie métier.
- Maintien du logo et des couleurs existantes.
- Maintien de la logique de génération de code à 6 chiffres.
- Maintien des exports PDF et JSON.
- Maintien des graphiques existants.
- Ajout d’une structure JSON enrichie : `sessions`, `temps_total_cumule_secondes`, `rgpd_acceptance`, `access_history`, `passation_root_id`.
- Import des anciens JSON rendu compatible avec les anciennes clés existantes.

## Fichiers principaux modifiés
- `app.py`
- Ajout : `CHANGELOG_STANDARD_CLARTE360.md`
- Sauvegarde technique incluse : `app_before_standard.py`
