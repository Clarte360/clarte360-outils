"""GO22 RC3 - contrat du questionnaire unique, sans IA pendant la passation."""
import copy

import pytest
from sqlalchemy import func, select

from clarte360_cp.application.orientation import OrientationAccessDenied, OrientationConflict
from clarte360_cp.application.preparation import (
    create_questionnaire_v2, save_questionnaire, lock_questionnaire, open_beneficiary_access,
    read_preparation, save_beneficiary_answers, submit_beneficiary_answers,
    save_joint_review, confirm_joint_review, cav3_context,
)
from clarte360_cp.domain.preparation import empty_answers, valid_answers
from clarte360_cp.domain.preparation_v2 import (
    SCHEMA_Q_V2, SCHEMA_R_V2, DEFAULT_CONTEXT_PROMPT, new_idea,
    adapt_context_question, generate_questionnaire_v2, valid_questionnaire_v2,
    valid_answers_v2,
)
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import PreparationResponse, PreparationQuestionnaire, AuditEvent
from tests.helpers import context

ACC = ["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_VALIDATE", "CP_PUBLISH"]
BEN = ["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_INTERACT", "CP_BENEFICIARY_VALIDATE"]


@pytest.fixture
def sc(engine, Session):
    coach = context(scopes=ACC, actor="ACC-RC3")
    ben = context(role="BENEFICIAIRE", scopes=BEN, actor="BEN-RC3")
    with Session() as s:
        case = CaseRepository(s).open_or_create(coach)
        cid = case.case_id
    return str(engine.url), cid, coach, ben


@pytest.fixture
def sources():
    return {
        "APS_OBJECTIF": {"authorized":True,"source_ref":"APS-TEST","idea_list":["muséographe","préparatrice en pharmacie"]},
        "BOUSSOLE_VALEURS": {"authorized":True,"source_ref":"VAL-TEST","items":["Créativité", "Respect", "Autonomie"]},
        "MOTEURS_PRO": {"authorized":True,"source_ref":"MOT-TEST"},
        "PREFERENCES_PRO": {"authorized":True,"source_ref":"PREF-TEST","dimensions":[
            {"code":"PP1","label":"Autonomie","pole_1":"Cadre guidé","pole_2":"Grande liberté"},
            {"code":"PP2","label":"Changement","pole_1":"Continuité","pole_2":"Nouveauté"},
            {"code":"PP3","label":"Relations","pole_1":"Travail indépendant","pole_2":"Coopération"},
        ]},
        "IPIP_REPORT":{"authorized":True,"source_ref":"NEO-TEST","status":"REEL"},
        "PIP_REPORT":{"authorized":True,"source_ref":"PIP-SIMULE","status":"FICTIF"},
        "ENTREPRISE_PERSPECTIVE":{"authorized":False,"source_ref":"EMP-INTERDIT","wording":"Ne doit pas sortir"},
    }


def ready(sc, sources):
    db, cid, coach, ben = sc
    draft = create_questionnaire_v2(coach,cid,sources,context="AUTOFINANCE",database_url=db)
    locked=lock_questionnaire(coach,cid,expected_row_version=draft.row_version,database_url=db)
    opened=open_beneficiary_access(coach,cid,expected_row_version=locked.row_version,database_url=db)
    return opened


def filled(q):
    a=empty_answers(q)
    a["cav1"]["ideas"]=[{
        "id":idea["id"], "interest":"EXPLORER" if i==0 else "NON_ACTUELLEMENT",
        "meaning":["Exercer ce métier"] if i==0 else [], "status":[],"attraction":[],"access":[],
        "context":{"choices":["Dans une organisation existante"] if i==0 else [],"other":""},"note":""
    } for i,idea in enumerate(q["ideas_active"])]
    if not q["ideas_active"]:a["cav1"]["no_idea"]=True
    a["cav2"]["valeurs"]["choices"]=["Créativité"] if q["cav2"]["valeurs"]["mode"]=="CHOIX" else []
    if q["cav2"]["valeurs"]["mode"]=="LIBRE":a["cav2"]["valeurs"]["free"]=["Respect"]
    a["cav2"]["moteurs"]["choices"]=["Innover"] if q["cav2"]["moteurs"]["mode"]=="CHOIX" else []
    if q["cav2"]["moteurs"]["mode"]=="LIBRE":a["cav2"]["moteurs"]["free"]=["Comprendre les choses"]
    if q["cav2"]["preferences"]["mode"]=="DIMENSIONS":
        a["cav2"]["preferences"]["priorities"]=[{"code":"PP1","pole":"EQUILIBRE","other":"","importance":"IMPORTANT_ADAPTABLE","note":""}]
    else:a["cav2"]["preferences"]["free"]="Conserver des échanges réguliers"
    a["cav2"]["preferences"]["situation"]="PAS_IDENTIFIEE"
    return a


