from pathlib import Path
from clarte360_pip.framework.public_access import validate_public_identity, save_public_lead
from clarte360_pip.framework.persistence import build_snapshot, restore_snapshot
from clarte360_pip.connectors.onet import OnetPort
from clarte360_pip.framework.config import OnetSettings


def test_public_only_four_identity_fields_are_required():
    assert validate_public_identity({"first_name":"A","last_name":"B","phone":"+33 6 12 34 56 78","email":"a@b.fr","job_title":"","company":""}) == []
    errs=validate_public_identity({"first_name":"","last_name":"","phone":"","email":""})
    assert len(errs) == 4


def test_public_snapshot_keeps_interests_and_onet_timing():
    state={"passation_id":"p","session_id":"s","public_interests":["Bilan de compétences"],"public_other_interest":"","onet_selected_timing":"POST_PIP_RESULTS","pip_state":{},"public_access_verified":True}
    snap=build_snapshot(state)
    assert snap["public_interests"] == ["Bilan de compétences"]
    assert snap["onet_selected_timing"] == "POST_PIP_RESULTS"
    restored={}
    restore_snapshot(snap, restored)
    assert restored["public_interests"] == ["Bilan de compétences"]


def test_onet_connector_is_real_v2_contract(monkeypatch):
    captured={}
    class Resp:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def read(self): return b'{"question": []}'
    def fake(req, timeout=0):
        captured["url"]=req.full_url
        captured["key"]=req.headers.get("X-api-key") or req.headers.get("X-API-Key")
        return Resp()
    monkeypatch.setattr("clarte360_pip.connectors.onet.urlopen", fake)
    port=OnetPort(OnetSettings("test-key","https://api-v2.onetcenter.org"))
    port.fetch_interest_profiler()
    assert "/mnm/interestprofiler/questions" in captured["url"]
    assert "start=1" in captured["url"] and "end=60" in captured["url"]
    assert captured["key"] == "test-key"


def test_sidebar_contains_permanent_branding_and_resume():
    text=Path("clarte360_pip/ui/sidebar.py").read_text(encoding="utf-8")
    assert "logo_clarte360.png" in text
    assert "www.clarte360.com" in text
    assert "Reprendre ma passation" in text


def test_onet_can_be_selected_after_pip_results():
    text=Path("clarte360_pip/ui/pages.py").read_text(encoding="utf-8")
    assert "POST_PIP_RESULTS" in text
    assert "Passer aussi O*NET 60" in text
    assert "render_onet_questionnaire" in text
