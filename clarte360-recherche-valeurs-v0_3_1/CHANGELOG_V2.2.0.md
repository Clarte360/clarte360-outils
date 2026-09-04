# Clarté360 Recherche des valeurs — V2.2.0-preproduction-4

Date : 4 septembre 2026

## Objet

Mise en conformité avec l'audit préparatoire du 4 septembre 2026 et le référentiel officiel RVC360 API V2.5.

## Changements principaux

- Nouveau contrat transversal de qualité d'expression pour toutes les réponses libres utilisant `open_response_widget`.
- Statuts distincts : `aucune_modification`, `correction_forme`, `reformulation_expression`, `clarification_necessaire`, `echec_technique`.
- Un échec API ou une proposition identique à l'original ne peut plus être présenté comme « réponse déjà claire ».
- Même traitement pour clavier et voix.
- Métadonnées JSON enrichies : statut d'expression, raison, correction linguistique distincte de la reformulation.
- Module 4 : décisions indépendantes Oui / Peut-être / Non pour chaque hypothèse.
- Plusieurs hypothèses d'une même exploration peuvent rejoindre simultanément le panier Hypothèses.
- Les refus du Module 4 sont mémorisés séparément et réutilisés pour éviter les repropositions répétitives.
- Schéma métier de reprise porté à `2.2.0`.
- Suite de tests remise en cohérence avec la version courante et complétée par des tests V2.2.0.


## Correctif preproduction-2 — qualité réelle de la proposition d’expression

À la suite du test bénéficiaire réel sur la définition de « créativité », le moteur ne se contente plus d’un nettoyage superficiel de l’oral.

- Le prompt demande désormais d’identifier les unités de sens explicitement présentes, puis de les recomposer dans un français naturel et réutilisable.
- Les hésitations sans contenu (par exemple « je ne sais pas quoi encore », « des trucs dans ce genre-là quoi ») peuvent être supprimées sans être recopiées mécaniquement.
- Une proposition qui conserve trop de marqueurs d’oralité ou d’imprécision est rejetée avant affichage.
- En cas de proposition insuffisante, une deuxième tentative est déclenchée avec une consigne de reprise explicite.
- Le cas réel « créativité » est désormais un test de non-régression.
- Une réserve réellement porteuse de sens ne doit pas être gommée : le moteur la conserve ou demande une clarification.

## Contrôles réalisés

- `python -m py_compile app.py` : OK
- `pytest -q` : 132 tests réussis

## Points à tester en passation bénéficiaire

1. Réponse écrite déjà propre.
2. Réponse écrite avec fautes légères.
3. Réponse écrite compréhensible mais très orale/répétitive.
4. Réponse ambiguë nécessitant une précision.
5. Simulation d'indisponibilité API : aucun faux message « déjà claire ».
6. Même série à l'oral.
7. Module 4 avec trois hypothèses : conservation de deux hypothèses et refus de la troisième.
8. Reprise JSON après sélection multiple des hypothèses.


## V2.2.0-preproduction-4 - Convergence Module 4

- maximum absolu de 5 questions validées par bloc dans le Module 4 ; aucune 6e question automatique ;
- bouton permanent « Faire le point avec mes réponses actuelles » après au moins une réponse validée ;
- synthèse transversale de toute la mémoire validée des deux voies du Module 4 ;
- recherche de récurrences entre situations différentes avant proposition de nouvelles hypothèses ;
- comparaison avec les valeurs déjà validées, à examiner, au panier Hypothèses et les pistes à clarifier afin d’éviter les doublons ;
- possibilité de signaler qu’un élément déjà connu est renforcé sans le reproposer comme nouvelle hypothèse ;
- après synthèse sans hypothèse : autre voie, nouveau bloc volontaire de 5 questions maximum ou arrêt ;
- relances du même bloc renforcées pour rester sur le même fil et éviter les changements brutaux de sujet ;
- compatibilité reprise JSON : un ancien cycle contenant déjà 5 réponses ou davantage est envoyé directement vers la synthèse globale.
