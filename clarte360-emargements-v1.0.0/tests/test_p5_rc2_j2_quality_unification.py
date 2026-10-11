"""J2 canonical Quality checks; entirely fictitious identities/actions."""
import json
from pathlib import Path
import pytest
from db import make_engine, init_db, execute, one, q, utcnow_iso
from services import (
    create_quality_event,quality_case,quality_case_history,quality_case_sources,
    quality_case_messages,link_quality_source,quality_unlinked_sources,suggest_quality_links,
    create_beneficiary_report, update_user_report, update_quality_event,
    create_trainer_report, add_quality_case_message, create_quality_issue,
    create_improvement_action, update_improvement_action,update_quality_issue,
    add_quality_event_action,update_quality_event_action, quality_event_actions,
    list_quality_events, delete_improvement_action,quality_dashboard_v31
)
from purge_guard import preview_action_purge,certify_test_action,purge_certified_action
from security import hash_password

ADMIN='quality-j2-admin@example.invalid'
@pytest.fixture
def ctx(tmp_path):
    engine=make_engine('sqlite:///'+str(tmp_path/'quality-j2.sqlite'))
    init_db(engine)
    now=utcnow_iso()
    org=execute(engine,"INSERT INTO organizations(name,legal_name,active,created_at,updated_at) VALUES('Org fictif','Org fictif',1,:n,:n)",{'n':now})
    ids=[]
    for code in ['TEST-J2','VOISINE-J2']:
        ids.append(execute(engine,"""INSERT INTO actions(action_no,title,nature,mode,planned_hours,organization_id,status,created_at,updated_at)
             VALUES(:a,'Action fictive','Formation','INDIVIDUEL',1,:o,'BROUILLON',:n,:n)""",{'a':code,'o':org,'n':now}))
    bid=execute(engine,"INSERT INTO beneficiaries(public_id,first_name,last_name,birth_date,created_at,updated_at) VALUES('BEN-J2','Fictive','Personne','2000-01-01',:n,:n)",{'n':now})
    execute(engine,"INSERT INTO participants(action_id,last_name,first_name,beneficiary_id,created_at) VALUES(:a,'Personne','Fictive',:b,:n)",{'a':ids[0],'b':bid,'n':now})
    tid=execute(engine,"INSERT INTO trainers(full_name,email,created_at,updated_at) VALUES('Intervenant fictif','trainer-j2@example.invalid',:n,:n)",{'n':now})
    execute(engine,'UPDATE actions SET trainer_id=:t WHERE id=:a',{'t':tid,'a':ids[0]})
    execute(engine,'INSERT INTO admins(email,password_hash,created_at) VALUES(:e,:p,:n)',{'e':ADMIN,'p':hash_password('j2-only-secret-password'),'n':now})
    yield engine,ids[0],ids[1],bid,tid,tmp_path
    engine.dispose()


def test_additive_schema_and_idempotence(ctx):
    e,*_=ctx
    init_db(e)
    for name in ['quality_source_links','quality_event_history','quality_capa_source_links']:
        assert one(e,"SELECT name FROM sqlite_master WHERE type='table' AND name=:n",{'n':name})


def test_new_beneficiary_signalement_is_one_case_with_two_source_links(ctx):
    e,aid,_,bid,_,_=ctx
    report_id=create_beneficiary_report(e,aid,bid,'Observation','Essai qualité','Message fictif')
    events=list_quality_events(e,aid)
    assert len(events)==1
    links=quality_case_sources(e,events[0]['id'])
    assert {(x['source_kind'],x['source_id']) for x in links} >= {('BENEFICIARY_REPORT',report_id)}
    assert any(x['source_kind']=='QUALITY_ISSUE' for x in links)
    assert quality_case_history(e,events[0]['id'])[0]['change_kind']=='CREATION'
    assert not any(x['source_kind']=='BENEFICIARY_REPORT' and x['id']==report_id for x in quality_unlinked_sources(e,aid))