def test_q_unique_has_two_parts_and_no_repeat_ipip_pip(sources):
    q=generate_questionnaire_v2(sources,context="AUTOFINANCE")
    assert q["schema"]==SCHEMA_Q_V2
    assert len(q["ideas_active"])==2
    assert len(q["cav2"])==3
    assert set(q["cav2"])=={"valeurs","moteurs","preferences"}
    assert {r["status"] for r in q["report_refs"]}=={"REEL","FICTIF"}
    assert "PIP_ATTRACTION" not in str(q) and "IPIP_FAVORISER" not in str(q)
    assert "GO_NO_GO" not in str(q) and "PREF_GO" not in str(q)
    assert all(i["context_prompt"]==DEFAULT_CONTEXT_PROMPT for i in q["ideas_active"])
    assert q["enterprise_wording"]==""
    assert all(r["code"]!="ENTREPRISE_PERSPECTIVE" for r in q["source_refs"])
    assert "bilan" not in q["intro"].lower()


def test_legacy_preparation_v1_still_supported(sources):
    from clarte360_cp.domain.preparation import generate_questionnaire
    q=generate_questionnaire({"APS_OBJECTIF":sources["APS_OBJECTIF"]})
    assert valid_answers(empty_answers(q),q)["ideas"]==[]


def test_context_hypothesis_changes_only_one_piste(sources):
    q=generate_questionnaire_v2(sources)
    before=copy.deepcopy(q)
    q["ideas_active"][1]=adapt_context_question(q["ideas_active"][1],"une activité dans une entreprise familiale")
    assert "entreprise familiale" in q["ideas_active"][1]["context_prompt"]
    assert q["ideas_active"][0]==before["ideas_active"][0]
    assert q["cav2"]==before["cav2"]
    assert q["source_refs"]==before["source_refs"]
    assert valid_questionnaire_v2(q)["ideas_active"][1]["context_note"]


def test_coach_adds_new_piste_and_archives_aps_without_erasing_provenance(sc,sources):
    db,cid,coach,ben=sc
    v=create_questionnaire_v2(coach,cid,sources,database_url=db)
    q=copy.deepcopy(v.questionnaire)
    deleted=q["ideas_active"].pop(1)
    q["ideas_archived"].append(deleted)
    q["ideas_active"].append(new_idea("un autre projet professionnel","ENTRETIEN"))
    s=save_questionnaire(coach,cid,q,expected_row_version=v.row_version,database_url=db)
    l=lock_questionnaire(coach,cid,expected_row_version=s.row_version,database_url=db)
    o=open_beneficiary_access(coach,cid,expected_row_version=l.row_version,database_url=db)
    public=read_preparation(ben,cid,database_url=db).questionnaire
    assert deleted["id"] not in {x["id"] for x in public["ideas_active"]}
    assert public["ideas_archived"]==[]
    assert public["source_refs"]==[]  # traçabilité interne, non partagée
    assert "un autre projet professionnel" in {x["wording"] for x in public["ideas_active"]}
    assert "préparatrice en pharmacie" in [x["wording"] for x in l.questionnaire["ideas_archived"]]
    assert l.questionnaire["source_refs"][0]["source_ref"]=="APS-TEST"
    with pytest.raises(ValueError,match="verrouillé"):
        save_questionnaire(coach,cid,q,expected_row_version=o.row_version,database_url=db)


