from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from clarte360_cp.connectors.gestion_actions import LaunchTokenError, verify_launch_token
from clarte360_cp.domain.launch import LaunchContext
from clarte360_cp.framework.timeout import is_timed_out


_AUTH_SESSION = "_cp_authenticated_launch"
_EXPIRED_LINKS = "_cp_expired_launch_bindings"
_TIMEOUT_LINK = "_cp_last_timeout_binding"


class SessionExpiredError(LaunchTokenError):
    """La session doit être réouverte avec un nouveau lien signé."""


@dataclass(frozen=True)
class _AuthenticatedLaunch:
    binding: str
    context: LaunchContext


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def session_defaults(*, now: datetime | None = None) -> dict:
    return {
        "session_id": str(uuid4()),
        "navigation_page": "home",
        "last_activity_at": now_iso(now),
        "case_id": None,
        "case_row_version": None,
        "launch_context": None,
    }


def invalidate_session(state, *, now: datetime | None = None, retire_current: bool = False) -> None:
    """Efface les widgets et le contexte local, jamais les réponses enregistrées.

    L'empreinte d'un lien dont la session est inactive reste bloquée jusqu'à
    l'expiration initiale du lien. Cela empêche de réouvrir la même session avec
    le même lien lorsque le timeout configuré est inférieur au TTL du lien.
    Aucune donnée nominative ni aucun jeton brut n'est conservé ici.
    """
    current = now or datetime.now(timezone.utc)
    expired = dict(state.get(_EXPIRED_LINKS, {}))
    last_timeout = state.get(_TIMEOUT_LINK)
    previous = state.get(_AUTH_SESSION)
    if retire_current and isinstance(previous, _AuthenticatedLaunch):
        expired[previous.binding] = previous.context.exp
        last_timeout = previous.binding
    expired = {binding: exp for binding, exp in expired.items() if exp >= current.timestamp()}
    for key in list(state):
        del state[key]
    if expired:
        state[_EXPIRED_LINKS] = expired
    if last_timeout:
        state[_TIMEOUT_LINK] = last_timeout


def _inactive(state, *, now: datetime, limit_minutes: int) -> bool:
    return not state.get("last_activity_at") or is_timed_out(
        state.get("last_activity_at"), now=now, limit_minutes=limit_minutes,
    )


def resolve_session_launch(state, token: str, signing_key: str, *,
                           limit_minutes: int = 60, now_epoch: int | None = None) -> LaunchContext:
    """Vérifie le lien à l'entrée, puis conserve l'autorité dans cette session.

    Le TTL de 900 secondes reste imposé par verify_launch_token pour toute
    nouvelle ouverture. Une session déjà établie dépend de son inactivité,
    et non de l'expiration du lien qui l'a ouverte. L'empreinte lie la session
    au jeton exact et à la clé de validation courante : leur changement impose
    une vérification complète et efface tous les anciens widgets.

    Cette fonction ne compte jamais comme une activité utilisateur : elle peut
    donc aussi protéger les fragments automatiques sans prolonger la session.
    """
    now = datetime.now(timezone.utc) if now_epoch is None else datetime.fromtimestamp(now_epoch, timezone.utc)
    binding = hashlib.sha256((signing_key + "\0" + token).encode("utf-8")).hexdigest()
    previous = state.get(_AUTH_SESSION)
    if isinstance(previous, _AuthenticatedLaunch):
        inactive = _inactive(state, now=now, limit_minutes=limit_minutes)
        if hmac.compare_digest(previous.binding, binding):
            if inactive:
                invalidate_session(state, now=now, retire_current=True)
                raise SessionExpiredError("Votre session a expiré après une période sans interaction.")
            if state.get("launch_context") != previous.context:
                invalidate_session(state, now=now)
                raise LaunchTokenError("Le contexte de session a changé. Ouvrez un nouveau lien sécurisé.")
            return previous.context
        invalidate_session(state, now=now, retire_current=inactive)
    else:
        invalidate_session(state, now=now)

    if binding == state.get(_TIMEOUT_LINK) or binding in state.get(_EXPIRED_LINKS, {}):
        raise SessionExpiredError("Votre session a expiré. Ouvrez un nouveau lien sécurisé pour reprendre.")
    # La vérification ordinaire reste obligatoire, y compris après un timeout,
    # dans un nouvel onglet/navigateur, ou après tout changement du lien ou clé.
    launch = verify_launch_token(token, signing_key, now_epoch=int(now.timestamp()))
    state.pop(_TIMEOUT_LINK, None)
    state.update(session_defaults(now=now))
    state["launch_context"] = launch
    state[_AUTH_SESSION] = _AuthenticatedLaunch(binding, launch)
    return launch


def reconcile_session_state(state: dict, launch, case_id: str, case_row_version: int) -> dict:
    """Reconstruit l'état UI à partir du contexte signé et de la persistance."""
    previous_launch = state.get("launch_context")
    previous_case = state.get("case_id")
    if ((previous_launch is not None and previous_launch != launch)
            or (previous_case is not None and previous_case != case_id)):
        authenticated = state.get(_AUTH_SESSION)
        invalidate_session(state)
        if isinstance(authenticated, _AuthenticatedLaunch) and authenticated.context == launch:
            state[_AUTH_SESSION] = authenticated
    for key, value in session_defaults().items():
        state.setdefault(key, value)
    state["launch_context"] = launch
    state["case_id"] = case_id
    state["case_row_version"] = case_row_version
    return state


def initialize_session(launch, case_id: str, case_row_version: int) -> None:
    import streamlit as st
    reconcile_session_state(st.session_state, launch, case_id, case_row_version)


def touch_activity(state=None, *, now: datetime | None = None) -> None:
    """À appeler lors d'un rerun utilisateur, jamais depuis une minuterie."""
    if state is None:
        import streamlit as st
        state = st.session_state
    state["last_activity_at"] = now_iso(now)