def test_report_replies_append_instead_of_overwriting_history(ctx):
    e,aid,_,bid,_,_=ctx
    rid=create_beneficiary_report(e,aid,bid,'Observation','Question','Bonjour')
    event=list_quality_events(e,aid)[0]['id']
    assert update_user_report(e,'BENEFICIARY',rid,'EN_COURS','Nous analysons',ADMIN)[0]
    assert update_user_report(e,'BENEFICIARY',rid,'TRAITE','Veuillez consulter la réponse',ADMIN)[0]
    assert update_user_report(e,'BENEFICIARY',rid,'CLOTURE','Réponse finale',ADMIN)[0]
    assert one(e,'SELECT status,closed_at,admin_response FROM beneficiary_reports WHERE id=:i',{'i':rid})['status']=='CLOTURE'
    assert quality_case(e,event)['event']['status']=='CLOTURE'
    assert [x['message'] for x in quality_case_messages(e,event)]==['Nous analysons','Veuillez consulter la réponse','Réponse finale']
    history=quality_case_history(e,event)
    assert len([h for h in history if h['change_kind']=='MODIFICATION'])>=3
    assert len([h for h in history if h['change_kind']=='MESSAGE'])==3
    # Idempotence, same response does not append a duplicate.
    assert update_user_report(e,'BENEFICIARY',rid,'CLOTURE','Réponse finale',ADMIN)[0]
    assert len(quality_case_messages(e,event))==3


def test_canonical_state_updates_linked_report_and_legacy_issue(ctx):
    e,aid,_,bid,_,_=ctx
    rid=create_beneficiary_report(e,aid,bid,'Observation','Un problème','Description')
    event=list_quality_events(e,aid)[0]['id']
    issue=next(x['source_id'] for x in quality_case_sources(e,event) if x['source_kind']=='QUALITY_ISSUE')
    update_quality_event(e,event,ADMIN,status='EN_TRAITEMENT',qualification='Vérification engagée')
    assert one(e,'SELECT status FROM beneficiary_reports WHERE id=:i',{'i':rid})['status']=='EN_COURS'
    update_quality_event(e,event,ADMIN,status='CLASSE_SANS_SUITE',closure_comment='Signalement doublon confirmé')
    assert one(e,'SELECT status FROM beneficiary_reports WHERE id=:i',{'i':rid})['status']=='TRAITE'
    assert one(e,'SELECT status FROM quality_issues WHERE id=:i',{'i':issue})['status']=='CLOTUREE'
    update_quality_event(e,event,ADMIN,status='EN_TRAITEMENT')
    assert one(e,'SELECT closed_at FROM quality_events WHERE id=:i',{'i':event})['closed_at'] is None
    assert one(e,'SELECT closed_at FROM quality_issues WHERE id=:i',{'i':issue})['closed_at'] is None


def test_invalid_status_or_unmotivated_refusal_is_atomic(ctx):
    e,aid,_,_,_,_=ctx
    event=create_quality_event(e,'EXPRESSION','OBSERVATION','Test','',ADMIN,action_id=aid)
    count=len(quality_case_history(e,event))
    with pytest.raises(ValueError):update_quality_event(e,event,ADMIN,status='SUPPRIME')
    with pytest.raises(ValueError):update_quality_event(e,event,ADMIN,status='CLASSE_SANS_SUITE')
    assert len(quality_case_history(e,event))==count
    assert one(e,'SELECT status FROM quality_events WHERE id=:i',{'i':event})['status']=='NOUVEAU'


def test_message_visibility_requires_verified_source(ctx):
    e,aid,_,bid,_,_=ctx
    event=create_quality_event(e,'EXPRESSION','OBSERVATION','Interne','',ADMIN,action_id=aid)
    with pytest.raises(ValueError): add_quality_case_message(e,event,ADMIN,'À envoyer','VERS_BENEFICIAIRE')
    with pytest.raises(ValueError): add_quality_case_message(e,event,ADMIN,' ','INTERNE')
    add_quality_case_message(e,event,ADMIN,'Note interne','INTERNE')
    assert quality_case_messages(e,event)[0]['direction']=='INTERNE'