def test_unauthorized_beneficiary_cannot_see_before_lock(sc,sources):
    db,cid,coach,ben=sc
    a=create_questionnaire_v2(coach,cid,sources,database_url=db)
    assert read_preparation(ben,cid,database_url=db).questionnaire is None
    b=lock_questionnaire(coach,cid,expected_row_version=a.row_version,database_url=db)
    assert read_preparation(ben,cid,database_url=db).questionnaire is None
    open_beneficiary_access(coach,cid,expected_row_version=b.row_version,database_url=db)
    assert read_preparation(ben,cid,database_url=db).questionnaire is not None


def test_cav2_cannot_be_marked_done_without_prior_saved_cav1(sc,sources):
    db,cid,coach,ben=sc
    view=ready(sc,sources)
    a=filled(view.questionnaire);a["cav1_done"]=True;a["cav2_done"]=True
    with pytest.raises(ValueError,match="Terminez et enregistrez C-AV1"):
        save_beneficiary_answers(ben,cid,a,expected_row_version=view.row_version,database_url=db)


def test_unified_r1_requires_cav1_then_cav2_and_is_immutable(sc,sources,Session):
    db,cid,coach,ben=sc
    view=ready(sc,sources)
    a=filled(view.questionnaire);a["cav1_done"]=True
    step1=save_beneficiary_answers(ben,cid,a,expected_row_version=view.row_version,database_url=db)
    with pytest.raises(ValueError,match="Complétez C-AV1 puis C-AV2"):
        submit_beneficiary_answers(ben,cid,expected_row_version=step1.row_version,database_url=db)
    a["cav2_done"]=True
    step2=save_beneficiary_answers(ben,cid,a,expected_row_version=step1.row_version,database_url=db)
    r1=submit_beneficiary_answers(ben,cid,expected_row_version=step2.row_version,database_url=db)
    assert r1.active_answers["schema"]==SCHEMA_R_V2
    assert r1.active_answers["cav1_done"] and r1.active_answers["cav2_done"]
    assert cav3_context(coach,cid,database_url=db)["reponses"]["cav2"]["valeurs"]["choices"]==["Créativité"]
    with pytest.raises(ValueError,match="définitivement"):
        save_beneficiary_answers(ben,cid,a,expected_row_version=r1.row_version,database_url=db)
    with Session() as s:
        assert s.scalar(select(func.count()).select_from(PreparationResponse).where(PreparationResponse.state=="BENEFICIAIRE_VALIDE"))==1
        assert s.scalar(select(func.count()).select_from(PreparationQuestionnaire).where(PreparationQuestionnaire.state=="VERROUILLE"))==1


def test_r2_revalidation_and_no_automatic_ia(sc,sources):
    db,cid,coach,ben=sc
    view=ready(sc,sources)
    a=filled(view.questionnaire);a["cav1_done"]=True
    s=save_beneficiary_answers(ben,cid,a,expected_row_version=view.row_version,database_url=db)
    a["cav2_done"]=True
    s=save_beneficiary_answers(ben,cid,a,expected_row_version=s.row_version,database_url=db)
    r1=submit_beneficiary_answers(ben,cid,expected_row_version=s.row_version,database_url=db)
    edited=copy.deepcopy(a)
    edited["cav2"]["valeurs"]["choices"]=["Respect"]
    pending=save_joint_review(coach,cid,edited,expected_row_version=r1.row_version,database_url=db)
    assert pending.active_answers["cav2"]["valeurs"]["choices"]==["Créativité"]
    r2=confirm_joint_review(coach,cid,beneficiary_confirmed=True,method="PARTAGE_ECRAN_ORAL",expected_row_version=pending.row_version,database_url=db)
    assert r2.active_answers["cav2"]["valeurs"]["choices"]==["Respect"]
    assert r2.active_response_version>r1.active_response_version
    assert cav3_context(coach,cid,database_url=db)["response_version"]==r2.active_response_version


