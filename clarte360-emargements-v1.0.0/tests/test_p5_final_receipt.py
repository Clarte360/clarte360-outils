"""P5 - non-regression supplementaire sur changements de nature d'action.

Toutes les identites et donnees sont fictives. Aucun VPS/CRM distant.
"""
import pytest
from db import make_engine,init_db,execute,utcnow_iso,one
from services import create_action,create_crm_contact,set_document_validation,set_document_publication
from client_portal import (create_client_portal_account,issue_client_access_token,redeem_client_access_token,
 grant_client_action,create_client_delivery,share_client_document,list_client_documents,
 read_client_document,export_client_action_zip,client_upload_document,
 client_action_summary,list_client_submissions)
ADMIN='admin-p5@example.test'

@pytest.fixture
def setup_p5(tmp_path,monkeypatch):
    import services
    monkeypatch.setattr(services,'BENEFICIARY_DOC_DIR',tmp_path/'blobs')
    (tmp_path/'blobs').mkdir()
    engine=make_engine('sqlite:///'+str(tmp_path/'p5.db'));init_db(engine)
    execute(engine,"INSERT INTO admins(email,password_hash,active,role,created_at) VALUES(:a,'placeholder',1,'ADMIN',:t)",{'a':ADMIN,'t':utcnow_iso()})
    aid=create_action(engine,{'action_no':'P5-DEMO','title':'Formation laboratoire test','subtitle':None,'nature':'FORMATION','mode':'INTRA','client_name':'Entreprise de test','client_type':'Professionnel','group_code':None,'planned_hours':7,'expected_participants':5,'admin_email':ADMIN,'trainer_name':None,'trainer_email':None,'location':None,'notes':None,'source':'P5_SYNTHETIQUE'},ADMIN)
    cc=create_crm_contact(engine,'Test','Client','test-client@example.test',company='Entreprise de test')['id']
    cl=create_client_portal_account(engine,cc,ADMIN)
    token=issue_client_access_token(engine,cl,ADMIN)
    redeem_client_access_token(engine,token,'Mot2Passe-Long2026!')
    grant_client_action(engine,cl,aid,ADMIN,'CLIENT_ADMIN',can_download=True,can_upload=True)
    rid,_,_=create_client_delivery(engine,aid,b'justificatif synthetique','preuve.pdf',ADMIN)
    set_document_validation(engine,rid,'VALIDE',ADMIN)
    set_document_publication(engine,rid,True,ADMIN)
    share_client_document(engine,rid,cl,ADMIN)
    assert read_client_document(engine,rid,cl,aid)==b'justificatif synthetique'
    return engine,cl,aid,rid

@pytest.mark.parametrize('nature', ['BILAN DE COMPETENCES','COACHING INDIVIDUEL','ACCOMPAGNEMENT INDIVIDUEL'])
def test_requalification_action_interdit_tout_acces_documentaire_client(setup_p5,nature):
    engine,cl,aid,rid=setup_p5
    execute(engine,'UPDATE actions SET nature=:n,prestation_type=:n WHERE id=:a',{'n':nature,'a':aid})
    summary=client_action_summary(engine,cl,aid)
    assert not summary['collective_training']
    with pytest.raises(PermissionError):list_client_documents(engine,cl,aid)
    with pytest.raises(PermissionError):read_client_document(engine,rid,cl,aid)
    with pytest.raises(PermissionError):export_client_action_zip(engine,cl,aid)
    with pytest.raises(PermissionError):client_upload_document(engine,cl,aid,b'new','new.pdf')
    with pytest.raises(PermissionError):list_client_submissions(engine,cl,aid)


def test_remise_preexistante_ne_se_reactive_pas_apres_changement_nature(setup_p5):
    engine,cl,aid,rid=setup_p5
    execute(engine,"UPDATE actions SET nature='BILAN DE COMPETENCES' WHERE id=:a",{'a':aid})
    with pytest.raises(PermissionError):read_client_document(engine,rid,cl,aid)
