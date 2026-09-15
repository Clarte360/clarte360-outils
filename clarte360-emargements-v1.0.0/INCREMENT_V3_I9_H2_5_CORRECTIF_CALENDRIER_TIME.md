# I9 H2.5 — Correctif calendrier / collision `time`

## Incident réel
Références observées sur la base VPS : `5C3BFD8CD0` et `6954781688`.

Trace : `AttributeError: module 'time' has no attribute 'fromisoformat'` dans `calendar_tab()`.

## Cause
`app.py` importait `time` depuis `datetime`, puis `from services import *` réinjectait le module standard `time` importé dans `services.py`. Le symbole global `time` ne désignait donc plus `datetime.time` à l'exécution.

Comme les onglets Streamlit exécutent leur contenu lors du rendu de la fiche action, l'exception du calendrier interrompait également l'affichage d'autres onglets, donnant l'impression que plusieurs modules avaient crashé simultanément.

## Correctif
- alias explicite `time as dt_time` depuis `datetime` ;
- remplacement des appels horaires par `dt_time.fromisoformat(...)` et `dt_time(...)` ;
- test de non-régression empêchant le retour du motif fautif.

## Portée
Aucune migration de base. Aucun changement de données. Aucun changement VPS direct.