def test_cav3_ia_snapshot_is_internal_and_automatically_stale_after_r2(sc,sources,Session):
    import json
    from clarte360_cp.application.preparation import run_cav3_analysis, cav3_analysis_history
    from clarte360_cp.repositories.models import Cav3Analysis

    class Responses:
        def create(self, **kwargs):
            result={"directions":[{"proposition":"Explorer les activités d'analyse",
                "evidence":["CAV1:piste-1"],"source_refs":["APS-TEST"],
                "question_en_seance":"Qu'est-ce qui vous attire ?"}],
                "points_a_eclaircir":[],"incertitudes":["À confirmer en séance"],"source_refs":["APS-TEST"]}
            return type("Response", (), {"output_text":json.dumps(result),"status":"completed"})()
    class Client:
        responses=Responses()

    db,cid,coach,ben=sc
    view=ready(sc,sources)
    answers=filled(view.questionnaire);answers["cav1_done"]=True
    step=save_beneficiary_answers(ben,cid,answers,expected_row_version=view.row_version,database_url=db)
    answers["cav2_done"]=True
    step=save_beneficiary_answers(ben,cid,answers,expected_row_version=step.row_version,database_url=db)
    r1=submit_beneficiary_answers(ben,cid,expected_row_version=step.row_version,database_url=db)
    from clarte360_cp.connectors.cav3_ai import Cav3AISettings
    settings=Cav3AISettings("synthetic-key","synthetic-model")
    first=run_cav3_analysis(coach,cid,settings,database_url=db,client=Client())
    assert first["current"] is True
    assert cav3_analysis_history(coach,cid,database_url=db)[0]["current"] is True
    revised=copy.deepcopy(answers);revised["cav2"]["valeurs"]["choices"]=["Respect"]
    pending=save_joint_review(coach,cid,revised,expected_row_version=r1.row_version,database_url=db)
    assert cav3_analysis_history(coach,cid,database_url=db)[0]["current"] is False
    provisional=run_cav3_analysis(coach,cid,settings,database_url=db,client=Client())
    assert provisional["source_stage"]=="R2_PROVISOIRE"
    assert provisional["current"] is True
    r2=confirm_joint_review(coach,cid,beneficiary_confirmed=True,method="PARTAGE_ECRAN_ORAL",
                            expected_row_version=pending.row_version,database_url=db)
    history=cav3_analysis_history(coach,cid,database_url=db)
    assert history[0]["current"] is False
    assert history[0]["response_version"] < r2.active_response_version
    assert history[1]["current"] is True
    assert history[1]["source_stage"] == "R2_CONFIRME"
    assert history[1]["current"] is True
    with Session() as session:
        stored=session.get(Cav3Analysis,first["analysis_id"])
        assert stored is not None
        assert stored.result_json and stored.source_fingerprint


def test_beneficiary_cannot_invoke_cav3_even_if_ai_is_configured(sc):
    from clarte360_cp.application.preparation import run_cav3_analysis
    class NoCall:
        class Responses:
            def create(self, **kwargs): pytest.fail("aucun appel IA bénéficiaire")
        responses=Responses()
    with pytest.raises(OrientationAccessDenied):
        run_cav3_analysis(sc[3],sc[1],{"api_key":"synthetic"},
                          database_url=sc[0],client=NoCall())


def test_no_idea_no_sources_still_completable(sc):
    db,cid,coach,ben=sc
    q=create_questionnaire_v2(coach,cid,{},database_url=db)
    assert all(q.questionnaire["cav2"][s]["mode"]=="LIBRE" for s in ("valeurs","moteurs","preferences"))
    l=lock_questionnaire(coach,cid,expected_row_version=q.row_version,database_url=db)
    o=open_beneficiary_access(coach,cid,expected_row_version=l.row_version,database_url=db)
    a=filled(o.questionnaire);a["cav1_done"]=True
    s=save_beneficiary_answers(ben,cid,a,expected_row_version=o.row_version,database_url=db)
    a["cav2_done"]=True
    s=save_beneficiary_answers(ben,cid,a,expected_row_version=s.row_version,database_url=db)
    fin=submit_beneficiary_answers(ben,cid,expected_row_version=s.row_version,database_url=db)
    assert fin.active_answers["cav1"]["no_idea"] is True
    assert fin.active_answers["cav2"]["preferences"]["free"]


