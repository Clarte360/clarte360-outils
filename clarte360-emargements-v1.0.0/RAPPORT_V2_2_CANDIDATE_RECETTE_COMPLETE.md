# CLARTÉ360 ÉMARGEMENTS — V2.2-RC1 — CANDIDATE DE RECETTE COMPLÈTE

## 1. Périmètre consolidé
Cette candidate regroupe les trois lots V2.2 sans reconstruction de l'application :

- Lot 1 : socle technique et espace intervenant ;
- Lot 2 : bénéficiaires permanents et portail documentaire ;
- Lot 3 : fin d'action et qualité.

Le dossier historique de déploiement reste `clarte360-emargements-v1.0.0`.

## 2. Compléments réalisés pendant la consolidation finale
L'audit transversal de la candidate a détecté plusieurs éléments qui devaient être finalisés avant une vraie recette :

1. La version affichée était encore `2.2-Lot2` : elle est maintenant `2.2-RC1`.
2. Le Lot 3 créait la file `client_transmissions`, mais le worker ne transmettait pas encore physiquement les pièces jointes. La candidate traite maintenant cette file et joint le ZIP final ou le PDF COLD au mail.
3. La complétion d'une évaluation COLD crée désormais le second flux de transmission indépendant, uniquement lorsque la transmission client a été activée et avec les destinataires configurés.
4. Les transmissions client utilisent une réservation atomique et un statut `UNKNOWN_DELIVERY` après interruption ambiguë, afin d'éviter les doubles envois.
5. Le mécanisme de rétention portail détectait les dossiers anciens mais n'avait pas encore le cycle complet d'avertissement puis purge. La candidate envoie l'avertissement, laisse 30 jours pour télécharger le ZIP, puis purge uniquement le portail.
6. Si une nouvelle action est rattachée au bénéficiaire avant la purge, la purge n'a pas lieu.
7. Le nom du ZIP final utilise la date de fin d'action lorsqu'elle est disponible.
8. Le journal des transmissions client est désormais visible depuis l'administration.

## 3. Protection des acquis
Les tests historiques V1/V2, ceux de la V2.1.4 et ceux des trois lots V2.2 restent présents et réussissent. Les migrations sont additives et ne remplacent pas la base SQLite existante.

## 4. DeltaGenerator / lisibilité des interfaces
Contrôle transversal effectué sur `app.py` : aucune instruction de type expression conditionnelle Streamlit (`st.success(...) if ... else ...`) n'est présente. Le test historique interdisant les motifs déjà responsables des affichages `DeltaGenerator` reste actif.

Ce contrôle couvre le même fichier applicatif utilisé par l'administration, l'espace intervenant et l'espace bénéficiaire.

## 5. Résultat technique
**75 tests réussis sur 75.**

Compilation Python des modules principaux : réussie.

## 6. Ce qui doit être testé sur le VPS
La candidate est prête pour une recette fonctionnelle réelle. Les points prioritaires sont :

- invitation / mot de passe / mot de passe oublié intervenant ;
- affichage et renvoi du code personnel stagiaire par l'intervenant ;
- tableaux de bord intervenant et bénéficiaire sur PC et smartphone ;
- rattachement d'un bénéficiaire existant avec changement d'email ;
- dépôt du même fichier sous deux noms et vérification de la déduplication ;
- clôture d'une action et génération automatique du ZIP quelques heures plus tard ;
- envoi SMTP réel du ZIP final aux destinataires choisis ;
- complétion d'une évaluation COLD et réception de son PDF séparé ;
- journal des transmissions ;
- pilotage qualité direction ;
- absence totale de `DeltaGenerator` ou autre représentation technique dans les trois interfaces.

## 7. Verdict
**V2.2-RC1 prête pour déploiement de recette VPS.**

La mise en production définitive ne doit être décidée qu'après la recette humaine complète et la vérification des emails réels.