def test_cross_action_and_duplicate_link_protection(ctx):
    e,aid,other,bid,_,_=ctx
    now=utcnow_iso()
    rid=execute(e,"""INSERT INTO beneficiary_reports(action_id,beneficiary_id,report_type,subject,description,created_at,updated_at)
      VALUES(:a,:b,'Observation','Question','Texte',:n,:n)""",{'a':aid,'b':bid,'n':now})
    wrong=create_quality_event(e,'EXPRESSION','OBSERVATION','Question','Texte',ADMIN,action_id=other,beneficiary_id=bid,origin='SIGNALEMENT_BENEFICIAIRE')
    with pytest.raises(ValueError,match='actions différentes'):link_quality_source(e,wrong,'BENEFICIARY_REPORT',rid,ADMIN)
    event=create_quality_event(e,'EXPRESSION','OBSERVATION','Question','Texte',ADMIN,action_id=aid,beneficiary_id=bid,origin='SIGNALEMENT_BENEFICIAIRE')
    assert link_quality_source(e,event,'BENEFICIARY_REPORT',rid,ADMIN)
    assert link_quality_source(e,event,'BENEFICIARY_REPORT',rid,ADMIN) is False
    other_event=create_quality_event(e,'EXPRESSION','OBSERVATION','Question','Texte',ADMIN,action_id=aid,beneficiary_id=bid,origin='SIGNALEMENT_BENEFICIAIRE')
    with pytest.raises(ValueError,match='autre fiche'):link_quality_source(e,other_event,'BENEFICIARY_REPORT',rid,ADMIN)


def test_unlinked_legacy_suggestions_never_auto_merged(ctx):
    e,aid,_,bid,_,_=ctx
    now=utcnow_iso()
    rid=execute(e,"""INSERT INTO beneficiary_reports(action_id,beneficiary_id,report_type,subject,description,created_at,updated_at)
       VALUES(:a,:b,'Observation','Archive','Contenu exact',:n,:n)""",{'a':aid,'b':bid,'n':now})
    ev=create_quality_event(e,'EXPRESSION','OBSERVATION','Archive','Contenu exact',ADMIN,
         action_id=aid,beneficiary_id=bid,origin='SIGNALEMENT_BENEFICIAIRE')
    candidate=suggest_quality_links(e,aid)
    assert len(candidate)==1 and candidate[0]['id']==ev
    assert not quality_case_sources(e,ev)
    assert link_quality_source(e,ev,'BENEFICIARY_REPORT',rid,ADMIN)
    assert not suggest_quality_links(e,aid)


def test_ambiguous_legacy_sources_not_suggested(ctx):
    e,aid,_,bid,_,_=ctx; now=utcnow_iso()
    execute(e,"""INSERT INTO beneficiary_reports(action_id,beneficiary_id,report_type,subject,description,created_at,updated_at)
       VALUES(:a,:b,'Observation','Doublon','Identique',:n,:n)""",{'a':aid,'b':bid,'n':now})
    for _ in range(2):create_quality_event(e,'EXPRESSION','OBSERVATION','Doublon','Identique',ADMIN,
        action_id=aid,beneficiary_id=bid,origin='SIGNALEMENT_BENEFICIAIRE')
    assert not suggest_quality_links(e,aid)


def test_legacy_issue_and_improvement_are_single_canonical_case(ctx):
    e,aid,_,_,_,_=ctx
    iid=create_quality_issue(e,aid,'RECLAMATION','Une réclamation','Détails','Admin',ADMIN)
    ev=quality_case_sources(e,list_quality_events(e,aid)[0]['id'])[0]
    assert any(x['source_kind']=='QUALITY_ISSUE' and x['source_id']==iid for x in quality_case_sources(e,list_quality_events(e,aid)[0]['id']))
    capa=create_improvement_action(e,aid,'Corriger','Action fictive','Responsable','2026-10-17',iid,ADMIN)
    mirror=one(e,"SELECT * FROM quality_capa_source_links WHERE source_kind='IMPROVEMENT_ACTION' AND source_id=:i",{'i':capa})
    assert mirror is not None
    update_improvement_action(e,capa,'TERMINEE',ADMIN)
    assert one(e,'SELECT status FROM quality_event_actions WHERE id=:i',{'i':mirror['quality_event_action_id']})['status']=='TERMINEE'
    update_quality_issue(e,iid,'CLOTUREE','Responsable',ADMIN)
    assert list_quality_events(e,aid)[0]['status']=='CLOTURE'


