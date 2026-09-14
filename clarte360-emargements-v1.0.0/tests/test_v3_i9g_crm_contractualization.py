import json
import pytest
from db import make_engine, init_db, q, one, execute
from services import (
    create_action, add_participant, create_beneficiary, link_participant_to_beneficiary,
    create_crm_contact, list_crm_contacts, set_crm_marketing_consent, update_crm_status,
    convert_crm_contact_to_beneficiary, build_contractualization_context,
    prepare_contractualization_case, list_contractualization_cases, update_contractualization_case,
)

def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e

def seed_action(e,no='I9G-001'):
    aid=create_action(e,{
        'action_no':no,'title':'Bilan I9-G','subtitle':None,'nature':'Bilan de compétences','mode':'INDIVIDUEL',
        'client_name':'Particulier','client_type':'Particulier','group_code':None,'planned_hours':15,
        'expected_participants':1,'admin_email':'admin@example.org','trainer_name':None,'trainer_email':None,
        'location':'Visio','notes':None,'source':'TEST'
    },'test')
    execute(e,"UPDATE actions SET prestation_type='BILAN_COMPETENCES',delivery_mode='DISTANCIEL_VISIO',start_date='2026-10-01',end_date='2026-11-30' WHERE id=:a",{'a':aid})
    pid,_=add_participant(e,aid,{'last_name':'MARTIN','first_name':'Alice','birth_date':'1988-03-04','email':'alice@example.org'},'test')
    bid=create_beneficiary(e,'MARTIN','Alice','1988-03-04','alice@example.org',actor='test')
    link_participant_to_beneficiary(e,pid,bid,'test')
    execute(e,"INSERT INTO slots(action_id,slot_date,start_time,end_time,status,created_at,updated_at) VALUES(:a,'2026-10-10','09:00','10:30','PREVU','n','n')",{'a':aid})
    return aid,pid,bid

def test_i9g_schema_adds_crm_and_contractualization_without_replacing_existing_tables():
    e=eng(); tables={x['name'] for x in q(e,"SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ('crm_contacts','crm_events','contractualization_cases','contractualization_events','actions','beneficiaries'):
        assert t in tables

def test_i9g_marketing_consent_is_independent_from_research_consent_and_revocable():
    e=eng(); c=create_crm_contact(e,'Bob','Durand','bob@example.org',research_consent_at='2026-09-12T10:00:00Z',marketing_consent=False,rgpd_notice_version='RGPD-1',actor='admin')
    assert c['research_consent_at'] and not c['marketing_consent']
    set_crm_marketing_consent(e,c['id'],True,'admin','RGPD-2')
    r=one(e,'SELECT * FROM crm_contacts WHERE id=:i',{'i':c['id']}); assert r['marketing_consent']==1 and r['marketing_consent_at'] and r['research_consent_at']
    set_crm_marketing_consent(e,c['id'],False,'admin','RGPD-2')
    r=one(e,'SELECT * FROM crm_contacts WHERE id=:i',{'i':c['id']}); assert r['marketing_consent']==0 and r['marketing_revoked_at']

def test_i9g_crm_statuses_and_events_are_traceable():
    e=eng(); c=create_crm_contact(e,'Bob','Durand','bob@example.org',actor='admin')
    update_crm_status(e,c['id'],'A_CONTACTER','admin'); update_crm_status(e,c['id'],'CONTACTE','admin')
    assert list_crm_contacts(e)[0]['status']=='CONTACTE'
    assert len(q(e,'SELECT * FROM crm_events WHERE contact_id=:c',{'c':c['id']}))>=3
    with pytest.raises(ValueError): update_crm_status(e,c['id'],'INVENTE','admin')

def test_i9g_conversion_reuses_exact_existing_beneficiary_instead_of_duplicating():
    e=eng(); bid=create_beneficiary(e,'DURAND','Bob','1980-01-02','old@example.org',actor='test'); b=one(e,'SELECT * FROM beneficiaries WHERE id=:i',{'i':bid})
    c=create_crm_contact(e,'Bob','Durand','bob@example.org',actor='admin')
    got=convert_crm_contact_to_beneficiary(e,c['id'],'1980-01-02','admin')
    assert got['id']==b['id']
    assert len(q(e,"SELECT * FROM beneficiaries WHERE last_name='DURAND' AND first_name='Bob'"))==1
    assert one(e,'SELECT status,beneficiary_id FROM crm_contacts WHERE id=:i',{'i':c['id']})=={'status':'CONVERTI','beneficiary_id':b['id']}

def test_i9g_contract_context_matches_future_contractualisation_boundary():
    e=eng(); aid,pid,bid=seed_action(e)
    ctx=build_contractualization_context(e,aid,bid,pid,contract_type='BC_PARTICULIER_BIPARTITE',aps_ref='APS-123')
    assert ctx['format']=='CLARTE360_CONTRACTUALISATION_CONTEXT_V1'
    assert ctx['action']['no_clar']=='I9G-001' and ctx['action']['prestation_type']=='BILAN_COMPETENCES'
    assert ctx['beneficiary']['beneficiary_id'].startswith('BEN-')
    assert ctx['aps']['reference']=='APS-123' and len(ctx['calendar'])==1
    assert 'pdf' not in ctx and 'financements' not in ctx

def test_i9g_contract_case_tracks_status_and_returned_document_references_without_generating_contract():
    e=eng(); aid,pid,bid=seed_action(e)
    case=prepare_contractualization_case(e,aid,bid,pid,contract_type='BC_PARTICULIER_BIPARTITE',aps_ref='APS-123',actor='admin')
    assert case['status']=='A_PREPARER'
    update_contractualization_case(e,case['id'],'GENEREE',external_ref='CTX-EXT-1',pdf_ref='docs/I9G-001_contrat.pdf',json_ref='docs/I9G-001_dossier.json',financing_refs=['FIN-1'],actor='admin')
    row=list_contractualization_cases(e,action_id=aid)[0]
    assert row['status']=='GENEREE' and row['pdf_ref'].endswith('.pdf') and row['json_ref'].endswith('.json')
    assert json.loads(row['financing_refs_json'])==['FIN-1']
    assert len(q(e,'SELECT * FROM contractualization_events WHERE case_id=:c',{'c':case['id']}))==2

def test_i9g_contract_context_rejects_cross_action_participant():
    e=eng(); aid,pid,bid=seed_action(e,'I9G-001'); aid2,_,_=seed_action(e,'I9G-002')
    with pytest.raises(ValueError): build_contractualization_context(e,aid2,bid,pid)
