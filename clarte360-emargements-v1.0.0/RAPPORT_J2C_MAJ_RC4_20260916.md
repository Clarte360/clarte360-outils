# J2C MAJ RC4 — 16/09/2026

Correctif ciblé demandé après recette RC3.

## 1. Outils prescrits autonomes
- PIP RIASEC / O*NET conserve son lancement signé spécifique.
- Tous les autres outils externes restent autonomes après validation de la prescription : le Hub Clarté360 ouvre l'URL de l'application sans exiger le secret HMAC du Hub.
- L'application externe conserve donc son propre système d'identification, de sauvegarde et de reprise.

## 2. Espace bénéficiaire — bandeaux rouges intermittents
- Correction d'un conflit Streamlit avéré : les mêmes documents étaient rendus dans plusieurs onglets avec la même clé de téléchargement.
- Les clés sont désormais propres à chaque onglet (administratif / cours / archives), ce qui évite les erreurs `DuplicateElementKey` qui pouvaient remonter sous forme de bandeau incident.

## 3. Contresignature intervenant
- Alignement UX avec la signature bénéficiaire : deux modes maintenus et explicités :
  - signature manuscrite (canvas),
  - nom et prénom + certification.
- Clé canvas renouvelée pour éviter la réutilisation d'un composant Streamlit obsolète après déploiement.

## 4. Bouton MAJ WORKER
- Ajout dans la barre latérale administrateur : `MAJ WORKER — toutes les actions`.
- Recalcule de façon idempotente les files des actions ACTIVE / A_CLOTURER :
  - tokens et événements d'émargement,
  - échéances qualité,
  - rappels Teams H-2 et H-15 bénéficiaires + intervenants,
  - demandes de contresignature devenues actionnables.
- Les événements déjà envoyés sont préservés ; les événements en échec/annulés/non envoyés sont réparés.
- Le bouton ne remplace pas le service systemd : le worker continue à fonctionner en arrière-plan, application fermée et sans session administrateur.

## 5. Non-régression
- Calendrier et Teams ne sont pas restructurés dans ce correctif.
- Le moteur PIP RIASEC reste inchangé.
