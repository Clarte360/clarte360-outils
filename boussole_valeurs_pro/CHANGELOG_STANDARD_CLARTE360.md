# Boussole des valeurs professionnelles - v1.8.2

Correctifs socle Clarté360 v3.0 :

- Correction de la page RGPD / traçabilité : ajout de la fonction de formatage des durées utilisée par le bloc de traçabilité.
- Ajout d'un bouton de retour visible en haut des pages RGPD et Contact lorsque l'utilisateur est déjà entré dans l'application.
- Correction de la navigation latérale : un clic sur une rubrique métier ferme automatiquement la page institutionnelle RGPD ou Contact et ramène dans le cœur de l'application.
- Conservation de la suppression du bouton Réinitialiser la session pendant la passation.
- Conservation de la suppression de l'onglet RGPD du menu métier.

Logique métier non modifiée : valeurs, points d'appui, cotations, boussole, valeurs énergies et philosophie pédagogique inchangés.


## v1.8.2

- Harmonisation graphique du rapport PDF avec la charte Clarté360 : logo officiel centré, titre centré, en-tête institutionnel aligné sur Moteurs Professionnels.
- Aucune modification de la logique métier, des écrans Streamlit, du JSON, des sessions, du RGPD ou du timeout.

## 1.8.3 — Validation saisies / VPS / Hub ready
- validation métier centralisée et import JSON durci ;
- préparation URL/service VPS ;
- contrat Hub I9-H1 Administrateur/Intervenant → bénéficiaire ;
- tests automatisés ajoutés ;
- aucune modification des règles métier de la Boussole.


## 1.8.4 — Garde-fou anti-perte de travail
- garde-fou navigateur homogénéisé sur F5, fermeture d’onglet et navigation externe ;
- détection immédiate des nouvelles saisies côté navigateur ;
- empreinte métier du travail pour distinguer un JSON à jour d’un JSON devenu ancien ;
- téléchargement JSON = nouvel état sauvegardé ; toute modification ultérieure réactive la protection ;
- import JSON = nouveau point de reprise propre ;
- aucune modification de la logique métier, des cotations, de la roue ou des Valeurs énergies.


## 1.8.5 - VPS MAIL / HUB REGISTRY
- configuration e-mail VPS : priorité au secret `[MAIL]`, compatibilité maintenue avec `[email]` Streamlit Cloud et anciens formats ;
- suppression totale de l'affichage du code d'accès en mode test lorsque l'envoi e-mail échoue ;
- messages utilisateur alignés sur la configuration MAIL du serveur VPS ;
- branchement réel du contrat Hub I9 dans `app.py` (`hub_token`/`token`, HMAC, suppression du jeton de l'URL) ;
- une prescription Hub valide dispense du code e-mail mais conserve le consentement RGPD bénéficiaire ;
- identité bénéficiaire préremplie depuis le contexte Hub signé lorsqu'elle est fournie ;
- service VPS d'exemple aligné sur FRAMEWORK VPS V1.1 : dossier stable `boussole_valeurs_pro`, utilisateur `ubuntu`, port 8505 explicite ;
- identité applicative passée en production sur `https://boussole-valeurs.clarte360.com`.
