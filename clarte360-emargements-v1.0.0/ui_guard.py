from __future__ import annotations

import traceback
import uuid
from typing import Callable, TypeVar

from db import audit

T = TypeVar("T")


def log_ui_exception(engine, context: str, exc: Exception, *, action_id=None, actor="system",
                     entity_type=None, entity_id=None) -> str:
    """Journalise le détail technique et retourne une référence courte affichable à l'utilisateur."""
    ref = uuid.uuid4().hex[:10].upper()
    details = {
        "error_ref": ref,
        "context": context,
        "exception_type": type(exc).__name__,
        "message": str(exc)[:800],
        "traceback": traceback.format_exc()[-6000:],
    }
    try:
        audit(engine, "UI_MODULE_ERROR", action_id, actor, entity_type, entity_id, details)
    except Exception:
        # L'échec de journalisation ne doit jamais provoquer une seconde panne utilisateur.
        pass
    return ref


def safe_call(engine, context: str, fn: Callable[[], T], *, action_id=None, actor="system",
              entity_type=None, entity_id=None) -> tuple[bool, T | None, str | None]:
    try:
        return True, fn(), None
    except Exception as exc:
        ref = log_ui_exception(engine, context, exc, action_id=action_id, actor=actor,
                               entity_type=entity_type, entity_id=entity_id)
        return False, None, ref


def user_message(ref: str | None = None, *, subject: str = "Cette fonction") -> str:
    msg = f"{subject} est momentanément indisponible. Les autres fonctions restent accessibles."
    if ref:
        msg += f" Référence incident : {ref}."
    return msg
