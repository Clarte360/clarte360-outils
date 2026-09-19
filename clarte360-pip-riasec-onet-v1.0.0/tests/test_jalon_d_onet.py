from pathlib import Path
import pytest
from clarte360_pip.connectors.onet import OnetPort, normalize_onet_results, ONET_INSTRUMENT, ONET_QUESTION_COUNT, ONET_API_VERSION
from clarte360_pip.framework.config import OnetSettings


def test_onet_contract_is_short_form_60_v2():
    assert ONET_INSTRUMENT == "O*NET Interest Profiler Short Form"
    assert ONET_QUESTION_COUNT == 60
    assert ONET_API_VERSION == "2.0"


def test_onet_results_are_sorted_descending_without_rescaling():
    src=[{"code":"social","score":18},{"code":"realistic","score":27},{"code":"artistic","score":23}]
    out=normalize_onet_results(src)
    assert [x["score"] for x in out] == [27,23,18]
    assert src[0]["score"] == 18


def test_onet_score_requires_exactly_60_valid_answers(monkeypatch):
    port=OnetPort(OnetSettings("key","https://api-v2.onetcenter.org"))
    with pytest.raises(ValueError):
        port.score_interest_profiler({str(i):3 for i in range(1,60)})
    with pytest.raises(ValueError):
        port.score_interest_profiler({str(i):3 for i in range(1,61)} | {"60":6})


def test_onet_scoring_sends_answer_string_in_official_order(monkeypatch):
    captured={}
    port=OnetPort(OnetSettings("key","https://api-v2.onetcenter.org"))
    def fake(path, params=None):
        captured["path"]=path; captured["answers"]=params["answers"]
        return {"result":[]}
    monkeypatch.setattr(OnetPort, "_get", lambda self, path, params=None: fake(path, params))
    answers={str(i): ((i-1)%5)+1 for i in range(1,61)}
    port.score_interest_profiler(answers)
    assert captured["path"] == "/mnm/interestprofiler/results"
    assert captured["answers"] == "12345"*12


def test_ui_keeps_pre_and_post_pip_timing_and_descriptive_comparison():
    text=Path("clarte360_pip/ui/pages.py").read_text(encoding="utf-8")
    assert '"PRE_PIP"' in text and '"POST_PIP_RESULTS"' in text
    assert "résultat PIP reste volontairement masqué" in text
    assert "score officiel décroissant" in text
    assert "ne sont ni fusionnées ni moyennées" in text
