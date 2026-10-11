# CLARTÉ360 — Gestion des Actions / Émargements — J11 / P5-RC2

**Statut : PACKAGE FINAL J11 POUR RECETTE MÉTIER SUR VPS — NON VALIDÉ POUR EXPLOITATION DÉFINITIVE.**

Ce document supplante `DEPLOIEMENT_VPS.md` de la P5-RC1 (référence obsolète V1.3 et 423 tests). Il s'applique uniquement à la version **P5-RECETTE-RC2** et au FRAMEWORK VPS CLARTÉ360 V1.4 du 05/10/2026, à vérifier de nouveau lors du déploiement.

## 1. Ce que le GO utilisateur du 11/10/2026 autorise

- Réalisation locale des réglages des rappels Teams et livraison du ZIP final J11 destiné à la recette sur VPS.
- **AUCUN accès, commit ou push GitHub par l'assistant.** Import dans GitHub Desktop uniquement par le propriétaire, après examen du ZIP.
- **AUCUN déploiement VPS, migration SQL réelle, redémarrage ou modification des secrets par l'assistant.** Le GO de préparation J11 ne vaut pas GO `DÉPLOIEMENT VPS`.
- La recette Teams/SMTP, quatre espaces, droits BC, restauration PRA et intégrations 13/17 se fait après la livraison et après autorisation d'installation. Toute non-conformité reste à instruire.

## 2. Identité de l'application : NE PAS CHANGER

| Élément | Identité officielle |
| --- | --- |
| URL | https://emargements.clarte360.com |
| Port Streamlit | 8501 sur 127.0.0.1 |
| Service web | clarte360-emargements.service |
| Service worker | clarte360-emargements-worker.service |
| Dépôt | Clarte360/clarte360-outils |
| Dossier stable | /opt/clarte360/clarte360-outils/clarte360-emargements-v1.0.0/ |
| Secrets centralisés | /opt/clarte360/secrets/secrets.toml |
| Lien secrets | .streamlit/secrets.toml → /opt/clarte360/secrets/secrets.toml |
| SQLite existant | data/clarte360_emargements.db (WAL/SHM à respecter) |
| PRA | OneDrive — 99 BACKUP VPS CLARTE360, ne pas créer un second dispositif |

Le nom du ZIP ou de son répertoire d'extraction **ne détermine pas l'identité de déploiement**. Les exemples `systemd/` historiques du code ne doivent pas être installés automatiquement à la place des services existants.

## 3. Sécurisation préalable — à exécuter par le propriétaire APRÈS GO VPS

1. Vérifier le Framework VPS à jour et l'identité ci-dessus, ainsi que DNS/Nginx/port et l'absence de conflit (`sudo ss -lntp`, `sudo systemctl cat ...`, `sudo nginx -t`).
2. Vérifier `git status` et le commit **actuellement en production**, sans supposer que P5-RC1 est encore sur le VPS. Conserver les fichiers non suivis historiques et les sauvegardes sans les committer.
3. Effectuer un **point de retour arrière cohérent et récent** : code/commit + snapshot SQLite `Connection.backup()` + WAL/SHM traités de façon cohérente + `data/` COMPLET (documents, signatures, exports, qualifications, historiques) + liens de secrets/configuration. Ne pas utiliser le vieux point AVANT P5 comme retour arrière RC2.
4. Contrôler qu'une restauration isolée est possible selon le PRA du dossier OneDrive `99 BACKUP VPS CLARTE360`. Les copies/restaurations de base seule ne prouvent pas les documents ou la reconstruction complète du VPS.
5. Préparer un environnement de recette et des adresses e-mail **strictement fictives/de démonstration** sans interrompre les vraies formations ; prévoir une fenêtre calme car les délais sont communs à toutes les actions Teams de l'organisme sélectionné.

**Important :** `data/`, `.venv/`, les secrets, les documents et les fichiers de sauvegarde ne sont jamais remplacés par les fichiers du ZIP. Les migrations SQLite du démarrage ajoutent deux colonnes aux organismes et les objets de J1-J9 : retour arrière du code seul INSUFFISANT.

## 4. Import du ZIP dans GitHub Desktop — propriétaire uniquement

