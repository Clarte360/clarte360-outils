import json
import pytest
from db import make_engine, init_db, execute, one
from security import hash_password
from services import (
    create_professional_intervenant, create_professional_candidate, get_professional_360,
    update_professional_identity, update_professional_profile,
    add_professional_experience, add_professional_education,
    store_professional_document, professional_global_ai_reanalysis_state,
    save_global_professional_ai_analysis, professional_reset_preview,
    reset_professional_dossier
)


def eng(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'rc22.db')); init_db(e)
    execute(e,"INSERT INTO admins(email,password_hash,full_name,active,role,created_at) VALUES(:e,:p,'Admin',1,'ADMIN','2026-10-01T00:00:00+00:00')",
            {'e':'admin@test','p':hash_password('Secret-Admin-2026')})
    return e


def test_identity_is_separate_from_professional_title(tmp_path):
    e=eng(tmp_path)
    p=create_professional_intervenant(e,'BEN ROMDHANE Christelle','c@example.org',actor='admin@test')
    prof=get_professional_360(e,p)
    assert prof['display_name']=='BEN ROMDHANE Christelle'
    assert prof.get('title') is None
    update_professional_identity(e,p,'Christelle','BEN ROMDHANE','admin@test')
    prof=get_professional_360(e,p)
    assert prof['first_name']=='Christelle'
    assert prof['last_name']=='BEN ROMDHANE'
    assert prof['display_name']=='Christelle BEN ROMDHANE'
    assert prof['full_name']=='Christelle BEN ROMDHANE'
    assert prof.get('title') is None


def test_same_name_different_hash_is_new_version(tmp_path):
    e=eng(tmp_path); p=create_professional_candidate(e,'Test Person','x@example.org',actor='admin@test')
    d1=store_professional_document(e,p,b'old bytes','CV.pdf','CV','admin@test')
    save_global_professional_ai_analysis(e,p,{'profile':{'title':None,'summary':None,'specialties':[]},'experiences':[],
        'education':[],'certifications':[],'languages':[],'identity_alerts':[],'missing_points':[],'service_candidates':[]},
        'admin@test','openai','model','prompt','hash',None,[d1])
    state=professional_global_ai_reanalysis_state(e,p)
    assert state['to_analyze_ids']==[]
    d2=store_professional_document(e,p,b'new bytes','CV.pdf','CV','admin@test')
    assert d2!=d1
    assert one(e,'SELECT archived_at FROM professional_documents WHERE id=:i',{'i':d1})['archived_at'] is not None
    state=professional_global_ai_reanalysis_state(e,p)
    assert state['to_analyze_ids']==[d2]
    assert state['removed_documents'][0]['id']==d1
    assert state['new_versions'][0]['current']['id']==d2


def test_exact_same_name_and_hash_does_not_create_second_row(tmp_path):
    e=eng(tmp_path); p=create_professional_candidate(e,'Test Person','y@example.org',actor='admin@test')
    d1=store_professional_document(e,p,b'same','piece.pdf','AUTRE','admin@test')
    d2=store_professional_document(e,p,b'same','piece.pdf','AUTRE','admin@test')
    assert d2==d1
    assert one(e,'SELECT COUNT(*) n FROM professional_documents WHERE professional_person_id=:p',{'p':p})['n']==1


def test_reset_requires_admin_password_and_preserves_identity_status_documents(tmp_path):
    e=eng(tmp_path); p=create_professional_intervenant(e,'Active Test','active@example.org',actor='admin@test')
    update_professional_identity(e,p,'Active','Test','admin@test')
    update_professional_profile(e,p,{'title':'Consultant','summary':'Résumé','collaboration_type':'A_DEFINIR','email':'active@example.org'},'admin@test')
    add_professional_experience(e,p,'Consultant','Entreprise',actor='admin@test')
    add_professional_education(e,p,'Diplôme','Ecole',actor='admin@test')
    d=store_professional_document(e,p,b'document','cv.pdf','CV','admin@test')
    save_global_professional_ai_analysis(e,p,{'profile':{'title':'Consultant','summary':'Résumé','specialties':[]},'experiences':[],
        'education':[],'certifications':[],'languages':[],'identity_alerts':[],'missing_points':[],'service_candidates':[]},
        'admin@test','openai','model','prompt','hash',None,[d])
    preview=professional_reset_preview(e,p)
    assert preview['active'] is True and preview['principal_status']=='INTERVENANT'
    assert preview['counts']['professional_experiences']==1
    with pytest.raises(ValueError,match='Mot de passe'):
        reset_professional_dossier(e,p,'admin@test','wrong')
    result=reset_professional_dossier(e,p,'admin@test','Secret-Admin-2026')
    assert result['snapshot_sha256']
    prof=get_professional_360(e,p)
    assert prof['principal_status']=='INTERVENANT' and prof['active']==1
    assert prof['display_name']=='Active Test'
    assert len(prof['documents'])==1
    assert prof['experiences']==[] and prof['education']==[]
    assert prof.get('title') is None and prof.get('summary') is None
    assert one(e,'SELECT COUNT(*) n FROM professional_global_ai_runs WHERE professional_person_id=:p',{'p':p})['n']==0


