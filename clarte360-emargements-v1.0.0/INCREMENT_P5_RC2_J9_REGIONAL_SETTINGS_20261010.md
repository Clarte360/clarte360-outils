# INCRÉMENT P5-RC2 J9 — Paramètres régionaux et ergonomie

J9 est un jalon intermédiaire, cumulatif J1–J9. Il ne doit pas être déployé. Le ZIP final P5-RC2 sera transmis par l’utilisateur lui-même via GitHub.

## Fondations
- Nouvelles colonnes additives : `organizations.display_date_format`, `.display_time_format`, `.display_language`; fuseau `organizations.timezone` existant et conservé.
- Préférences par organisme, avec validation IANA, defaults FR, 24 h, Europe/Paris.
- Fichier pur `regional_settings.py` pour formater les horodatages UTC, dates civiles et heures de planning sans changer leur stockage ni leur interprétation.
- Paramètres régionaux disponibles dans Administration / Paramètres / Général ; identité légale conservée séparément.
- Champs de date Streamlit adaptés au format choisi et sorties affichées révisées (Qualité, événements, historiques, clients, intervenants, bénéficiaires, notifications).
- Les libellés longs, notamment « Distanciel-visioconférence », utilisent du texte non tronqué au lieu d’une métrique.
- Le passage heure d'été/hiver fait l'objet de tests ; les horodatages probants restent UTC.

## Périmètre non traité
- La langue EN constitue une préférence de présentation régionale, pas une traduction totale de l’interface.
- Les exports bruts/JSON et certaines preuves légales conservent les valeurs ISO/UTC ; les écrans Teams/planning métiers ne changent pas de fonctionnement.
- Les vérifications réelles multi-organismes et visuelles attendent la recette finale après un seul déploiement RC2.
- Les interfaces Contractualisation 13 / Gestion Clients 17 restent hors périmètre J9.

## Test
Suite complète, test spécifique des 20 cas J9 et test sur une extraction neuve du ZIP à conserver en preuves externes.
