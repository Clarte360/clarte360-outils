# I9-H — Consolidation finale / Candidate de recette

Date : 12/09/2026
Base : I9-G

## Objectif

Clore la séquence I9-A → I9-H sans modifier le VPS : durcissement transversal, observabilité métier, contrôle de candidate, documentation de recette et non-régression complète.

## Évolutions

- ajout d'un diagnostic I9 en lecture seule dans Paramètres ;
- contrôles de disponibilité du socle, de l'URL publique, de la structure applicative et de la présence des tests ;
- contrôles non bloquants des connecteurs Email, Microsoft 365 / Teams et PIP ;
- aucune valeur de secret, identifiant Microsoft ni détail technique sensible affiché par le diagnostic ;
- ajout de `release_check.py` pour compilation, imports principaux et suite pytest avant commit/push ;
- tests de durcissement anti-traceback / anti-secret et isolation des connecteurs optionnels ;
- maintien du principe : une indisponibilité Teams, PIP ou SMTP ne bloque pas le Hub ni les autres modules.

## Règles de déploiement

I9-H n'effectue aucune modification automatique du VPS. La séquence reste : PC → GitHub Desktop → Commit/Push → confirmation PUSH FAIT → git pull VPS → tests → compilation → restart → contrôles → recette.

## Hors périmètre

- aucune modification des secrets VPS ;
- aucune création/modification Entra ;
- aucun déploiement ;
- aucune recette réseau réelle Teams/PIP/SMTP ;
- aucune modification de l'application Contractualisation.
