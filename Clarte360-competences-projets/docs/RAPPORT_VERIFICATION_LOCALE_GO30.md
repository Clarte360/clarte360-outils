# GO30 — Rapport de vérification locale des candidates coordonnées

Date de préparation : 29/10/2026. Statut : candidate pour déploiement en VPS de recette; GO30 non déclaré validé.

## Origines

- Compétences & Projets : recette locale 0.4.29 GO29, non déployée, mise à jour en `0.4.30-go30-dual-candidate`.
- Gestion des Actions : `clarte360-gestion-actions-v3.0.0-P5-RECETTE-RC2.zip` uniquement, mise à jour en `3.0.0-P5-RECETTE-RC3-GO30-CANDIDAT`.
- Le candidat GO4 n’a pas servi de source. Les ZIP de base restent inchangés.

## Contrôles exécutés

- Compilation Python de `app.py`, de la navigation GDA et du constructeur CP_V1 : réussie.
- Validation JSON des identités d’application et du catalogue d’outils : réussie.
- Contrôle statique de la navigation : l’entrée C&P existe pour bénéficiaire avec action sélectionnée, intervenant et administrateur; elle est absente pour le bénéficiaire sans action sélectionnée.
- Contrôle statique du routage : le bénéficiaire est dirigé vers l’accès dédié; le code C&P est exclu de Mes outils et de l’ancien lancement générique.
- Le numéro d’action métier est transmis dans le contexte CP_V1 signé et affiché dans C&P; un contrôle de parsing direct a accepté le nouveau contexte et conservé la compatibilité d’un ancien jeton sans ce champ.
- Contrôle ergonomique A3 : l’ordre visible met les résultats détaillés avant le plan d’action. Les cinq étapes du bénéficiaire portent des teintes pastel douces; l’action visible dans le contexte accompagnateur utilise le numéro métier.
- Revue complémentaire en posture utilisateur : la page Documents ne prétend plus que GDA est absent; elle dirige vers « Vérifier les sources et le CV » et distingue ce qui est visible dans le dossier C&P de l’inventaire réellement partagé. Les références, octets, type MIME et empreintes techniques sont repliés derrière une commande facultative; le déposant et les éléments de parcours sont affichés sans identifiants internes.
- Les libellés de sources ne prétendent plus importer automatiquement le contenu des pièces. La saisie manuelle des références reste présentée comme telle.
- La compilation complète a détecté puis corrigé une indentation incorrecte dans l’écran bénéficiaire C-AV. La compilation Python des deux candidats passe maintenant.
- Contrôle de l’accès IA : C-AV3, le CV et le rapprochement ROME nécessitent une action explicite et une confirmation d’information/accord du bénéficiaire, reliée à la version des données concernées. L’appel C-AV3 filtre les champs, plafonne le payload à 48 Kio, utilise `store=False`, limite délai/reprises et valide les sorties.
- Contrôle direct synthétique du connecteur C-AV3 : payload augmenté refusé avant l’appel fournisseur, champs hors liste non transmis, payload surdimensionné refusé. Le service réel n’a pas été appelé.
- Sauvegarde progressive : les réponses bénéficiaire C-AV1/C-AV2, les formulations C-AV1/C-AV2 préparées par l’intervenant et les corrections R2 en séance sont enregistrées côté serveur à chaque changement de champ; les étapes sont navigables avant leur validation définitive. R1 reste immuable après envoi, et une revalidation en séance produit R2. Le mode opératoire VPS contient les contrôles de reprise depuis la dernière version confirmée sur le serveur.
- Délai de session : 60 minutes par défaut et minimum, jusqu’à 240 minutes configurables. Le TTL de 15 minutes concerne uniquement le lien initial de lancement, pas une session déjà établie. La recette exige aussi un reverse proxy HTTPS maintenant le WebSocket Streamlit et des délais proxy lecture/écriture d’au moins 3 600 secondes.
- Le raccourci C&P GDA est contextualisé sur l’action et apparaît verrouillé avant prescription. L’entrée générique de gauche est masquée hors de cet espace; l’autorisation serveur et le contexte signé restent les contrôles d’accès.
- L’écran administrateur fournit des contrôles à la demande de clé configurée (valeur masquée), catalogue, bridge GDA et santé C&P; aucun contrôle réseau réel VPS n’a été fait ici.
- Contrôle de package et d’intégrité ZIP : voir les manifestes SHA-256 associés.

## Périmètre de sauvegarde progressive — point de conformité

Le champ par champ est implémenté dans le parcours C-AV : préparation du questionnaire par l’intervenant avant publication, brouillon bénéficiaire C-AV1/C-AV2 avant R1, puis brouillon R2 de relecture en séance. L’envoi R1 est clairement irréversible et reste en lecture seule; la publication Q verrouille le questionnaire.

La sauvegarde champ par champ est limitée aux écrans C-AV indiqués plus haut. Elle n’est pas généralisée aux sources et CV, idées et repères préliminaires, directions, recherche/choix ROME, enrichissement du parcours, investigations, comparaison, décision, plan d’action, résultats, synthèse et suivi. Ces écrans utilisent des commandes explicites de brouillon/partage/transmission; une saisie non soumise peut rester seulement dans le navigateur. C’est un écart bloquant pour l’exigence formulée d’enregistrer chaque champ éditable avant tout envoi. La candidate n’est donc pas conforme RC tant que cette sauvegarde n’est pas généralisée et vérifiée pour l’intervenant et le bénéficiaire.

## Contrôles non exécutés / limites connues

- Les suites pytest complètes ne sont pas exécutées : `pytest` n’est pas installé dans l’environnement disponible. La compilation et les contrôles directs synthétiques indiqués ci-dessus ont été exécutés.
- Aucun essai navigateur, API ROME, bridge CP_V1, secret, scopes, rôle réel, multi-action, document, impression, rollback ou parcours humain n’a été réalisé sur le VPS.
- Il n’existe donc pas encore de constat « anomalies bloquantes = 0 » et aucun GO30 RC n’est annoncé.

## Résultat

Les packages restent des candidates d’audit. Elles ne peuvent pas être qualifiées RC pour l’exigence de sauvegarde champ par champ sur tout A3 tant que ces écrans n’enregistrent pas leurs brouillons progressivement. Le rapport GO30 RC devra être complété après correction, déploiement isolé, exécution du mode opératoire, contrôle installation/rollback et résolution de toute anomalie bloquante.
