# Changelog — Clarté360 Recherche de mes valeurs V2.1.3.8E

## Objet
Version de stabilisation issue des essais réels de la V2.1.3.8D.

## Principales corrections

- Moteur de décision obligatoire à quatre issues :
  - valeur reconnue ;
  - clarification unique nécessaire ;
  - valeur absente du référentiel mais possible ;
  - formulation ne correspondant pas au nom d’une valeur.
- Traitement identique des entrées écrites et orales avant le questionnaire spécifique.
- Blocage des doublons après normalisation, dans les valeurs validées, à examiner et à revoir en séance.
- Normalisation des noms : suppression des articles linguistiques, ponctuation terminale et reprise de la forme canonique du référentiel.
- Refus d’enregistrer une phrase, un constat ou une aspiration comme nom de valeur ; orientation informative vers le module 4 sans bascule automatique.
- Transition atomique entre les listes : une valeur ne peut plus rester simultanément validée et à examiner.
- Conservation structurée des questions complémentaires, réponses originales, reformulations, versions retenues, contexte et dates.
- Conservation séparée de la définition personnelle et de la définition Clarté360.
- Mise à jour du nom final dans la liste centrale lors d’un réexamen.
- Affichage renforcé de la progression « Valeur X / Y ».
- Remplacement du bouton ambigu « Quitter sans modifier » par :
  - « Abandonner la valeur en cours » ;
  - « Arrêter la saisie des valeurs restantes ».
- Les valeurs déjà complètement validées restent conservées lors de l’arrêt d’une série.
- Réinitialisation du délai d’inactivité sur les interactions réelles du module 3 et du moteur de réponse.
- Recalcul de l’analyse lorsqu’un nom, une définition ou une clarification change.
- Schéma métier porté à `2.1.3.8E`.

## Fichiers modifiés

- `app.py`
- `tests/test_v218_model.py`
- `tests/test_v218c_regressions.py`
- `tests/test_v218d_stabilisation.py`
- `tests/test_v218e_stabilisation.py` ajouté
- `README.md`

## Correctif moteur de normalisation — 2026-08-01

- suppression de toute substitution automatique entre deux valeurs différentes ;
- `Perfectionnisme` reste désormais `Perfectionnisme` et ne peut plus être transformé en `Professionnalisme` ;
- la normalisation est limitée aux corrections purement formelles : retrait d'article, ponctuation terminale, casse, accents et adoption de la forme canonique uniquement en cas d'équivalence stricte ;
- distinction corrigée entre valeur réellement présente dans le référentiel et valeur personnelle absente du référentiel ;
- ajout de tests de non-substitution et de présence référentielle exacte.
