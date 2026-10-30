from __future__ import annotations

from clarte360_cp.domain.enums import ActorRole


def render_home(ctx, bootstrap) -> None:
    import streamlit as st

    st.caption(f"Action n° {ctx.action_no or ctx.action_id} · Accès ouvert depuis Gestion des Actions")

    if ctx.actor_role is ActorRole.ACCOMPAGNATEUR:
        from clarte360_cp.ui.accompagnateur import render_accompanist_app
        render_accompanist_app(ctx, bootstrap)
        return

    if ctx.actor_role is ActorRole.BENEFICIAIRE:
        from clarte360_cp.ui.beneficiaire import render_beneficiary_app
        render_beneficiary_app(ctx, bootstrap)
        return

    st.error("Rôle de lancement non reconnu pour cette application.")
    st.stop()
