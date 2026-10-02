from __future__ import annotations

from typing import Mapping
import streamlit as st

from clarte360_ipip.questionnaire import TOTAL_ITEMS, item_at, position


def render_question(q, item_no: int, answers: Mapping[int, int]) -> int | None:
    item = item_at(q, item_no)
    pos = position(item_no, answers)

    st.markdown('<div class="clarte-question-shell">', unsafe_allow_html=True)
    st.markdown(f'<div class="clarte-question-kicker">QUESTION {item_no} / {TOTAL_ITEMS}</div>', unsafe_allow_html=True)
    st.progress(pos.progress_ratio)
    st.markdown(f'<div class="clarte-question-text">{item.text_fr}</div>', unsafe_allow_html=True)
    st.caption("Choisissez la réponse qui vous décrit le mieux aujourd'hui. Il n'y a pas de bonne ou de mauvaise réponse.")

    options = [1, 2, 3, 4, 5]
    current = answers.get(item_no)
    idx = options.index(current) if current in options else None
    value = st.radio(
        "Votre réponse",
        options,
        index=idx,
        format_func=lambda x: q.response_scale[x],
        key=f"ipip_item_{item_no}",
        horizontal=False,
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)
    return value
