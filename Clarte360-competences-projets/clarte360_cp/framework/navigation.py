from __future__ import annotations

from clarte360_cp.ui.spec import ACCOMPAGNATEUR_PAGES, BENEFICIARY_PAGES

VALID_PAGES = frozenset({"home", "timeout", *ACCOMPAGNATEUR_PAGES, *BENEFICIARY_PAGES})


def set_page(state: dict, page: str) -> None:
    """Navigation UI uniquement : ne valide, ne publie et ne mute aucun objet métier."""
    if page not in VALID_PAGES:
        raise ValueError(f"Page inconnue: {page}")
    state["navigation_page"] = page
