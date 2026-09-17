# V2.8 — VALIDATION-SAISIES-VPS-HUB-READY

- validation centralisée des saisies et du JSON ;
- maintien de la compatibilité des JSON V2.7 conformes ;
- suppression du code consultant « Valeurs énergies » codé en dur : secret de déploiement ;
- contrôles email/texte/identifiants/cotes/domaines ;
- préparation VPS et service systemd ;
- URL cible `https://roue-valeurs.clarte360.com` ;
- contrat Hub I9-H1 pour prescription Administrateur/Intervenant vers bénéficiaire ;
- aucune modification des calculs de roue, règles de cotation ou logique Valeurs énergies.

# V2.8.1 — GARDE-FOU JSON HOMOGÉNÉISÉ

- garde-fou navigateur basé sur l'état métier réellement modifié ;
- téléchargement d'un JSON = nouveau point de sauvegarde de référence ;
- toute modification métier postérieure réarme automatiquement l'avertissement ;
- import d'un JSON = nouveau point de sauvegarde de référence ;
- les métadonnées techniques (sessions, timestamps, traces) n'arment pas l'alerte ;
- aucun changement des calculs, cotations, domaines ou de la logique Valeurs énergies.
