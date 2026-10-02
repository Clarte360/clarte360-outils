# Clarté360 — Profil de fonctionnement professionnel — IPIP-NEO-120

Version applicative : **0.8.0-rc2**  
État : **RC2 — J6 ACCOMPAGNEMENT / sécurité terminé**  
Mode : **ACCOMPAGNEMENT**

## Références
- CDC : `CDC_CLARTE360_IPIP_NEO120_V1_6.docx`
- Framework maître : `FRAMEWORK CLARTE 360_V5.docx`
- Addendum : `FRAMEWORK_CLARTE360_V4_1_ADDENDUM_REFERENCE_PIP_RIASEC_ONET.docx`
- Implémentation technique de référence : PIP RIASEC / O*NET Clarté360 V1.0.10 ACCOMPAGNEMENT
- Framework VPS : V1.3

## Métier conservé
Cette RC2 ne refait pas le métier IPIP. Les référentiels, 120 items, 5 domaines, 30 facettes, scoring, inversions, adaptation O6, interprétation, questionnaire de ressenti, verrouillage TERMINE et contrat Gestion des Actions proviennent de la RC1 V0.7.1 et restent protégés par non-régression.

## J1
Le J1 remet en place l'enveloppe Framework : identité, branding, logo, sidebar, navigation, session, timeout, contact, persistance générique, stockage serveur atomique et structure UI.

Les évolutions RGPD finales, accueil final, passation une affirmation à la fois, restitution graphique et rapport PDF seront traitées dans les jalons suivants.

## Lancement local technique
`streamlit run app.py`

Cette version n'est pas destinée au déploiement dans le cadre du chantier actuel.

## RC2 — J2 (01/10/2026)
Accueil Clarté360, RGPD spécifique IPIP, information préalable tracée et mention non clinique. Le métier IPIP reste gelé.


## RC2 J3 — Passation bénéficiaire
La passation RC2 présente désormais une affirmation à la fois, avec progression Question X / 120, navigation PRÉCÉDENT/SUIVANT, sauvegarde serveur à chaque navigation et reprise exacte de la position. Les sauvegardes historiques par bloc restent lisibles.

## RC2 — J4 (2026-10-02)
La restitution bénéficiaire est remise au niveau Clarté360 : vue des 5 domaines, repères graphiques descriptifs, 30 facettes structurées, contextualisation points d'appui/vigilance, exemples professionnels non prescriptifs, questions de réflexion et mise en perspective avec le parcours. Le métier IPIP reste gelé.


## RC2 - J5
Rapport PDF Clarté360 refondu et séquence de clôture contrôlée.

## RC2 - J6
Audit et renforcement du contrat ACCOMPAGNEMENT côté IPIP : scopes explicites, anti-croisement, report_ref complet et confiné, refus des réponses brutes dans les événements, contrôle TERMINE et idempotence. Gestion des Actions n'est pas modifiée.


## J7 — Audit final RC2
Audit final CDC V1.6 / Framework V5 / Addendum V4.1, campagne intégrale et prévalidation des scopes de clôture avant toute mutation. La RC2 reste à soumettre à la recette utilisateur avant déploiement.

## RC3 — recette finale (2026-10-02)
- Le questionnaire de ressenti permet de revoir les résultats puis de revenir au ressenti sans perdre les saisies en cours.
- Le téléchargement du rapport utilise un nom lisible : initiale du prénom + nom + IPIP NEO120 + intitulé du rapport.
- La référence documentaire envoyée à Gestion des Actions conserve un `storage_ref` technique, mais expose un `file_name` / `display_name` humain et un libellé de catégorie lisible.
- Aucun changement du référentiel IPIP, du scoring, des inversions, de l'interprétation ou de la décision O6.
