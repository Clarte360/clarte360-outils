# VPS / Hub Ready — Contractualisation 1.2.2

URL actuelle : https://contractualisation.clarte360.com
Dossier stable : `/opt/clarte360/clarte360-outils/clarte360-contractualisation-v1.0.0`
Service proposé : `clarte360-contractualisation.service`
Port interne proposé/documenté : `8502`, binding `127.0.0.1` (à confirmer contre la cartographie réelle avant toute modification VPS).
Aucun worker requis.

Secrets attendus : `[security].admin_password`; paramètres facultatifs consultant ; futur secret HMAC Hub. Aucun secret réel dans l'archive.

Données : la base XLSM n'est pas persistée côté VPS ; elle est chargée en mémoire. Les exports sont téléchargés par l'administrateur. Aucune donnée bénéficiaire ne doit être stockée dans l'arborescence Git.

Mise à jour : développement -> tests -> GitHub -> VPS -> tests VPS -> compilation -> restart -> recette. Aucun déploiement réalisé dans ce livrable.
