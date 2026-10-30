# GO22 RC3C — correctifs de recette et reprise

Date : 18/10/2026. Version : `0.4.0-go22-questionnaire-unique-rc3c`.

**Candidate de recette non validée. Dernière version officiellement validée : GO21 RC2.**

## Origine et portée

Cette candidate part de l'archive officielle RC3B du 17/10/2026, dont les 98 fichiers ont été vérifiés contre le manifeste de livraison. Elle traite les retours du 18/10/2026 : indication du champ de précision, question personnalisée du deuxième métier et impossibilité de transmettre après expiration du lien de lancement.

La recette reste en mode ACCOMPAGNEMENT, sur un dossier synthétique isolé. Aucune donnée réelle du bénéficiaire ayant signalé l'incident n'a été consultée sur son serveur de recette. Aucun déploiement, commit, push, service de production, référentiel normatif ou connecteur Hub/GDA n'est modifié par cette livraison. Les cinq rapports de démonstration restent fictifs. L'IA C-AV3 et le raccordement des vrais rapports restent ouverts.

## 1. Consigne de précision par piste

L'aperçu Accompagnateur et le formulaire Bénéficiaire utilisent la même consigne à la question 2 de chaque piste :

> Plusieurs réponses possibles. Si vous choisissez Je souhaite préciser, utilisez la zone Autres informations sur cette piste ou son contexte, située en bas de cette fiche.

Le nom de la zone de texte vient de la même constante dans les deux rendus. Cette zone concerne uniquement la piste dans laquelle elle est affichée.

Les questions restent lisibles dès l'ouverture de chaque fiche. La saisie des précisions est activée après la réponse à la première question d'intérêt. Aucun intérêt n'est présélectionné. Ce choix préalable évite d'accepter une précision qui ne pourrait pas encore être rattachée à une réponse valide dans le modèle existant.

## 2. Question publique et remarque privée

L'éditeur présente distinctement :

| Champ | Destination |
|---|---|
| Remarque privée de l'accompagnateur — non visible par le bénéficiaire | Préparation interne uniquement |
| Question 6 — contexte d'exercice, visible par le bénéficiaire | Question personnalisée de la piste concernée |
| Réponses proposées à la question 6 (une par ligne) | Choix proposés au bénéficiaire pour cette question |

Le parcours reste : modifier la fiche, **Enregistrer la fiche de cette piste**, vérifier **03 — Voir Q complet**, puis **04 — Verrouiller Q** et valider la mise à disposition. Une proposition d'adaptation doit être acceptée avant validation. Aucune remarque privée n'est rendue publique automatiquement.

L'aperçu projette les données publiques de Q et montre le contenu enregistré avant et après verrouillage. L'enregistrement d'une piste remplace cette piste à sa position d'origine ; il ne la retire plus pour l'ajouter en fin de liste. Q reste immuable après validation. Le schéma n'ajoute pas un bloc arbitraire de questions supplémentaires : la personnalisation porte sur la question de contexte existante.

La cause de l'absence observée dans le dossier réel ne peut pas être établie sans la saisie exacte et la version effectivement publiée. Les tests vérifient qu'une question personnalisée et enregistrée sur la deuxième piste apparaît bien chez le bénéficiaire ; ils ne prouvent pas quel champ avait été utilisé dans l'essai initial.

## 3. Lien de lancement et inactivité

RC3B vérifiait de nouveau l'expiration du lien à chaque interaction complète de l'application. Une personne répondant activement pouvait donc se retrouver bloquée à 900 secondes.

RC3C sépare les contrôles :

| Situation | Comportement |
|---|---|
| Nouvelle ouverture d'un lien | Vérification complète existante : signature, identifiants, rôle, scopes, expiration et TTL maximal de 900 secondes |
| Session déjà authentifiée, même lien et même clé | Poursuite possible après expiration du lien tant que l'inactivité ne dépasse pas le seuil configuré |
| Changement de lien, de clé ou de contexte | Purge des anciens widgets, puis nouvelle vérification complète |
| 60 minutes sans interaction reçue, configuration par défaut | Fermeture de la session ; reprise avec un nouveau lien |
| Contrôle automatique de synchronisation | Contrôle l'accès avant de lire la base ; ne compte pas comme activité utilisateur |

L'autorité d'accès est conservée uniquement dans la session serveur Streamlit, liée à l'empreinte du jeton exact et de la clé. Aucun cache global, aucune extension du TTL du jeton et aucun nouvel accès sans vérification ne sont introduits. Le contrôle d'inactivité est exécuté avant toute sauvegarde.

Dans le kit, les raccourcis `1_OUVRIR_ACCOMPAGNATEUR.cmd` et `2_OUVRIR_BENEFICIAIRE.cmd` renouvellent les liens du même dossier temporaire. Ils ne réinitialisent pas les réponses enregistrées. Le serveur temporaire conserve sa durée maximale de trois heures : ce délai distinct n'est pas prolongé par l'activité du formulaire.

