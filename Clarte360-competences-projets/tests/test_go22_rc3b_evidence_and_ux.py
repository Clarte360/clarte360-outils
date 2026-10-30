"""RC3B : chiffres sourcés/fiction, UX réactive et compatibilité RC2/RC3A."""
from __future__ import annotations

import copy
from pathlib import Path
import pytest

from clarte360_cp.domain.preparation_v2 import (
    generate_questionnaire_v2, valid_questionnaire_v2,
    public_questionnaire_v2, empty_answers_v2, valid_answers_v2,
)
from clarte360_cp.domain.preparation_evidence import valid_evidence
from tools.go22_rc3_demo_seed import synthetic_sources
from tests.test_go22_rc3_unique_q import filled

ROOT=Path(__file__).parents[1]


def test_synthetic_reports_all_five_tools_but_are_never_preenchecked():
    q=generate_questionnaire_v2(synthetic_sources("two"),context="AUTOFINANCE")
    assert set(q["evidence"])=={"valeurs","moteurs","preferences","ipip","pip"}
    assert all(x["status"]=="FICTIF" for x in q["evidence"].values())
    assert len(q["evidence"]["valeurs"]["rows"])==len(q["cav2"]["valeurs"]["choices"])
    assert len(q["evidence"]["moteurs"]["rows"])==10
    assert len(q["evidence"]["preferences"]["rows"])==10
    assert len(q["evidence"]["ipip"]["rows"])==5
    assert len(q["evidence"]["pip"]["rows"])==6
    assert q["evidence"]["pip"]["profile_code"]=="RSC"  # 3 lettres EXACTES de la source fictive
    a=empty_answers_v2(q)
    assert not a["cav2"]["valeurs"]["choices"]
    assert not a["cav2"]["moteurs"]["choices"]
    assert not a["cav2"]["preferences"]["priorities"]


def test_report_reference_without_structured_results_never_gets_invented_scores():
    src=synthetic_sources("two")
    for k in src:
        src[k].pop("result_summary",None)
    q=generate_questionnaire_v2(src,context="AUTOFINANCE")
    assert q["evidence"]=={}
    assert len(q["report_refs"])==2


def test_source_results_cannot_be_supplied_without_authorization():
    src=synthetic_sources("zero")
    src["PIP_REPORT"]["authorized"]=False
    q=generate_questionnaire_v2(src,context="AUTOFINANCE")
    assert "pip" not in q["evidence"]
    assert not any(x["code"]=="PIP_REPORT" for x in q["report_refs"])


def test_public_projection_masks_internal_source_refs_preserves_pedagogical_results():
    q=generate_questionnaire_v2(synthetic_sources("many"),context="AUTOFINANCE")
    p=public_questionnaire_v2(q)
    assert p["source_refs"]==[]
    assert all("SIMULATION/" not in str(x) for x in p["evidence"].values())
    assert p["evidence"]["pip"]["profile_code"]=="RSC"
    assert empty_answers_v2(p)["cav1_done"] is False
    assert len(p["ideas_active"])==5


def test_no_evidence_in_legacy_v2_q_is_accepted():
    src=synthetic_sources("two")
    q=generate_questionnaire_v2(src,context="AUTOFINANCE")
    q.pop("evidence")
    assert valid_questionnaire_v2(q)["schema"].endswith("_V2")
    assert "evidence" not in valid_questionnaire_v2(q)


def test_invalid_score_payload_shape_and_fake_status_blocked():
    q=generate_questionnaire_v2(synthetic_sources("two"),context="AUTOFINANCE")
    bad=copy.deepcopy(q)
    bad["evidence"]["pip"]["rows"][0]["unknown"]="bad"
    with pytest.raises(ValueError):valid_questionnaire_v2(bad)
    bad=copy.deepcopy(q)
    bad["evidence"]["pip"]["profile_code"]="RSCZZ"
    with pytest.raises(ValueError):valid_questionnaire_v2(bad)
    bad=copy.deepcopy(q)
    bad["evidence"]["pip"]["status"]="REEL"  # cannot launder fictive score into a real one
    with pytest.raises(ValueError):valid_questionnaire_v2(bad)


def test_r1_final_validation_cannot_pass_unexplained_yes_situation():
    src=synthetic_sources("two")
    q=generate_questionnaire_v2(src,context="AUTOFINANCE")
    a=empty_answers_v2(q)
    for idea in q["ideas_active"]:
        a["cav1"]["ideas"].append({"id":idea["id"],"interest":"EXPLORER", "meaning":[],"status":[],"attraction":[],"access":[],
            "context":{"choices":[],"other":""},"note":""})
    a["cav1_done"]=True
    a["cav2"]["valeurs"]["choices"]=["Respect"]
    a["cav2"]["moteurs"]["choices"]=["Construire"]
    a["cav2"]["preferences"]["none_reason"]="AUCUN_CRITERE_IDENTIFIE"
    a["cav2"]["preferences"]["situation"]="OUI"
    a["cav2_done"]=True
    with pytest.raises(ValueError,match="Décrivez la situation"):
        valid_answers_v2(a,q,final=True)
    a["cav2"]["preferences"]["situation_note"]="Des déplacements imprévisibles non compatibles avec mes contraintes."
    assert valid_answers_v2(a,q,final=True)["cav2_done"]


def test_ui_widgets_react_without_hidden_subform_or_select_all():
    field=(ROOT/"clarte360_cp/ui/preparation_rc3b.py").read_text(encoding="utf-8")
    core=(ROOT/"clarte360_cp/ui/preparation_rc3.py").read_text(encoding="utf-8")
    assert "with st.form" not in field
    assert "Select all" not in field
    assert "st.pills" in field
    assert "situation==\"OUI\"" in field
    assert "ctx_sel=_multi(" in field # fresh idea context visible in one pass
    assert "with st.form(f\"rc3_benef_cav1" not in core
    assert "with st.form(f\"rc3_benef_cav2" not in core


def test_no_pip_five_letter_invention():
    src=synthetic_sources("two")
    src["PIP_REPORT"]["result_summary"]["profile_code"]="RSCIA"
    q=generate_questionnaire_v2(src,context="AUTOFINANCE")
    assert q["evidence"]["pip"]["profile_code"]=="RSCIA"
    src["PIP_REPORT"]["result_summary"]["profile_code"]="RSCIX"
    with pytest.raises(ValueError):generate_questionnaire_v2(src,context="AUTOFINANCE")
