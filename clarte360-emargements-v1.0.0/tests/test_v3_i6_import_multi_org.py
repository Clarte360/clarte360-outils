import io, json
import pandas as pd
from db import make_engine, init_db, q, one
from services import (
    ensure_default_organization, upsert_organization, list_organizations,
    save_import_profile, list_import_profiles, get_import_profile, ensure_default_import_profile
)
from excel_import import read_action_xlsm
import source_store


def _workbook_bytes(action_key='ACTION_ID', action_no='X100'):
    conv=pd.DataFrame([{
        action_key:action_no,'TITLE_X':'Formation générique','CLIENT_X':'Client Test','HOURS_X':7,
        'TRAINER_X':'Intervenant Test','DATE_START_X':'2026-10-01','DATE_END_X':'2026-10-02'
    }])
    stag=pd.DataFrame([{
        action_key:action_no,'TITLE_X':'Formation générique','CLIENT_X':'Client Test','HOURS_X':7,
        'LAST_X':'DURAND','FIRST_X':'Marie','BIRTH_X':'1990-02-03','MAIL_X':'m@example.org'
    }])
    bio=io.BytesIO()
    with pd.ExcelWriter(bio,engine='openpyxl') as w:
        conv.to_excel(w,sheet_name='ACTIONS',index=False)
        stag.to_excel(w,sheet_name='PERSONNES',index=False)
    return bio.getvalue()


def test_i6_schema_and_profiles_are_organization_scoped(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'i6.db')); init_db(e)
    o1=ensure_default_organization(e,'Organisme A')
    o2=upsert_organization(e,None,{'name':'Organisme B','timezone':'Europe/Paris'},'admin')
    p1=save_import_profile(e,None,o1,{'code':'MAIN','name':'Base A','action_key':'NO_A','action_sheet':'A','participant_sheet':'P','mapping_json':'{}','config_json':'{}','active':True},'admin')
    p2=save_import_profile(e,None,o2,{'code':'MAIN','name':'Base B','action_key':'NO_B','action_sheet':'A','participant_sheet':'P','mapping_json':'{}','config_json':'{}','active':True},'admin')
    assert p1 != p2
    assert [x['id'] for x in list_import_profiles(e,o1)] == [p1]
    assert [x['id'] for x in list_import_profiles(e,o2)] == [p2]
    assert get_import_profile(e,p1)['action_key']=='NO_A'
    assert len(list_organizations(e,active_only=True))==2


def test_i6_generic_excel_mapping_has_no_clarte_or_adca_dependency(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'i6map.db')); init_db(e); oid=ensure_default_organization(e,'Organisme Générique')
    mapping={
        'title':['TITLE_X'],'client_name':['CLIENT_X'],'planned_hours':['HOURS_X'],'trainer_name':['TRAINER_X'],
        'date_start':['DATE_START_X'],'date_end':['DATE_END_X'],'participant_last_name':['LAST_X'],
        'participant_first_name':['FIRST_X'],'participant_birth_date':['BIRTH_X'],'participant_email':['MAIL_X']
    }
    pid=save_import_profile(e,None,oid,{'code':'GEN','name':'ERP générique','action_key':'ACTION_ID','action_sheet':'ACTIONS','participant_sheet':'PERSONNES','mapping_json':json.dumps(mapping),'config_json':'{}','active':True},'admin')
    profile=get_import_profile(e,pid)
    data,parts=read_action_xlsm(_workbook_bytes(), 'X100', profile, 'INTRA')
    assert data['title']=='Formation générique'
    assert data['client_name']=='Client Test'
    assert data['planned_hours']==7.0
    assert data['organization_id']==oid
    assert data['source']=='ERP générique'
    assert len(parts)==1 and parts[0]['last_name']=='DURAND' and parts[0]['email']=='m@example.org'


def test_i6_default_profile_is_idempotent_and_key_is_parameterized(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'default.db')); init_db(e); oid=ensure_default_organization(e,'Org')
    p1=ensure_default_import_profile(e,oid,'CUSTOM_NO')
    p2=ensure_default_import_profile(e,oid,'OTHER_NO')
    assert p1==p2
    assert get_import_profile(e,p1)['action_key']=='CUSTOM_NO'


def test_i6_source_store_is_generic_and_isolated_by_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(source_store,'STORE_DIR',tmp_path/'sources')
    monkeypatch.setattr(source_store,'META_PATH',tmp_path/'sources'/'sources.json')
    source_store.STORE_DIR.mkdir(parents=True,exist_ok=True)
    source_store.save_uploaded_source('PROFILE_1','a.xlsx',b'AAA')
    source_store.save_uploaded_source('PROFILE_2','b.xlsx',b'BBB')
    a,ia=source_store.read_snapshot('PROFILE_1'); b,ib=source_store.read_snapshot('PROFILE_2')
    assert a==b'AAA' and b==b'BBB'
    assert ia['snapshot_path'] != ib['snapshot_path']
    source_store.set_external_path('PROFILE_1','/tmp/source-a.xlsx')
    assert source_store.source_info('PROFILE_1')['external_path']=='/tmp/source-a.xlsx'

def test_i6_ui_no_longer_exposes_rigid_clarte_adca_import_tabs():
    text=open('app.py',encoding='utf-8').read()
    assert 'Base GESTION OF CLARTE360 (.xlsm)' not in text
    assert 'Base GESTION OF ADCA (.xlsm)' not in text
    assert 'Importer une action' in text
    assert 'Base de gestion de l’organisme' in text


def test_i6_profile_mapping_is_audited(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'audit.db')); init_db(e); oid=ensure_default_organization(e,'Org Audit')
    pid=save_import_profile(e,None,oid,{'code':'AUD','name':'Source Audit','action_key':'ACT','mapping_json':'{}','config_json':'{}','active':True},'admin@example.org')
    row=one(e,"SELECT * FROM audit_log WHERE event_type='IMPORT_PROFILE_CREATED' AND entity_id=:i",{'i':str(pid)})
    assert row is not None
