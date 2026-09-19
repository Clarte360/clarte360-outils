# Clarté360 PIP RIASEC / O*NET - Contrats sortants Gestion des Actions - Jalon G

**Version contrat PIP :** `PIP-GA-OUTBOUND-1.0`  
**Schéma enveloppe :** `clarte360.pip.gestion-actions.event.v1`  
**Principe :** ce document décrit uniquement le côté PIP. Aucune modification de Gestion des Actions n'est incluse dans ce jalon.

## 1. Architecture de livraison

Le PIP n'appelle jamais Gestion des Actions depuis le navigateur. Chaque événement est d'abord écrit dans une **outbox serveur durable** :

`<CLARTE360_PIP_DATA_DIR>/connector_outbox/gestion_actions/pending/`

L'identifiant d'événement est aussi la clé d'idempotence. Il est calculé à partir du type d'événement et du payload canonique. Un événement strictement identique n'est donc enregistré qu'une fois.

Chaque enveloppe comporte au minimum : `event_id`, `idempotency_key`, `event_type`, `tool_id`, `contract_version`, `created_at`, `status`, `attempts`, `last_attempt_at`, `last_error`, `payload`.

Un worker/transport serveur pourra appeler `retry_pending(...)`. En cas d'indisponibilité du Hub, l'événement reste `PENDING`, le nombre de tentatives et la dernière erreur sont conservés. Après acquittement, l'enveloppe est déplacée dans `delivered/`.

La méthode `signed_delivery_headers(...)` prépare la signature HMAC SHA-256 serveur-à-serveur avec la clé déjà configurée du connecteur. Le secret n'est jamais placé dans l'URL, le payload ou les journaux.

## 2. PUBLIC

### `CONTACT_EMAIL_VERIFIED`

Émis immédiatement après validation correcte du code e-mail, sans attendre la passation.

Payload métier :
- `participant_id` technique PUBLIC ;
- `source = PIP_PUBLIC` ;
- prénom, nom, e-mail, téléphone ;
- fonction/titre, entreprise ;
- date/heure de vérification e-mail ;
- consentement marketing ;
- version d'information RGPD ;
- intérêts déclarés ;
- intérêt `PIP-RIASEC` ajouté systématiquement.

### `CONTACT_UPDATED`

Contrat disponible pour tout enrichissement ultérieur de la fiche contact. Le Jalon G ne fabrique pas artificiellement un événement lorsqu'aucune donnée contact n'a changé.

### `CALLBACK_REQUESTED`

Émis uniquement si la personne répond OUI à :

> Souhaitez-vous être recontacté(e) par Clarté360 pour échanger sur vos résultats ou votre projet ?

Payload : coordonnées nécessaires, source, date/heure, motif `ECHANGER_RESULTATS_OU_PROJET`.

**Interdit dans cet événement :** réponses PIP/O*NET, scores, code Holland, classement ou profil.

## 3. ACCOMPAGNEMENT

Les statuts `CONSULTE` et `EN_COURS` restent disponibles via l'outbox.

### `TERMINE`

Le statut final n'est plus émis à la dernière question PIP/O*NET. Il est émis **uniquement après** :
1. fin du parcours prévu ;
2. recueil du ressenti ;
3. génération réussie du ou des PDF ;
4. persistance serveur des documents.

Payload final :
- prescription, action, bénéficiaire et participant technique si disponible ;
- `passation_id` ;
- date/heure de fin ;
- version applicative ;
- PIP : `bank_version`, `scoring_version`, `report_version`, scores R/I/A/S/E/C, classement, code Holland, égalités ;
- O*NET : passé ou non, instrument/API/timing, scores et rangs si passé, version du rapport ;
- ressenti utile ;
- références documentaires PDF.

**Aucune des 72 réponses PIP et aucune des 60 réponses O*NET n'est transmise.**

## 4. Documents PDF

Les PDF ACCOMPAGNEMENT sont persistés sous :

`<CLARTE360_PIP_DATA_DIR>/reports/<passation_id>/`

Chaque référence documentaire transmise contient :
- nom de fichier ;
- MIME `application/pdf` ;
- SHA-256 ;
- taille en octets ;
- `storage_ref` relatif au répertoire de données PIP.

Si O*NET a été passé, les deux documents restent distincts : rapport PIP et rapport O*NET.

## 5. Séparation CRM / étude PUBLIC

À compter du Jalon G, les nouvelles données d'étude utilisent `clarte360.pip.public-study.v2` et un `study_id` aléatoire indépendant.

Le dataset étude ne contient plus `participant_id`, `passation_id`, identité, e-mail, téléphone ni identifiant CRM. Le pseudonyme d'étude n'est plus dérivé d'un identifiant de contact. Il n'existe donc pas de clé technique commune volontaire entre l'univers CRM et l'univers étude.

## 6. Responsabilité du futur chantier Gestion des Actions

Le futur chantier Hub/Gestion des Actions devra :
- consommer/acquitter les événements selon ce contrat ;
- gérer création/mise à jour CRM et rappel ;
- archiver/référencer les PDF accompagnement ;
- respecter l'idempotency key ;
- ne jamais exiger les réponses brutes PIP/O*NET ;
- définir les droits de visibilité des résultats et documents.