def test_legacy_sources_dont_synthesize_fake_poles(sources):
    raw=copy.deepcopy(sources);raw["PREFERENCES_PRO"].pop("dimensions")
    q=generate_questionnaire_v2(raw)
    assert q["cav2"]["preferences"]["mode"]=="LIBRE"
    assert q["cav2"]["preferences"]["dimensions"]==[]


def test_critical_mixed_sources_distinct_enterprise(sources):
    raw=copy.deepcopy(sources);raw["ENTREPRISE_PERSPECTIVE"]["authorized"]=True
    with pytest.raises(ValueError,match="Perspective employeur"):
        generate_questionnaire_v2(raw,context="AUTOFINANCE")
    permitted=generate_questionnaire_v2(raw,context="ENTREPRISE_TRIPARTITE")
    assert "Ne doit pas sortir" in permitted["enterprise_wording"]


def test_reject_untrusted_fabricated_cav1_response(sc,sources):
    db,cid,coach,ben=sc
    view=ready(sc,sources)
    a=filled(view.questionnaire);a["cav1_done"]=True
    a["cav1"]["ideas"][0]["context"]["choices"]=["Un contexte fabriqué"]
    with pytest.raises(ValueError,match="Contexte non proposé"):
        save_beneficiary_answers(ben,cid,a,expected_row_version=view.row_version,database_url=db)


def test_unfinished_preference_brouillon_allowed_but_cannot_finalize(sources):
    q=generate_questionnaire_v2(sources)
    a=filled(q);a["cav1_done"]=True
    a["cav2"]["preferences"]["priorities"][0]["pole"]=""
    assert valid_answers_v2(a,q)["cav2"]["preferences"]["priorities"][0]["pole"]==""
    a["cav2_done"]=True
    with pytest.raises(ValueError,match="Pôle futur"):
        valid_answers_v2(a,q,final=True)


def test_no_idea_after_ideas_discarded_is_valid(sources):
    q=generate_questionnaire_v2(sources)
    a=filled(q);a["cav1_done"]=True
    for p in a["cav1"]["ideas"]:p["interest"]="NON_ACTUELLEMENT"
    a["cav1"]["no_idea"]=True
    assert valid_answers_v2(a,q)["cav1"]["no_idea"]
    a["cav1"]["ideas"][0]["interest"]="EXPLORER"
    with pytest.raises(ValueError,match="Aucune idée"):
        valid_answers_v2(a,q)


def test_new_spontaneous_idea_gets_neutral_context_without_ai(sources):
    q=generate_questionnaire_v2(sources)
    a=filled(q);a["cav1_done"]=True
    a["cav1"]["new_ideas"]=[{"wording":"Projet dans un autre domaine",
         "context":{"choices":["Plusieurs contextes possibles"],"other":"Je voudrais vérifier un contexte particulier"}}]
    r=valid_answers_v2(a,q)
    assert r["cav1"]["new_ideas"][0]["context"]["choices"]==["Plusieurs contextes possibles"]
    assert r["cav1"]["new_ideas"][0]["context"]["other"]
    a["cav1"]["new_ideas"][0]["context"]["choices"]=["Choix inventé par IA"]
    with pytest.raises(ValueError,match="Réponse de contexte non prévue"):
        valid_answers_v2(a,q)


def test_coach_may_reword_piste_without_rewriting_original_aps(sc,sources):
    db,cid,coach,ben=sc
    first=create_questionnaire_v2(coach,cid,sources,database_url=db)
    original=first.questionnaire["ideas_active"][0]["source_wording"]
    q=copy.deepcopy(first.questionnaire)
    q["ideas_active"][0]["wording"]="Conception d'expositions et scénographie"
    revised=save_questionnaire(coach,cid,q,expected_row_version=first.row_version,database_url=db)
    assert revised.questionnaire["ideas_active"][0]["source_wording"]==original
    q=copy.deepcopy(revised.questionnaire)
    q["ideas_active"][0]["source_wording"]="Un métier jamais mentionné"
    with pytest.raises(ValueError,match="Provenance APS immuable"):
        save_questionnaire(coach,cid,q,expected_row_version=revised.row_version,database_url=db)