def test_capa_history_is_append_only_and_noop_does_not_duplicate(ctx):
    e,aid,_,_,_,_=ctx
    event=create_quality_event(e,'AUDIT','OBSERVATION','Écart','Fictif',ADMIN,action_id=aid)
    cid=add_quality_event_action(e,event,'Vérifier',ADMIN)
    prev=len(quality_case_history(e,event))
    update_quality_event_action(e,cid,ADMIN,status='EN_COURS',owner_name='Responsable')
    assert len(quality_case_history(e,event))==prev+1
    update_quality_event_action(e,cid,ADMIN,status='EN_COURS',owner_name='Responsable')
    assert len(quality_case_history(e,event))==prev+1


def test_quality_tab_and_general_share_single_rendering_code(ctx):
    src=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
    assert src.count('def render_quality_case_workbench(')==1
    assert "render_quality_case_workbench(action_id=a['id']" in src
    assert 'render_quality_case_workbench(action_id=action_id,' in src
    chunk=src[src.index('def quality_tab(a):'):src.index('def documents_tab(a):')]
    assert 'update_quality_issue(' not in chunk and 'update_user_report(' not in chunk


def test_event_action_context_is_preserved(ctx):
    e,aid,other,_,_,_=ctx
    first=create_quality_event(e,'AUDIT','OBSERVATION','Première','Fictif',ADMIN,action_id=aid)
    second=create_quality_event(e,'AUDIT','OBSERVATION','Deuxième','Fictif',ADMIN,action_id=other)
    assert [x['id'] for x in list_quality_events(e,aid)]==[first]
    assert [x['id'] for x in list_quality_events(e,other)]==[second]


def test_purge_j1_cascades_j2_history_and_links(ctx):
    e,aid,other,bid,_,tmp=ctx
    rid=create_beneficiary_report(e,aid,bid,'Observation','Fictif','Données fictives')
    event=list_quality_events(e,aid)[0]['id']
    add_quality_case_message(e,event,ADMIN,'Note fictive')
    cert=certify_test_action(e,aid,ADMIN,evidence='Je certifie que toutes les données de TEST-J2 sont fictives et non réelles.',
         confirmation='JE CERTIFIE ESSAI TEST-J2',password='j2-only-secret-password',data_root=tmp)
    assert cert[0],cert
    preview=preview_action_purge(e,aid,data_root=tmp)
    result=purge_certified_action(e,aid,ADMIN,confirmation='SUPPRIMER ESSAI TEST-J2',
         preview_fingerprint=preview['fingerprint'],data_root=tmp)
    assert result[0],result
    assert not q(e,'SELECT * FROM quality_source_links')
    assert not q(e,'SELECT * FROM quality_event_history')
    assert not q(e,'SELECT * FROM quality_event_messages')
    assert one(e,'SELECT id FROM actions WHERE id=:i',{'i':other})
    assert not q(e,'PRAGMA foreign_key_check')


def test_quality_legacy_issues_are_never_deleted_when_unlinked(ctx):
    e,aid,_,_,_,_=ctx;now=utcnow_iso()
    iid=execute(e,"INSERT INTO quality_issues(action_id,issue_type,title,created_at) VALUES(:a,'DIFFICULTE','Ancienne fiche',:n)",{'a':aid,'n':now})
    assert any(x['source_kind']=='QUALITY_ISSUE' and x['id']==iid for x in quality_unlinked_sources(e,aid))
    assert one(e,'SELECT id FROM quality_issues WHERE id=:i',{'i':iid})
