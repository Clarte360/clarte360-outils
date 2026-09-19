from __future__ import annotations
from collections import Counter

DIMS = ("R","I","A","S","E","C")
BLOCKS = ("ACT","SIT","ENV")
FACETS = {f"{d}{n}" for d in DIMS for n in range(1,6)}

def validate_bank(bank: dict) -> list[str]:
    errors=[]; items=bank.get("items",[])
    ids=[x.get("item_id") for x in items]
    if len(items)!=72: errors.append(f"La banque doit contenir 72 items, reçu {len(items)}.")
    if len(ids)!=len(set(ids)): errors.append("Les IDs item ne sont pas uniques.")
    dc=Counter(x.get("dimension") for x in items)
    if set(dc)!=set(DIMS) or any(dc[d]!=12 for d in DIMS): errors.append(f"Répartition dimensions invalide: {dict(dc)}")
    fc=Counter(x.get("facette") for x in items)
    if set(fc)!=FACETS or any(fc[f]<2 for f in FACETS): errors.append("Les 30 facettes doivent être couvertes par au moins 2 items.")
    if any(x.get("bloc") not in BLOCKS for x in items): errors.append("Bloc inconnu dans la banque.")
    scale=bank.get("response_scale",{})
    if set(scale)!={"1","2","3","4","5"}: errors.append("Échelle de réponse invalide.")
    for x in items:
        if not all(x.get(k) for k in ("item_id","item_version","bloc","dimension","facette","texte_fr")): errors.append(f"Item incomplet: {x.get('item_id')}")
    return errors

def assert_valid_bank(bank: dict) -> None:
    errors=validate_bank(bank)
    if errors: raise ValueError(" | ".join(errors))
