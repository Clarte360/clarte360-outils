# INCREMENT INTERVENANTS RC2-2-2 — P1 DONNÉES — 02/10/2026

## 1. Objet
Le jalon P1 implémente exclusivement le socle de données demandé par le CDC RC2-2-2 : migration du type de collaboration, structuration des points à vérifier, provenance réutilisable des faits/preuves et protection automatique des décisions humaines.

Base de départ officielle : `clarte360-gestion-actions-v3.0.0-INTERVENANTS-RC2-2-1-RECETTE.zip`.
Version de travail : `3.0.0-INTERVENANTS-RC2-2-2-P1`.

Aucun chantier P2 IA, P3 UX, P4 tableaux, P5 Actions ou P6 CV n'est engagé dans ce jalon.

## 2. Schéma additif
Quatre objets persistants sont ajoutés sans reconstruction destructive des tables RC2-2-1 :

### 2.1 `professional_collaboration_history`
Historise les changements de type de collaboration avec Clarté360 et les migrations automatiques. Le journal porte l'ancienne valeur, la nouvelle valeur, la raison, l'acteur, un identifiant d'événement idempotent et, si nécessaire, un état de reclassement humain.

### 2.2 `qualification_review_points`
Transforme les anciens points IA textuels en objets actionnables : source, prestation, critère/document/preuve éventuels, libellé, statut `OUVERT / LEVE / CONFIRME / NON_PERTINENT`, commentaire de résolution, auteur et dates.

### 2.3 `professional_fact_sources`
Ajoute une provenance générique aux faits professionnels structurés. Un fait peut être relié à une ou plusieurs sources sans dupliquer le fait lui-même : saisie humaine, proposition IA acceptée, import, migration ou autre origine maîtrisée.

### 2.4 `qualification_evidence_links`
Permet de réutiliser un fait ou document déjà validé dans plusieurs prestations et critères. Le lien exprime la pertinence pour la qualification ; il ne recopie ni le document ni le fait.

## 3. Migration du type de collaboration
Liste cible fermée côté métier :
- `A_DEFINIR`
- `SALARIE`
- `STAGIAIRE`
- `SOUS_TRAITANT`
- `MANDATAIRE_ASSOCIE`

Migration additive et tracée :
- `SALARIE_INTERNE` -> `SALARIE` ;
- `SOUS_TRAITANT` conservé ;
- `A_DEFINIR` conservé ;
- `INDEPENDANT` -> `A_DEFINIR` + reclassement humain requis ;
- `PARTENAIRE` -> `A_DEFINIR` + reclassement humain requis.

La migration est idempotente : un redémarrage de `init_db()` ne crée pas plusieurs événements de migration identiques.

## 4. Protection automatique des décisions humaines
Le verrou humain devient une règle backend et non une décision utilisateur :
- proposition IA sans décision humaine : `human_locked=0` ;
- décision humaine globale existante : `human_locked=1` ;
- décision humaine par critère existante : `human_locked=1` ;
- lors de l'initialisation, les anciens états incohérents sont réparés selon la présence réelle d'une valeur humaine.

Les signatures de fonctions existantes sont conservées pour compatibilité, mais un appel métier ne peut plus enregistrer une décision humaine non protégée.

## 5. Migration des anciens points IA
Les chaînes historiques de `ai_missing_json` sont projetées dans `qualification_review_points` comme points `OUVERT` de source `MIGRATION`, avec une clé stable dérivée du run/qualification et de l'index du point.

L'historique d'origine reste conservé. La migration ne supprime pas le JSON historique et ne crée pas de doublons au redémarrage.

## 6. Provenance des faits professionnels
Les créations manuelles d'expériences, diplômes/formations, certifications, langues et spécialités créent une provenance `HUMAN`.

L'acceptation d'une proposition IA crée directement une provenance `AI_ACCEPTED` avec, lorsqu'ils existent, l'identifiant du document source et l'identifiant de la suggestion IA. Une acceptation IA n'est donc plus faussement marquée comme saisie humaine.

Les faits RC2-2-1 préexistants sans provenance reçoivent une provenance `MIGRATION` au premier `init_db()`. Cette opération est idempotente et n'invente pas de document source absent des données historiques.

Les modifications humaines de lignes structurées enregistrent également une provenance humaine. La suppression d'un fait supprime ses liens génériques de provenance/pertinence afin d'éviter des références pendantes.

## 7. Réutilisation des preuves/faits
Le service de qualification peut désormais lier un même fait/document à plusieurs prestations et critères via `qualification_evidence_links`. Une vérification explicite évite la duplication logique même lorsque certains champs facultatifs sont `NULL`.

Cela prépare le principe RC2-2-2 : « valider une fois, réutiliser plusieurs fois », sans transformer automatiquement la pertinence d'une preuve en décision de qualification.

## 8. Compatibilité et suppression de dossier
Les nouveaux objets ont été intégrés aux opérations de remise à zéro et de suppression contrôlée du dossier professionnel. Les objets possédés uniquement par le dossier P1 ne bloquent pas artificiellement la suppression physique d'un dossier d'essai sans dépendance métier externe.

L'historique de collaboration est préservé lors d'une remise à zéro de contenu professionnel, mais est supprimé avec la personne lors d'une suppression physique réellement autorisée.

## 9. Fichiers de code modifiés
- `db.py`
- `services.py`
- `branding.py`

Tests historiques adaptés uniquement lorsque l'ancienne liste de collaboration ou l'identifiant de version rendait l'attente obsolète. Le sens des garde-fous n'a pas été supprimé.

Nouveau test P1 : `tests/test_intervenants_rc2_2_2_p1_data.py`.

## 10. Hors périmètre P1
Restent volontairement pour les jalons suivants :
- correction sémantique du faux niveau IA global 0/4 ;
- PDF hybride page par page ;
- instrumentation appels/retries/tokens/coût ;
- refonte navigation/cockpit/Analyse IA/Qualifications ;
- date-picker ;
- tableaux DRH ;
- deep-link Action -> Qualification -> Retour Action ;
- finition CV/historique/UX.

## 11. Résultat du jalon
P1 fournit le schéma additif et les migrations nécessaires au CDC RC2-2-2 sans altérer les domaines historiques PIP/IPIP, worker, émargements, signatures, Teams, outils bénéficiaire ou Gestion Clients.

La validation du jalon repose sur la campagne détaillée dans `RAPPORT_TESTS_INTERVENANTS_RC2_2_2_P1_20261002.md`.
