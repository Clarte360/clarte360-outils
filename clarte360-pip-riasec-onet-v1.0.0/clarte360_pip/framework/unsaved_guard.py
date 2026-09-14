from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping



_GUARD_KEYS = (
    "rgpd_acceptance",
    "public_identity",
    "public_access_verified",
    "public_marketing_opt_in",
    "public_interests",
    "public_other_interest",
    "study_consent",
    "onet_selected_timing",
    "journey",
    "pip_state",
    "pip_scoring",
    "onet_state",
    "feeling",
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def public_work_fingerprint(session_state: Mapping[str, Any]) -> str:
    payload = {key: _jsonable(session_state.get(key)) for key in _GUARD_KEYS}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def public_work_started(session_state: Mapping[str, Any]) -> bool:
    pip_state = session_state.get("pip_state") or {}
    onet_state = session_state.get("onet_state") or {}
    feeling = session_state.get("feeling") or {}
    return bool(
        (isinstance(pip_state, dict) and pip_state.get("answers"))
        or (isinstance(onet_state, dict) and onet_state.get("answers"))
        or feeling
    )


def mark_public_work_saved(session_state: Any) -> None:
    session_state["public_last_saved_fingerprint"] = public_work_fingerprint(session_state)


def public_has_unsaved_work(session_state: Mapping[str, Any]) -> bool:
    if not public_work_started(session_state):
        return False
    current = public_work_fingerprint(session_state)
    saved = session_state.get("public_last_saved_fingerprint")
    return saved != current


def render_browser_unsaved_guard(active: bool) -> None:
    import streamlit.components.v1 as components

    flag = "true" if active else "false"
    components.html(
        f"""
<script>
(function() {{
  const target = window.parent;
  const key = "__clarte360_beforeunload_guard__";
  try {{
    if (target[key]) {{
      target.removeEventListener("beforeunload", target[key]);
      target[key] = null;
    }}
    if ({flag}) {{
      const handler = function(event) {{
        event.preventDefault();
        event.returnValue = "";
        return "";
      }};
      target[key] = handler;
      target.addEventListener("beforeunload", handler);
    }}
  }} catch (e) {{
    /* Le navigateur peut restreindre l'accès parent : l'application reste fonctionnelle. */
  }}
}})();
</script>
""",
        height=0,
        width=0,
    )
