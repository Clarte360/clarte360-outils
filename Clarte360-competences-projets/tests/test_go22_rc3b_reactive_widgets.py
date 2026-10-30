"""Passation sans Streamlit installé : simule les clics et contrôle le rendu immédiat."""
import sys
from types import SimpleNamespace

import pytest

from clarte360_cp.domain.preparation_v2 import generate_questionnaire_v2, empty_answers_v2
from clarte360_cp.ui.preparation_rc3b import render_av1, render_av2
from tools.go22_rc3_demo_seed import synthetic_sources


class FakeStreamlit:
    def __init__(self, values=None, state=None):
        self.values=values or {}
        self.session_state=state or {}
        self.called=[]

    def __enter__(self):return self
    def __exit__(self,*a):return False
    def container(self,**k):return self
    def expander(self,*a,**k):return self
    def popover(self,*a,**k):return self
    def columns(self,n):return [self]*n if isinstance(n,int) else [self]*len(n)
    def markdown(self,*a,**k):pass
    def caption(self,*a,**k):pass
    def divider(self,*a,**k):pass
    def write(self,*a,**k):pass
    def info(self,*a,**k):pass
    def warning(self,*a,**k):pass
    def dataframe(self,*a,**k):self.called.append(("dataframe", k))
    def progress(self,*a,**k):pass
    def radio(self,label,options,*,key=None,index=None,**kw):
        self.called.append(("radio",label,key))
        return self.values.get(key,options[index] if index is not None else None)
    def pills(self,label,options,*,key=None,default=None,**kw):
        self.called.append(("pills",label,key))
        return self.values.get(key,default or [])
    def checkbox(self,label,*,key=None,value=False,disabled=False,**kw):
        self.called.append(("checkbox",label,key,disabled))
        return False if disabled and not value else self.values.get(key,value)
    def text_area(self,label,*,key=None,value="",**kw):
        self.called.append(("text_area",label,key))
        return self.values.get(key,value)
    def text_input(self,label,*,key=None,value="",**kw):
        self.called.append(("text_input",label,key))
        return self.values.get(key,value)


def fake(monkeypatch,values=None,state=None):
    st=FakeStreamlit(values,state)
    monkeypatch.setitem(sys.modules,"streamlit",st)
    return st


def test_cav1_subquestions_visible_on_first_display_even_before_interest_selected(monkeypatch):
    q=generate_questionnaire_v2(synthetic_sources("two"))
    a=empty_answers_v2(q)
    st=fake(monkeypatch)
    render_av1(q,a,"B")
    assert any(x[0]=="pills" and "_meaning_" in x[-1] for x in st.called)
    assert any(x[0]=="pills" and "_context_" in x[-1] for x in st.called)
    assert any(x[0]=="text_area" and "_note_" in x[-1] for x in st.called)
    assert not any(x[0]=="checkbox" and "_no_idea" in x[-1] for x in st.called)


def test_added_idea_context_is_present_immediately_without_save_then_return(monkeypatch):
    q=generate_questionnaire_v2(synthetic_sources("zero"))
    a=empty_answers_v2(q)
    st=fake(monkeypatch,{"B_new":"Travail dans le sport\nCréer une entreprise"})
    data=render_av1(q,a,"B")
    assert len(data["cav1"]["new_ideas"])==2
    assert any(x[0]=="pills" and x[-1]=="B_newcontext_0" for x in st.called)
    assert any(x[0]=="pills" and x[-1]=="B_newcontext_1" for x in st.called)


def test_yes_on_unacceptable_condition_renders_explanation_immediately(monkeypatch):
    q=generate_questionnaire_v2(synthetic_sources("zero"))
    a=empty_answers_v2(q)
    st=fake(monkeypatch,{"B_situation":"OUI","B_situation_note":"Horaires incompatibles avec mes contraintes"})
    result=render_av2(q,a,"B")
    assert result["cav2"]["preferences"]["situation"]=="OUI"
    assert "Horaires incompatibles" in result["cav2"]["preferences"]["situation_note"]
    assert any(x[0]=="text_area" and x[-1]=="B_situation_note" for x in st.called)
    assert sum(x[0]=="dataframe" for x in st.called)==5


def test_exact_pole_wording_and_three_priority_limit_are_rendered(monkeypatch):
    q=generate_questionnaire_v2(synthetic_sources("two"))
    a=empty_answers_v2(q)
    val=q["cav2"]["valeurs"]["choices"]
    state={f"B_valeurs_pick_{i}":i<3 for i in range(len(val))}
    st=fake(monkeypatch,state=state)
    render_av2(q,a,"B")
    assert any(x[0]=="checkbox" and x[-2]=="B_valeurs_pick_3" and x[-1] is True for x in st.called)
    assert any(x[0]=="radio" and x[-1]=="B_situation" for x in st.called)


def test_a_affiner_is_available_for_report_based_priorities(monkeypatch):
    q=generate_questionnaire_v2(synthetic_sources("two"))
    a=empty_answers_v2(q)
    st=fake(monkeypatch,{
        "B_valeurs_no_priority_reason":"A_AFFINER",
        "B_moteurs_no_priority_reason":"A_AFFINER",
        "B_pref_no_priority_reason":"A_AFFINER",
    })
    result=render_av2(q,a,"B")
    assert result["cav2"]["valeurs"]["none_reason"]=="A_AFFINER"
    assert result["cav2"]["moteurs"]["none_reason"]=="A_AFFINER"
    assert result["cav2"]["preferences"]["none_reason"]=="A_AFFINER"
    reasons=[x for x in st.called if x[0]=="radio" and x[2] and x[2].endswith("no_priority_reason")]
    assert len(reasons)==3


def test_a_affiner_is_available_when_source_reports_are_missing(monkeypatch):
    q=generate_questionnaire_v2({})
    a=empty_answers_v2(q)
    st=fake(monkeypatch,{
        "B_valeurs_free_reason":"A_AFFINER",
        "B_moteurs_free_reason":"A_AFFINER",
        "B_pref_free_reason":"A_AFFINER",
    })
    result=render_av2(q,a,"B")
    assert result["cav2"]["valeurs"]["none_reason"]=="A_AFFINER"
    assert result["cav2"]["moteurs"]["none_reason"]=="A_AFFINER"
    assert result["cav2"]["preferences"]["none_reason"]=="A_AFFINER"