def test_accepted_structured_facts_are_idempotent(tmp_path):
    e=eng(tmp_path); p=create_professional_candidate(e,'Dedup Test','d@example.org',actor='admin@test')
    a=add_professional_experience(e,p,'Président','ADCA','2001-10',None,True,'Pilotage','admin@test')
    b=add_professional_experience(e,p,'Président','ADCA','2001-10',None,True,'Pilotage','admin@test')
    assert a==b
    assert one(e,'SELECT COUNT(*) n FROM professional_experiences WHERE professional_person_id=:p',{'p':p})['n']==1


def test_unused_dossier_can_be_deleted_even_with_internal_analysis_data(tmp_path):
    from services import professional_delete_dependencies, delete_professional_if_unused
    e=eng(tmp_path); p=create_professional_intervenant(e,'Delete Me','delete@example.org',actor='admin@test')
    update_professional_identity(e,p,'Delete','Me','admin@test')
    add_professional_experience(e,p,'Consultant','TestCo',actor='admin@test')
    d=store_professional_document(e,p,b'internal document','doc.pdf','AUTRE','admin@test')
    save_global_professional_ai_analysis(e,p,{'profile':{'title':'Consultant','summary':None,'specialties':[]},'experiences':[],
        'education':[],'certifications':[],'languages':[],'identity_alerts':[],'missing_points':[],'service_candidates':[]},
        'admin@test','openai','model','prompt','hash-delete',None,[d])
    assert professional_delete_dependencies(e,p)==[]
    prof=get_professional_360(e,p); tid=prof['trainer_id']
    assert delete_professional_if_unused(e,p,'admin@test') is True
    assert one(e,'SELECT * FROM professional_persons WHERE professional_person_id=:p',{'p':p}) is None
    assert one(e,'SELECT * FROM trainers WHERE id=:t',{'t':tid}) is None


def test_external_action_usage_still_blocks_physical_delete(tmp_path):
    from services import professional_delete_dependencies, delete_professional_if_unused
    e=eng(tmp_path); p=create_professional_intervenant(e,'Used Person','used@example.org',actor='admin@test')
    tid=get_professional_360(e,p)['trainer_id']
    execute(e,"""INSERT INTO actions(action_no,title,nature,mode,planned_hours,status,trainer_id,created_at,updated_at)
      VALUES('A-RC22','Test','FORMATION','PRESENTIEL',1,'BROUILLON',:t,'2026-10-01','2026-10-01')""",{'t':tid})
    deps=professional_delete_dependencies(e,p)
    assert any('action historique' in x for x in deps)
    with pytest.raises(ValueError,match='action historique'):
        delete_professional_if_unused(e,p,'admin@test')


def test_global_gateway_sends_scanned_pdf_as_input_file():
    from qualification_ai import GlobalDossierAIGateway

    class Resp:
        def __init__(self, payload):
            self.status='completed'; self.output_text=json.dumps(payload)
            self.usage=type('U',(),{'input_tokens':10,'output_tokens':5})()
    class Responses:
        def __init__(self): self.calls=[]
        def create(self, **kwargs):
            self.calls.append(kwargs)
            name=kwargs['text']['format']['name']
            if name=='dossier_professionnel_faits':
                return Resp({'profile':{'title':None,'summary':None,'specialties':[]},'experiences':[],
                    'education':[],'certifications':[],'languages':[],'identity_alerts':[],'missing_points':[]})
            return Resp({'service_candidates':[{'service_id':1,'service_level':0,'confidence':0.8,
                'rationale':'Aucun élément','source_document_ids':[],'missing_points':[],'evidence':[],'criteria':[]}]})
    class Client:
        def __init__(self): self.responses=Responses()

    client=Client(); gw=GlobalDossierAIGateway('', 'gpt-5.6-terra', client=client)
    gw.analyze({'documents':[{'id':8,'name':'Diplome BTS.pdf'}],
        'document_contents':[{'document_id':8,'name':'Diplome BTS.pdf','category':'DIPLOME','text':'[PDF SCANNE]'}],
        'document_files':[{'document_id':8,'name':'Diplome BTS.pdf','category':'DIPLOME','data_url':'data:application/pdf;base64,AAAA'}],
        'service_catalog':[{'service_id':1,'name':'Test','criteria':[]}]})
    content=client.responses.calls[0]['input'][0]['content']
    assert any(x.get('type')=='input_file' and x.get('filename')=='Diplome BTS.pdf' for x in content)


def test_rc22_ui_promotes_human_decision_and_menu_entry():
    from pathlib import Path
    src=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
    assert "'Intervenants / Partenaires','Paramètres'" in src
    assert "'Décision humaine'" in src
    assert 'Éléments repérés — niveau global bloqué' in src
    assert "button('Retenir pour instruction'" not in src
