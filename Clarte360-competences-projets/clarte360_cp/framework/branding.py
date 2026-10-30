from __future__ import annotations


def apply_framework_css() -> None:
    import streamlit as st
    from .config import DARK_TEXT, LIGHT_TEAL, OFFICIAL_TEAL
    st.markdown(
        f"""
<style>
:root {{ --clarte-teal: {OFFICIAL_TEAL}; --clarte-light: {LIGHT_TEAL}; --clarte-text: {DARK_TEXT}; }}
h1,h2,h3 {{ color:{OFFICIAL_TEAL}; }}
div.stButton > button[kind="primary"] {{ background:{OFFICIAL_TEAL}; border-color:{OFFICIAL_TEAL}; }}
div.stButton > button {{ border-radius:.65rem; min-height:2.7rem; }}
.clarte-box {{ border-left:6px solid {OFFICIAL_TEAL}; background:{LIGHT_TEAL}; padding:1rem; border-radius:.55rem; color:{DARK_TEXT}; }}
.clarte-muted {{ color:#5f6b6b; font-size:.92rem; }}
.clarte-context-bar {{ display:grid; grid-template-columns:1.35fr 1.15fr 1fr .9fr .9fr; gap:.65rem; align-items:center; padding:.7rem .9rem; margin:0 0 1rem 0; border:1px solid #dbe8e8; border-radius:.75rem; background:#fbfdfd; }}
.clarte-context-bar strong {{ color:{DARK_TEXT}; font-size:.9rem; }}
.clarte-context-bar span {{ color:#667575; font-size:.82rem; }}
.clarte-next-action {{ border:1px solid #b9dada; border-left:6px solid {OFFICIAL_TEAL}; border-radius:.75rem; padding:1rem 1.1rem; background:{LIGHT_TEAL}; margin:.25rem 0 .75rem 0; }}
.clarte-eyebrow {{ color:#4d7070; font-size:.76rem; font-weight:700; letter-spacing:.08em; }}
.clarte-next-title {{ color:{DARK_TEXT}; font-size:1.25rem; font-weight:700; margin:.25rem 0; }}
.clarte-kpi {{ min-height:105px; border:1px solid #dbe8e8; border-radius:.75rem; padding:.8rem; background:white; }}
.clarte-kpi span, .clarte-kpi small {{ display:block; color:#667575; }}
.clarte-kpi strong {{ display:block; color:{DARK_TEXT}; font-size:1.35rem; margin:.15rem 0; }}
.clarte-document-card, .clarte-source-card, .clarte-card {{ display:flex; flex-direction:column; gap:.25rem; border:1px solid #dbe8e8; border-radius:.75rem; padding:.85rem .95rem; background:white; margin:0 0 .65rem 0; }}
.clarte-document-card strong, .clarte-source-card strong, .clarte-card strong {{ color:{DARK_TEXT}; }}
.clarte-document-card span, .clarte-source-card span, .clarte-card span {{ color:{OFFICIAL_TEAL}; font-weight:600; }}
.clarte-document-card small, .clarte-source-card small, .clarte-card small {{ color:#667575; }}
.clarte-status-line {{ display:flex; justify-content:space-between; align-items:center; gap:1rem; border:1px solid #dbe8e8; border-radius:.65rem; padding:.7rem .9rem; margin-bottom:1rem; background:#fbfdfd; }}
.clarte-status-line span {{ color:{OFFICIAL_TEAL}; font-weight:700; }}
.clarte-question {{ display:flex; flex-direction:column; gap:.45rem; border-left:6px solid {OFFICIAL_TEAL}; background:{LIGHT_TEAL}; border-radius:.7rem; padding:1rem; margin-bottom:1rem; }}
.clarte-question span {{ color:#4d7070; font-size:.8rem; font-weight:700; }}
.clarte-question strong {{ color:{DARK_TEXT}; font-size:1.15rem; }}
.clarte-question small {{ color:#667575; }}
section[data-testid="stSidebar"] button {{ text-align:left; justify-content:flex-start; }}
.clarte-beneficiary-header {{ display:grid; grid-template-columns:1.3fr 1fr .8fr; gap:.75rem; align-items:center; padding:.75rem .9rem; margin:0 0 .25rem 0; border:1px solid #dbe8e8; border-radius:.8rem; background:#fbfdfd; }}
.clarte-beneficiary-header strong {{ color:{DARK_TEXT}; font-size:.95rem; }}
.clarte-beneficiary-header span {{ color:#667575; font-size:.85rem; }}
.clarte-beneficiary-next {{ margin-top:.8rem; }}
.clarte-duration {{ margin-top:.6rem; color:#4d7070; font-size:.86rem; font-weight:600; }}
.clarte-stage-line {{ display:flex; flex-wrap:wrap; align-items:center; gap:.45rem; margin:.25rem 0 1rem 0; }}
.clarte-stage, .clarte-stage-current {{ display:inline-block; padding:.34rem .68rem; border-radius:999px; border:1px solid #dbe8e8; font-size:.82rem; }}
.clarte-stage-0 {{ color:#3e596f; background:#eaf3fb; border-color:#cbddec; }}
.clarte-stage-1 {{ color:#49644b; background:#edf5e9; border-color:#d2e2c9; }}
.clarte-stage-2 {{ color:#6b5b3e; background:#faf2dc; border-color:#ebdfb8; }}
.clarte-stage-3 {{ color:#695270; background:#f4ebf7; border-color:#e2d2e9; }}
.clarte-stage-4 {{ color:#3e6261; background:#e7f4f1; border-color:#c6e2dc; }}
.clarte-stage-current {{ color:{DARK_TEXT}; font-weight:750; box-shadow:0 0 0 2px white, 0 0 0 3px #647b7b; }}
.clarte-stage-sep {{ color:#93a5a5; }}
.clarte-journey-card, .clarte-action-card, .clarte-readonly {{ display:flex; flex-direction:column; gap:.3rem; border:1px solid #dbe8e8; border-radius:.8rem; padding:.9rem 1rem; background:white; margin:0 0 .55rem 0; }}
.clarte-journey-card strong, .clarte-action-card strong, .clarte-readonly strong {{ color:{DARK_TEXT}; }}
.clarte-journey-card span, .clarte-action-card span, .clarte-readonly span {{ color:{OFFICIAL_TEAL}; font-weight:700; }}
.clarte-journey-card small, .clarte-action-card small, .clarte-readonly small {{ color:#667575; line-height:1.35; }}
.clarte-readonly {{ background:#fbfdfd; border-left:6px solid {OFFICIAL_TEAL}; }}
@media (max-width:1000px) {{ .clarte-context-bar {{ grid-template-columns:1fr 1fr; }} .clarte-beneficiary-header {{ grid-template-columns:1fr 1fr; }} }}
@media (max-width:640px) {{ .block-container {{ padding:1rem; }} div.stButton > button {{ min-height:3rem; }} .clarte-context-bar {{ grid-template-columns:1fr; }} .clarte-beneficiary-header {{ grid-template-columns:1fr; }} .clarte-kpi {{ min-height:88px; }} }}
</style>
""",
        unsafe_allow_html=True,
    )
