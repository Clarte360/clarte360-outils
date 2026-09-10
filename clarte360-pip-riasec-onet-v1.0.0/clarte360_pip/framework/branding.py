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
.clarte-box {{ border-left: 6px solid {OFFICIAL_TEAL}; background: {LIGHT_TEAL}; padding: 1rem 1.1rem; border-radius: .55rem; margin: 1rem 0; color: {DARK_TEXT}; }}
.clarte-card {{ border: 1px solid #d9eeee; border-radius: .8rem; padding: 1rem; background: #fff; box-shadow: 0 1px 8px rgba(0,128,128,.08); margin-bottom: 1rem; }}
.clarte-muted {{ color:#666; font-size:.92rem; }}
.clarte-mode {{ display:inline-block; padding:.25rem .6rem; border:1px solid #cfe6e6; border-radius:999px; color:{OFFICIAL_TEAL}; font-weight:700; font-size:.82rem; }}
@media (max-width: 640px) {{
  .block-container {{ padding-top: 1.2rem; padding-left: 1rem; padding-right: 1rem; }}
  div.stButton > button {{ min-height: 3rem; }}
}}
</style>
""",
        unsafe_allow_html=True,
    )
