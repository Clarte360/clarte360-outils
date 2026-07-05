# Clarté360 - Préférences professionnelles v1.9.1-socle-clarte360

Mise à niveau socle Clarté360 v3.0 alignée sur Moteurs professionnels v1.8.0 / Boussole valeurs pro v1.8.2.

## Points intégrés
- Version application : 1.9.1-socle-clarte360.
- Version socle : 3.0.
- Barre latérale standard : JSON de reprise, quitter et télécharger JSON, contact Clarté360, RGPD et mentions légales, réinitialisation avant démarrage.
- Page institutionnelle : Protection des données / Mentions légales / Nous contacter.
- Consentement RGPD obligatoire avant génération du code d'accès.
- Historique de génération et régénération du code dans le JSON.
- Bouton "Je n’ai pas reçu mon code".
- Traçabilité : sessions, temps cumulé, sauvegardes, informations techniques disponibles.
- Protection navigateur beforeunload.
- Timeout bénéficiaire 15 minutes avec téléchargement du JSON de reprise.
- Structure JSON enrichie : version application, version socle, passation root id, identifiant session, RGPD, access, temps cumulé.
- Rapport PDF harmonisé : logo centré et pied de page institutionnel Clarté360.
- Erreur SMTP administrateur non bloquante.

## Non modifié
- Questionnaire métier.
- Calculs de score.
- Ordre de tirage des questions et options.
- Interprétation des résultats.
- Exports JSON/PDF métier.

## v1.9.3 - Correctif chargement questionnaire
- Correction de l'appel `validate_question_bank` manquant au chargement des questions.
- Conservation du socle RGPD / traçabilité aligné Moteurs v1.8.
