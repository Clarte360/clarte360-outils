from pathlib import Path
from db import make_engine,init_db,one
from services import ensure_default_organization,upsert_organization,create_action,add_participant,add_slot,countersign_slot
from pdf_utils import collective_pdf,individual_pdf,certificate_pdf

def action(e):
    oid=ensure_default_organization(e)
    upsert_organization(e,oid,{'name':'OF TRANSFERABLE','legal_name':'OF TRANSFERABLE SAS','address':'1 rue Test','postal_code':'75000','city':'Paris','country':'France','siret':'12345678900011','nda':'11750000075','general_email':'qualite@example.org','timezone':'Europe/Paris','privacy_notice':'Notice test'},'test')
    aid=create_action(e,{'action_no':'REC001','title':'Recette','subtitle':None,'nature':'Formation','mode':'INTRA','client_name':'Client','client_type':'Entreprise','group_code':None,'planned_hours':3.5,'expected_participants':1,'admin_email':'admin@example.org','trainer_name':'Formateur','trainer_email':'f@example.org','location':'Paris','notes':None,'source':'TEST'},'test')
    from services import safe_set_action_modules
    safe_set_action_modules(e,aid,'FORMATION',True,True,True,True,oid,None,'test')
    return aid

def test_candidate_transferable_pdf_branding():
    e=make_engine('sqlite:///:memory:');init_db(e);aid=action(e)
    pid,_=add_participant(e,aid,{'individual_action_no':None,'last_name':'DURAND','birth_name':None,'first_name':'Marie','birth_date':None,'email':'m@example.org','employee_id':None,'company_name':'Client','phone':None},'test')
    sid=add_slot(e,aid,'2026-09-03','09:00','12:30','test');countersign_slot(e,sid,'Formateur','f@example.org','test','Certification')
    # PDFs must generate under a non-Clarte360 organisation without code changes.
    assert b'%PDF' in collective_pdf(e,aid)
    assert b'%PDF' in individual_pdf(e,pid)
    assert b'%PDF' in certificate_pdf(e,pid,draft=True)

def test_candidate_version_is_rc():
    from branding import APP_VERSION
    assert APP_VERSION=='2.0.0-rc1'
