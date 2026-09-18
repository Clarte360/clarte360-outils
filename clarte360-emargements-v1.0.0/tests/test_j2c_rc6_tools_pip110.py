from pathlib import Path
import json

from db import make_engine, init_db, execute, utcnow_iso
from services import (
    upsert_tool_catalog, list_tool_catalog, set_action_tool_allowed,
    action_allowed_tools, create_tool_prescription, ensure_default_organization,
)


def eng():
    e=make_engine("sqlite:///:memory:")
    init_db(e)
    ensure_default_organization(e)
    return e


def test_pip_registry_is_110_and_non_restrictive():
    data=json.loads(Path("config/tool_registry.json").read_text(encoding="utf-8"))
    pip=next(x for x in data["tools"] if x["tool_code"]=="PIP_RIASEC_ONET")
    assert pip["tool_version"]=="1.0.10-ACCOMPAGNEMENT"
    assert pip["active"] is True and pip["prescription_allowed"] is True
    assert pip["compatible_prestations"]==[]
    assert pip["metadata"]["compatibility_policy"]=="ALL_ACTION_TYPES"


def test_all_active_prescriptible_tools_visible_for_formation_even_with_legacy_metadata():
    e=eng()
    upsert_tool_catalog(e,{"tool_code":"LEGACY","name":"Legacy","base_url":"https://example.org","compatible_prestations":["COACHING"]},"admin")
    assert any(x["tool_code"]=="LEGACY" for x in list_tool_catalog(e,prescription_only=True,prestation_type="FORMATION"))


def test_multiple_action_permissions_persist_independently():
    e=eng(); n=utcnow_iso()
    oid=execute(e,"INSERT INTO organizations(name,legal_name,active,created_at,updated_at) VALUES('O','O',1,:n,:n)",{"n":n})
    aid=execute(e,"INSERT INTO actions(action_no,title,nature,prestation_type,mode,status,planned_hours,expected_participants,organization_id,created_at,updated_at) VALUES('ESSAI','Essai','Formation','FORMATION','INDIVIDUEL','ACTIVE',1,1,:o,:n,:n)",{"o":oid,"n":n})
    for code in ("PIP_RIASEC_ONET","BOUSSOLE_VALEURS","ROUE_VALEURS"):
        upsert_tool_catalog(e,{"tool_code":code,"name":code,"base_url":"https://example.org/"+code.lower(),"active":True,"prescription_allowed":True},"admin")
        ok,msg=set_action_tool_allowed(e,aid,code,True,"admin")
        assert ok, msg
    assert {x["tool_code"] for x in action_allowed_tools(e,aid)}=={"PIP_RIASEC_ONET","BOUSSOLE_VALEURS","ROUE_VALEURS"}


def test_action_tools_ui_autosaves_without_save_button():
    src=Path("app.py").read_text(encoding="utf-8")
    block=src[src.index("def action_tools_tab(a):"):src.index("def teams_tab(a):") if "def teams_tab(a):" in src[src.index("def action_tools_tab(a):"):] else src.index("def quality_tab", src.index("def action_tools_tab(a):"))]
    assert "ENREGISTRER LES OUTILS DE L’ACTION" not in block
    assert "if wanted != current_codes:" in block
    assert "set_action_tool_allowed" in block
