# V2 — Incrément intermédiaire n°2 — Émargements + Qualité fonctionnelle

Date : 3 septembre 2026

## Positionnement

Ce ZIP repart du jalon `2.0.0-dev-I1-consolide` (22/22 tests) et conserve le socle V1.1.1/V2 sans réécriture. Il reste un jalon technique : aucune installation VPS ni recette humaine n'est demandée.

## Réalisé dans cet incrément

- catalogue embarqué des 13 questionnaires standard V2 validés : Formation, Bilan de compétences, VAE, Coaching, Mentorat, Autre, plus retour intervenant ;
- conservation des codes de question et rubriques fixes R01-R16 / I01-I07 ;
- amorçage idempotent des modèles versionnés par organisme ;
- dates de début/fin d'action utilisables même lorsqu'aucun émargement n'est activé ;
- campagnes qualité bénéficiaire à chaud, à froid et intervenant ;
- calendrier standard : fin de prestation, J+90, Bilan de compétences M+6, retour intervenant en fin d'action ;
- relances automatiques : J+2/J+7 pour chaud et intervenant, +7/+14 pour froid ;
- table dédiée `quality_email_events` et réservation atomique du worker ;
- quarantaine `UNKNOWN_DELIVERY` après crash ambigu, comme pour l'émargement ;
- emails qualité adaptés au type de campagne et au paramétrage organisme ;
- lien individuel sécurisé `quality_token` ;
- questionnaire électronique responsive Streamlit PC/tablette/smartphone ;
- types de réponses : échelle 1-5 + N/A, NPS 0-10, choix unique, texte libre ;
- validation des questions obligatoires et consentement avant enregistrement ;
- snapshot du texte exact, code, rubrique, type, version et horodatage conservés ;
- clôture de campagne et neutralisation automatique des relances restantes ;
- création automatique d'une fiche difficulté/aléa/réclamation lorsqu'une réponse R12/I06 le justifie ;
- restitution PDF individuelle d'un questionnaire complété ;
- nouvel onglet `Qualité` dans une action pour préparer, suivre et consulter les campagnes ;
- export JSON d'action enrichi avec campagnes, réponses, événements qualité, difficultés et améliorations ;
- suppression participant/action complétée pour ne pas laisser survivre des objets qualité rattachés ;
- certificat/attestation différencié : Formation/BC/VAE vs Coaching/Mentorat/Autre ;
- normalisation de la clôture sur `CLOTUREE` au lieu du statut historique `TERMINEE`.

## Non compris volontairement dans cet incrément

Le prochain jalon reste consacré aux imports Clarté360/ADCA historiques, pilotage consolidé, statistiques, exploitation détaillée des réclamations/actions d'amélioration et finition de transférabilité/branding. La recette SMTP et smartphone réelle reste réservée à la candidate V2 sur VPS.