## 4. Sauvegarde et transmission explicite

Le bandeau annonçait déjà une sauvegarde automatique, mais RC3B ne persistait le questionnaire qu'au clic sur ses boutons d'enregistrement. RC3C sauvegarde chaque changement valide effectivement reçu par l'application : choix et sortie de zone de texte, avec comparaison sémantique pour ne pas créer une version lorsque rien n'a changé.

La base serveur reste la source de vérité. Le buffer de session associe les réponses affichées à leur `row_version` d'origine ou à celle confirmée après leur dernière sauvegarde réussie. Une lecture plus récente de la base ne remplace pas cette version locale. Un conflit est bloqué et expliqué ; aucune fusion ni nouvelle tentative automatique ne peut écraser l'autre fenêtre. Le bouton de rechargement remplace volontairement les widgets de ce questionnaire par les réponses enregistrées.

Le parcours Chromium a également révélé une interruption possible entre le commit en base et son accusé dans l'état Streamlit. La sauvegarde attendue est désormais mémorisée avant son exécution. Le rendu suivant ne peut l'acquitter que si le questionnaire, la version serveur immédiatement suivante et l'intégralité du contenu sauvegardé correspondent exactement à cette attente. Il conserve alors les nouveaux champs saisis. Ce contrôle corrige un faux conflit avec sa propre sauvegarde ; il n'autorise pas l'adoption silencieuse d'une modification différente venant d'une autre fenêtre.

La configuration livrée `.streamlit/config.toml` fixe `runner.fastReruns = false`. Les interactions rapprochées attendent ainsi le prochain point de reprise du rendu courant, ce qui évite que deux exécutions du même écran démarrent simultanément une transaction avec le même buffer. Cette sérialisation ne remplace ni l'accusé de sauvegarde ni le contrôle optimiste entre sessions. Lancer l'application depuis son répertoire afin de charger cette configuration, comme le fait le kit fourni.

Les indicateurs de fin d'étape ne sont jamais activés par une sauvegarde automatique. Une modification de C-AV1 invalide la fin de C-AV1 et de C-AV2 ; une modification de C-AV2 invalide sa fin et la confirmation finale. Le contenu déjà saisi dans l'autre partie est conservé. Revenir vers C-AV1 traite le dernier texte de C-AV2 avant de changer de page.

La transmission définitive utilise la version effectivement sauvegardée et exige les deux parties terminées, la confirmation explicite et le scope de validation. R1 reste unique et immuable ; R2 demeure une revalidation conjointe distincte. Aucune nouvelle passation n'est déclenchée pour C-AV3.

## 5. Vérification et limites

Les tests RC3C complètent la suite de 147 tests RC3B avec 27 contrôles d'accès/session, 19 contrôles de brouillon et 5 parcours Streamlit AppTest : **198 tests au total**. Les scénarios comprennent l'expiration simulée au-delà de 900 secondes, le refus d'une nouvelle ouverture expirée, la reprise d'un brouillon, une collision SQLite réellement simultanée, la personnalisation de la deuxième piste, la note privée exclue, les modifications avant transmission et la réception des dernières réponses.

Le rapport externe de livraison consigne les tests sur l'archive réextraite, la recette Chromium locale et les vérifications statiques du kit. Il distingue ces résultats des opérations non exécutées : lancement PowerShell sur le PC de Dominique, recette réelle sur son VPS temporaire et validation ergonomique par le bénéficiaire.

L'autosauvegarde ne peut pas garantir un texte jamais transmis par le navigateur. Avant de fermer, quitter la dernière zone de texte et vérifier l'absence d'erreur d'enregistrement. Une réponse qui échoue à la validation reste affichée dans la fenêtre, mais n'est pas annoncée comme enregistrée avec succès.

Le nouveau kit RC3C crée son propre dossier fictif. Il ne récupère pas automatiquement les réponses saisies dans une session RC3B. Pour reprendre cet ancien essai tant que son serveur existe, utiliser les raccourcis du kit RC3B correspondant ; ne pas attendre d'un nouveau kit qu'il importe cette base temporaire.

## Référentiels relus

- Framework Clarté360 V5, notamment sections 45.4–45.8 et 54 : activité, inactivité, reprise et sauvegarde.
- Addendum V4.2 PIP/RIASEC/O*NET et secrets centralisés, en complément du maître V5.
- Framework VPS V1.5 : identité et organisation stables, non modifiées.
- CDC GO03 V1.0, référentiel fonctionnel GO04, UX Accompagnateur GO05, UX Bénéficiaire GO06, états/droits/validations GO07 et architecture GO15.
- Protocole de livraison du 09/10/2026 et POINT DE REPRISE officiel consulté le 18/10/2026.

Les références et preuves sont détaillées dans le rapport de livraison externe. Le présent document décrit la candidate et ne modifie aucun référentiel maître.
