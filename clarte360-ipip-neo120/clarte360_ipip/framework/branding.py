from __future__ import annotations

import streamlit as st
from .config import DARK_TEXT, LIGHT_TEAL, OFFICIAL_TEAL


def apply_framework_css() -> None:
    st.markdown(
        f"""
<style>
:root {{ --clarte-teal: {OFFICIAL_TEAL}; }}
.stProgress > div > div > div > div {{ background-color: {OFFICIAL_TEAL}; }}
h1, h2, h3 {{ color: {OFFICIAL_TEAL}; }}
div.stButton > button[kind="primary"] {{ background-color: {OFFICIAL_TEAL}; border-color: {OFFICIAL_TEAL}; }}
div.stButton > button[kind="primary"]:hover {{ background-color: #006f6f; border-color: #006f6f; }}
.clarte-hero {{ border:1px solid #d9eeee; border-left:7px solid {OFFICIAL_TEAL}; background:linear-gradient(135deg,#f2fbfb,#fff); padding:1.35rem 1.4rem; border-radius:.8rem; margin:1rem 0; color:{DARK_TEXT}; line-height:1.55; }}
.clarte-card {{ border:1px solid #d9eeee; border-radius:.8rem; padding:1rem; background:#fff; box-shadow:0 1px 8px rgba(0,128,128,.08); margin-bottom:1rem; }}
.clarte-box {{ border-left:6px solid {OFFICIAL_TEAL}; background:{LIGHT_TEAL}; padding:1rem 1.1rem; border-radius:.55rem; margin:1rem 0; color:{DARK_TEXT}; }}
.clarte-muted {{ color:#666; font-size:.92rem; }}
.clarte-mode {{ display:inline-block; padding:.25rem .6rem; border:1px solid #cfe6e6; border-radius:999px; color:{OFFICIAL_TEAL}; font-weight:700; font-size:.82rem; }}
.clarte-question-shell {{ border:1px solid #d9eeee; border-radius:1rem; padding:1.25rem 1.35rem; background:#fff; box-shadow:0 2px 12px rgba(0,128,128,.07); margin:.8rem 0 1.1rem; }}
.clarte-question-kicker {{ color:{OFFICIAL_TEAL}; font-weight:800; letter-spacing:.04em; font-size:.9rem; margin-bottom:.45rem; }}
.clarte-question-text {{ color:{DARK_TEXT}; font-size:1.35rem; line-height:1.45; font-weight:700; margin:1.15rem 0 .7rem; }}
div[role="radiogroup"] label {{ padding:.42rem .2rem; }}
.clarte-result-scale {{ margin:.45rem 0 .65rem; }}
.clarte-result-track {{ height:.55rem; background:linear-gradient(90deg,#e9f4f4,#b9dddd,#e9f4f4); border-radius:999px; position:relative; margin:.4rem .35rem .2rem; }}
.clarte-result-marker {{ position:absolute; top:50%; width:1rem; height:1rem; border-radius:50%; background:{OFFICIAL_TEAL}; border:3px solid white; box-shadow:0 0 0 1px {OFFICIAL_TEAL}; transform:translate(-50%,-50%); }}
.clarte-result-axis {{ display:flex; justify-content:space-between; gap:.5rem; font-size:.75rem; color:#667; }}
.clarte-facet-card {{ border-top:1px solid #e4eeee; padding-top:.45rem; margin-top:.7rem; }}
@media (max-width: 640px) {{
  .block-container {{ padding-top:1.2rem; padding-left:1rem; padding-right:1rem; }}
  div.stButton > button {{ min-height:3rem; }}
  .clarte-question-shell {{ padding:1rem; }}
  .clarte-question-text {{ font-size:1.18rem; }}
  div[role="radiogroup"] label {{ min-height:2.7rem; align-items:center; }}
}}
</style>
""",
        unsafe_allow_html=True,
    )
