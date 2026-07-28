# Journal des modifications – Clarté360 Recherche de valeurs V2.1.2

Base : V2.1.1, elle-même reconstruite depuis la V2.0. Le présent journal décrit les fonctions effectivement intégrées dans le code livré.

## Canvas 2.1.1 à 2.1.29

1. **2.1.1 – Lecture vocale des questions** : toutes les questions ouvertes utilisent le composant commun qui affiche automatiquement `🔊 Écouter`. La lecture peut être désactivée globalement. Les questions fermées à simple choix ne sont pas obligatoirement lues.
2. **2.1.2 – Réponse vocale** : un seul enregistreur vocal est utilisé pour toutes les questions ouvertes du parcours métier.
3. **2.1.3 – Validation de la transcription** : la transcription brute est affichée et ne devient jamais une réponse officielle sans validation explicite.
4. **2.1.4 – Reformulation optionnelle** : après validation, le bénéficiaire choisit de conserver son texte ou de demander une reformulation.
5. **2.1.5 – Validation de la reformulation** : comparaison entre le texte validé et la proposition Clarté360, avec conservation, adoption ou modification.
6. **2.1.6 – Sauvegarde structurée** : mode de saisie, texte brut, transcription, correction, reformulation et version officielle sont conservés dans le JSON de travail.
7. **2.1.7 – Questionnaire bénéficiaire** : les deux grandes questions ouvertes ont été remplacées par des questions distinctes sur la situation, le parcours, les activités importantes, les passions, les projets et l’attente.
8. **2.1.8 – Lecture des contenus importants** : lecture ajoutée aux principales introductions, consignes, rappels, contrôles, messages de reprise, clôture, résultats et RGPD.
9. **2.1.9 – Double mode permanent** : clavier et voix sont proposés ensemble sur toutes les zones de réflexion ouverte.
10. **2.1.10 – Enregistrement intégré** : cycle unique enregistrer, arrêter, transcrire, corriger, valider ou réenregistrer.
11. **2.1.11 – Cohérence des valeurs** : synchronisation immédiate des valeurs validées entre mémoire, panneau, statuts, JSON et rapport.
12. **2.1.12 – Synchronisation des écrans** : fonction centrale de réconciliation et traçabilité des événements de dépendance.
13. **2.1.13 – Navigation libre et recalcul** : retour précédent/suivant, accès direct aux étapes déjà ouvertes, modification des anciennes réponses d’exploration, suppression des productions obsolètes, recalcul de l’aval et blocage de clôture tant que la cohérence n’est pas rétablie.
14. **2.1.14 – Valeurs découvertes seul** : conservation de l’origine, du sens, des situations, des émotions et du degré de certitude.
15. **2.1.15 – Validation immédiate** : choix entre validation HEC immédiate et mise en attente, avec retour à l’étape quittée.
16. **2.1.16 – Statuts** : valeurs repérées, à confirmer, en cours d’analyse, validées, à revoir ou abandonnées.
17. **2.1.17 – Interruptions IA** : tentatives automatiques, conservation de la réponse et relance manuelle claire.
18. **2.1.18 – Évolution du raisonnement** : première hypothèse et hypothèse révisée sont conservées et affichées.
19. **2.1.19 – Reprise intelligente** : accueil personnalisé, interrogation sur les nouvelles valeurs et reprise exacte de l’état du parcours.
20. **2.1.20 – Priorité aux découvertes personnelles** : traitement des nouvelles valeurs avant la poursuite de la recherche guidée.
21. **2.1.21 – Fermeture définitive** : sortie temporaire distincte, double confirmation et écran spécifique.
22. **2.1.22 – JSON final épuré** : fichier de restitution sans dialogues, transcriptions brutes, erreurs, questionnaires détaillés ni secret.
23. **2.1.23 – Consultation et réimpression** : mode lecture seule, synthèse, PDF régénérable, copie JSON et transmission.
24. **2.1.24 – Remise des documents** : PDF et JSON final proposés avant clôture.
25. **2.1.25 – Transmission** : envoi SMTP du JSON final, avec PDF facultatif.
26. **2.1.26 – Consentement** : distinction entre besoin pédagogique et autorisation d’envoi automatique.
27. **2.1.27 – Irréversibilité** : aucun retour au mode modification depuis le JSON final et aucun nouvel appel IA.
28. **2.1.28 – RGPD** : adaptation à la voix, aux corrections, aux deux JSON, à la transmission et au contrôle d’accès.
29. **2.1.29 – Code de déblocage** : secret absent des exports et preuve d’autorisation exigée pour la reprise.

## Corrections demandées après audit

- suppression de tous les numéros visibles devant les titres d’écran ;
- suppression des numéros d’étape dans la barre latérale ;
- suppression des doublons de boutons d’écoute ;
- remplacement du second système vocal de l’exploration par le composant vocal commun ;
- ajout d’une correction spécifique de l’oral : hésitations, répétitions immédiates, faux départs et ponctuation ;
- validation obligatoire de toute réponse écrite ou orale avant utilisation ;
- possibilité de modifier une ancienne réponse d’exploration et de recalculer toute la suite ;
- invalidation ciblée d’une validation lorsque le sens personnel d’une valeur change ;
- suppression des valeurs et validations associées lorsqu’une valeur source est retirée ;
- conservation exacte de l’état de reprise dans `metier.etat_reprise` ;
- audit de cohérence avant accès à la clôture et nouvelle vérification au moment de la confirmation définitive.

## Contrôles de fabrication

- compilation Python réussie ;
- **11 tests automatisés réussis** ;
- contrôle de l’absence de numérotation visible dans les titres ;
- contrôle de l’existence d’un seul appel `st.audio_input` dans le composant commun ;
- contrôle du nettoyage local des hésitations et répétitions ;
- contrôle des invalidations après modification du profil et d’une définition de valeur ;
- contrôle du blocage de clôture lorsque des sections sont obsolètes ;
- contrôle de la présence de l’état exact de navigation et de validation dans le JSON de reprise ;
- génération du PDF final depuis le seul JSON final vérifiée.

## Recette restante en préproduction

Les appels réels de transcription, de reformulation, l’envoi SMTP et le comportement responsive doivent être testés sur l’instance Streamlit équipée des Secrets réels. Aucun secret n’est inclus dans le ZIP.
