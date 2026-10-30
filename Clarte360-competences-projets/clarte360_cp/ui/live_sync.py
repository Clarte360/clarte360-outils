from __future__ import annotations

import os
from datetime import datetime

from clarte360_cp.application.live_sync import build_live_sync, record_sync_probe
from clarte360_cp.connectors import LaunchTokenError
from clarte360_cp.ui.entry import resolve_launch_context


def _fmt(value: datetime | None) -> str:
    if value is None:
        return "—"
    try:
        return value.strftime("%H:%M:%S")
    except Exception:
        return str(value)


def render_live_sync_status(ctx, case_id: str, *, compact: bool = True) -> None:
    """Petit fragment auto-rafraîchi. Il relit la source serveur sans rerun complet de la page."""
    import streamlit as st

    @st.fragment(run_every=2.0)
    def _live_fragment() -> None:
        # Une minuterie ne constitue pas une activité. Contrôler l'inactivité
        # avant toute lecture, puis faire afficher la fermeture par l'app.
        try:
            current = resolve_launch_context()
        except LaunchTokenError:
            st.rerun(scope="app")
            return
        if current != ctx or st.session_state.get("case_id") != case_id:
            st.rerun(scope="app")
            return
        live = build_live_sync(case_id)
        if compact:
            st.caption(f"Dossier actualisé en direct · dernière mise à jour {_fmt(live.latest_change_at)}")
        else:
            st.info(f"Dossier actualisé en direct · dernière mise à jour {_fmt(live.latest_change_at)}")

        if os.getenv("CLARTE360_GO21_SYNC_PROBE", "").strip() == "1":
            role = ctx.actor_role.value
            st.caption("Recette technique temporaire — invisible en production")
            if live.latest_probe_at:
                st.write(
                    f"**Dernier signal partagé :** {live.latest_probe_label or 'signal'} "
                    f"({live.latest_probe_actor or 'acteur'}, {_fmt(live.latest_probe_at)})"
                )
            label = "Signal depuis l'accompagnateur" if role == "ACCOMPAGNATEUR" else "Signal depuis le bénéficiaire"
            if st.button("Envoyer un signal de synchronisation", key=f"sync_probe_{role}_{case_id}", use_container_width=False):
                record_sync_probe(case_id, actor_type=role, actor_id=ctx.actor_id, label=label)
                st.rerun(scope="fragment")

    _live_fragment()
