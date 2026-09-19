# CLARTÉ360 — PIP RIASEC / O*NET — RAPPORT JALON B

Date : 18/09/2026
Base : Jalon A1 récupéré depuis OneDrive
Périmètre : RGPD, navigation, sauvegarde, reprise, timeout

## 1. RGPD
- Le consentement est associé à `RGPD_TEXT_VERSION`.
- Une version déjà acceptée n'est plus demandée de nouveau.
- La date, l'heure, la version et le consentement étude restent conservés.
- `rgpd_acceptance` est maintenant restauré explicitement depuis les sauvegardes JSON et les sauvegardes serveur accompagnement.
- La page RGPD peut être consultée pendant une passation puis revenir à la page utile sans remise à zéro.
- En PUBLIC, les informations RGPD sont présentées avant l'identité et la vérification e-mail conformément au CDC.

## 2. Navigation et non-réinitialisation
- Accueil et RGPD n'effacent ni réponses ni progression.
- Le bouton de démarrage détecte une passation déjà existante et devient une reprise.
- Le parcours PIP/O*NET existant est conservé lorsqu'une passation a commencé.
- Une fonction d'inférence de reprise détermine le bon écran selon la progression réelle.

## 3. Sauvegarde et reprise
- La sauvegarde conserve réponses, index, parcours PIP/O*NET, timing du choix O*NET, consentements et ressenti.
- La restauration réinitialise l'horloge d'activité et retire l'état timeout.
- La `bank_version` enregistrée peut être utilisée pour charger la banque runtime correspondante si elle est disponible.

## 4. Timeout
- Avant bascule vers timeout, la dernière page utile est mémorisée.
- Le JSON généré depuis timeout utilise cette dernière page utile comme cible de reprise.
- Un ancien JSON contenant `navigation_page=timeout` est accepté puis réparé automatiquement.
- Message CDC intégré : travail non perdu, ne pas fermer avant téléchargement.
- Bouton : `TÉLÉCHARGER MA SAUVEGARDE AVANT DE QUITTER`.
- L'utilisateur est informé qu'un seul téléchargement suffit.
- L'import JSON et le bouton `Reprendre` sont disponibles directement sur l'écran timeout.

## 5. Non-régression
- Banque active inchangée : PIP-BANK-0.5 / 72 items.
- Tableur maître inchangé : V0.6 ACTIF.
- Scoring inchangé.
- O*NET inchangé hors conservation renforcée de son état et de son timing.
- Aucun changement apporté à Gestion des Actions dans ce chantier.

## 6. Limites de ce jalon
- Les tests automatisés ne remplacent pas la recette navigateur réelle.
- Aucun déploiement VPS n'est réalisé à ce stade.
- Les évolutions PUBLIC/ACCOMPAGNEMENT plus larges restent au Jalon C.
