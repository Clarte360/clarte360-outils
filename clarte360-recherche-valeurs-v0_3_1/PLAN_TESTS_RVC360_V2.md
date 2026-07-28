# Plan de tests RVC360 V2

## 1. Démarrage et prérequis
- Refus si aucune valeur n'a été travaillée avec l'accompagnateur.
- Une valeur validée, plusieurs valeurs, formulation hors référentiel.
- Conservation des composants identification, RGPD, code, timeout.

## 2. Présentation
- Présentation courte, longue, objectif vide, refus partiel.
- Vérification de la présence dans le JSON et dans le contexte API.
- Lecture vocale de la présentation de l'assistant.

## 3. Valeurs inter-séances
- Source cahier, émotion, événement, proche, autre.
- Mot exact du référentiel, mot proche, valeur personnelle hors référentiel.
- Situations et émotions conservées.

## 4. Exploration
- Changement de domaine après deux tours sur le même angle.
- Changement de domaine si aucun apport nouveau.
- Réponse très courte, très longue, contradictoire, « je ne sais pas ».
- Vérifier qu'une seule question est posée.
- Vérifier qu'aucune hypothèse hors sous-ensemble RVC360 n'est retournée.

## 5. Hypothèses et validation
- Hypothèse rejetée, à revoir, validée.
- Définition personnelle obligatoire avant validation.
- Questionnaire successif importante / très importante / fondamentale.
- Valeur validée enregistrée avec source et statut.

## 6. Complétude
- Moins de 8 valeurs sans blocage.
- 8 à 12 valeurs et plus de 12 valeurs.
- Domaines non explorés affichés.
- Valeurs lexicalement proches signalées.
- Retour possible vers l'exploration.

## 7. JSON
- Sauvegarde à chaque grande étape.
- Reprise exacte sur chaque page.
- Présence des rubriques V2.
- Compatibilité avec un JSON V1.4.1.
- Historique, sessions et traçabilité conservés.

## 8. PDF
- Page de garde, logo, identité, date et versions.
- Pied de page, pagination et confidentialité.
- Valeurs classées par source.
- Situations, émotions, hypothèses non retenues et complétude.
- Absence d'interprétation psychologique.

## 9. Voix
- Lecture, enregistrement, arrêt, transcription, correction et validation.
- Audio absent du JSON.
- Retour possible à l'écrit.