1. Vérifier le manifeste SHA-256 fourni et le fichier de livraison `clarte360-gestion-actions-v3.0.0-P5-RECETTE-RC2.zip`.
2. Extraire le ZIP ; son dossier racine doit être `clarte360-emargements-v1.0.0/`. Copier **le code seulement** dans le dossier homonyme de la copie locale du dépôt GitHub. Ne supprimer aucune ancienne donnée ou configuration locale non versionnée.
3. Dans GitHub Desktop, vérifier les fichiers modifiés/nouveaux, s'assurer qu'aucun `data/`, `.venv`, `secrets.toml`, SQLite, signature, PDF bénéficiaire ou backup n'entre dans le commit. C'est le propriétaire qui fait commit et push.
4. Noter le hash du nouveau commit et le comparer au fichier `POINT_DE_REPRISE` et au PV J11.

**Aucune installation VPS ne doit être engagée sans le GO de déploiement explicite du propriétaire.** Les commandes de bascule/retour arrière seront préparées au moment de ce GO, sur les preuves récentes de l'environnement réel. Aucun copier-coller d'un ancien script de déploiement P5-RC1 ou d'un système d'exemple sans contrôle.

## 5. Contrôles VPS après installation autorisée

- Services web et worker `active`, health HTTP local et HTTPS public ; identités port/URL/services conformes au Framework VPS V1.4.
- 122 tables attendues pour la candidate P5-RC2 et deux nouvelles colonnes **additives** des organismes : `online_reminder_first_minutes` (120) et `online_reminder_second_minutes` (15). Ne pas interpréter ce chiffre comme un inventaire de la vraie base sans requête de contrôle.
- `PRAGMA integrity_check=ok`, `PRAGMA foreign_key_check` vide, anciennes clés/compteurs et fichiers persistants conservés ; journaliser les anomalies sans modifier les dossiers réels.
- Tester les quatre espaces (Administrateur, Intervenant, Bénéficiaire, Client/DRH), Teams/Graph, planning/ICS, confidentialité BC, documents, emails, Qualité, signatures, émargements, connecteurs disponibles ; inscrire les réserves 13/17.

## 6. Recette manuelle des rappels configurables — protocole prudent

**Précondition :** utiliser un organisme de démonstration ou une fenêtre sans séances clients imminentes, car les valeurs enregistrées sont **générales à l'organisme**. Ne jamais simuler les horaires sur une véritable formation en cours.

1. Se connecter en ADMINISTRATEUR → **Paramètres → Général → Paramètres régionaux et horaires** ; sélectionner l'organisme de recette.
2. Dans « Programmation des rappels – formations en ligne (Teams) », renseigner `5` minutes puis `2` minutes ; enregistrer. Le réglage n'affecte pas les horodatages probants.
3. Créer/choisir **une action fictive ACTIVE avec Teams activé**, un créneau encore à venir (au moins 7–10 minutes devant soi), un bénéficiaire fictif et, si possible, un intervenant de recette disposant d'une boîte e-mail de test contrôlée.
4. **Sans cliquer sur « MAJ WORKER »**, attendre les créneaux T−5 puis T−2 et relever les réceptions exactes des deux e-mails et leurs libellés « 5 minutes » puis « 2 minutes ». Une préparation en base ne vaut pas un SMTP envoyé et un SMTP envoyé ne vaut pas réception en boîte.
5. Déplacer une **autre séance fictive** avant son premier rappel ; confirmer qu'aucun rappel de l'ancien horaire n'est envoyé, que les événements annulés restent traçables et que seuls les nouveaux horaires sont concernés.
6. Tester la sécurité : aucun doublon si le bouton manuel est utilisé après coup ; aucun envoi d'un rappel dépassé, aucun accès à l'action après révocation, confidentialité des destinataires préservée.
7. **REVENIR MANUELLEMENT à `120` puis `15` minutes**, enregistrer, puis vérifier que les valeurs restent celles-ci après reconnexion. Aucun système ne les remet automatiquement : cette étape est impérative après les essais.
8. Consigner dans le PV métier : dates/heure réelles de réception, destinataires test, statuts `communication_events`, logs du worker sans secrets, résultats négatifs et anomalies. Sur échec, vérifier le statut d'envoi avant de réessayer ; ne jamais rejouer aveuglément les messages marqués envoyés ou livraison inconnue.

## 7. Critère de clôture

Le ZIP J11 est un **livrable pour recette réelle VPS**. Il ne prouve pas à lui seul la livraison effective SMTP, le comportement navigateur PC/mobile, la restauration complète PRA ni la liaison réelle Contractualisation 13 / Gestion Clients 17. Le PV d'exploitation définitif n'est signé qu'après recette métier, levée ou arbitrage documenté des réserves et décision du propriétaire.

Règle finale : **une seule P5-RC2 à installer après GO**, un seul dépôt GitHub piloté par le propriétaire, un POINT DE REPRISE actualisé aux jalons.
